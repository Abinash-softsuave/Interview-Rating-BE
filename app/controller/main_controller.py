"""
Main Controller - API route handlers
"""
import os
import tempfile
import time
from datetime import datetime
from typing import Tuple
import re
from urllib.parse import urlparse, urlencode

from fastapi import FastAPI, HTTPException, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
import httpx

from app.db.database import get_settings
from schemas import (
    BaseResponse, 
    HealthCheckResponse,
    VideoAnalysisResponse,
    VideoUrlRequest
)
from app.services.main_service import (
    VideoAnalyzer
)
from loguru import logger


# Setup - Lazy initialization to avoid errors during import
_settings = None
_logger_configured = False

def _get_settings():
    """Lazy load settings to avoid initialization errors during import"""
    global _settings
    if _settings is None:
        try:
            _settings = get_settings()
            _settings.SERVICE_NAME = "ai-service"
        except Exception as e:
            logger.warning(f"Failed to load settings: {e}. Using defaults.")
            # Create a minimal settings object if loading fails
            from types import SimpleNamespace
            _settings = SimpleNamespace(
                SERVICE_NAME="ai-service",
                GEMINI_API_KEY=os.getenv("GEMINI_API_KEY"),
                WHISPER_MODEL=os.getenv("WHISPER_MODEL", "base"),
                MAX_VIDEO_SIZE_MB=int(os.getenv("MAX_VIDEO_SIZE_MB", "5000")),
                USE_ALTERNATIVE_TRANSCRIPTION=os.getenv("USE_ALTERNATIVE_TRANSCRIPTION", "True").lower() == "true",
                TRANSCRIPTION_SERVICE=os.getenv("TRANSCRIPTION_SERVICE", "assemblyai"),
                TRANSCRIPTION_API_KEY=os.getenv("TRANSCRIPTION_API_KEY"),
                LOG_LEVEL=os.getenv("LOG_LEVEL", "INFO")
            )
    return _settings

def _configure_logger():
    """Configure logger - lazy initialization to avoid errors during import"""
    global _logger_configured
    if _logger_configured:
        return
    
    try:
        settings = _get_settings()
        
        # Setup logging - serverless-friendly (no file system writes)
        # In serverless environments like Vercel, we use console logging only
        # Check if we're in a serverless environment
        IS_SERVERLESS = os.getenv("VERCEL") is not None or os.getenv("AWS_LAMBDA_FUNCTION_NAME") is not None

        if not IS_SERVERLESS:
            # Only use file logging in non-serverless environments
            try:
                if not os.path.exists("logs"):
                    os.makedirs("logs", exist_ok=True)
                logger.add(
                    f"logs/{settings.SERVICE_NAME}.log",
                    rotation="10 MB",
                    retention="7 days",
                    level=settings.LOG_LEVEL,
                    format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {name}:{function}:{line} | {message}"
                )
            except (OSError, PermissionError) as e:
                # Fallback to console if file logging fails
                logger.warning(f"File logging not available: {e}. Using console logging only.")
        else:
            # In serverless, configure console logging with proper format
            import sys
            logger.remove()  # Remove default handler
            logger.add(
                sys.stderr,  # Use stderr for serverless (Vercel captures this)
                level=settings.LOG_LEVEL,
                format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {name}:{function}:{line} | {message}"
            )
        
        _logger_configured = True
    except Exception as e:
        # If logger configuration fails, at least ensure we have basic logging
        logger.warning(f"Logger configuration failed: {e}. Using default logger.")
        _logger_configured = True


def create_app() -> FastAPI:
    """Create and configure FastAPI application"""
    # Configure logger before creating app
    _configure_logger()
    
    app = FastAPI(
        title="AI Service",
        description="AI and Machine Learning service",
        version="1.0.0"
    )
    
    # CORS Middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    return app


def _is_valid_video_file(file_path: str, first_bytes: bytes = None) -> bool:
    """Validate that a file is actually a valid video file by checking file magic bytes"""
    try:
        # Video file magic numbers (file signatures)
        video_signatures = {
            b'\x00\x00\x00\x20ftypisom',  # MP4 ISO Media
            b'\x00\x00\x00\x18ftypmp41',  # MP4 v1
            b'\x00\x00\x00\x18ftypmp42',  # MP4 v2
            b'\x00\x00\x00\x1cftypmp41',  # MP4
            b'\x00\x00\x00\x20ftypmp41',  # MP4
            b'ftyp',  # MP4/MOV (usually starts with ftyp)
            
            # QuickTime/MOV files
            b'\x00\x00\x00\x14ftypqt  ',  # QuickTime
            b'\x00\x00\x00\x20ftypqt  ',  # QuickTime
            
            # WebM files
            b'\x1a\x45\xdf\xa3',  # WebM (EBML header)
            
            # AVI files
            b'RIFF',  # AVI files start with RIFF
            
            # FLV files
            b'FLV',
            
            # MKV files
            b'\x1a\x45\xdf\xa3',  # Matroska (same as WebM)
        }
        
        # Read first bytes from file if not provided
        if first_bytes is None or len(first_bytes) < 4:
            with open(file_path, "rb") as f:
                first_bytes = f.read(16)
        
        if len(first_bytes) < 4:
            return False
        
        # Check for common video file signatures
        # Check for MP4/MOV (ftyp at offset 4)
        if len(first_bytes) >= 8 and first_bytes[4:8] == b'ftyp':
            return True
        
        # Check for WebM/MKV (EBML header)
        if first_bytes[:4] == b'\x1a\x45\xdf\xa3':
            return True
        
        # Check for AVI (RIFF...AVI)
        if first_bytes[:4] == b'RIFF':
            # Check if it contains AVI header (at offset 8)
            if len(first_bytes) >= 12 and b'AVI' in first_bytes[8:12]:
                return True
        
        # Check for FLV
        if first_bytes[:3] == b'FLV':
            return True
        
        # Additional check: if file extension is known video format and file size is reasonable
        file_ext = os.path.splitext(file_path)[1].lower()
        video_extensions = {'.mp4', '.mov', '.avi', '.mkv', '.webm', '.flv', '.wmv', '.m4v'}
        if file_ext in video_extensions:
            # Check file size (should be at least a few KB for a video)
            file_size = os.path.getsize(file_path)
            if file_size > 1024:  # At least 1KB
                # Try using ffprobe as a last resort to validate
                try:
                    import subprocess
                    result = subprocess.run(
                        ["ffprobe", "-v", "error", "-show_entries", "format=format_name", 
                         "-of", "default=noprint_wrappers=1:nokey=1", file_path],
                        capture_output=True,
                        timeout=5,
                        check=True
                    )
                    # If ffprobe succeeded, it's a valid video file
                    return True
                except (subprocess.CalledProcessError, subprocess.TimeoutExpired, FileNotFoundError):
                    return False
        
        return False
        
    except Exception as e:
        logger.warning(f"Error validating video file: {e}")
        return False


async def download_video_from_url(url: str, output_path: str, filename_hint: str = None, file_id: str = None, is_retry: bool = False, retry_count: int = 0, tried_urls: set = None) -> Tuple[str, float]:
    """
    Download video from URL (supports Google Drive, Loom, and generic URLs)
    
    Args:
        url: Video URL to download
        output_path: Path to save the downloaded video
        filename_hint: Optional filename hint for file extension detection
        file_id: Optional Google Drive file ID (for retries)
        is_retry: Whether this is a retry attempt (skip URL validation)
        retry_count: Current retry attempt count (prevents infinite loops)
        tried_urls: Set of URLs already tried (prevents retrying same URL)
    
    Returns:
        Tuple of (downloaded_file_path, file_size_mb)
    
    Raises:
        HTTPException: For various error conditions with appropriate status codes
    """
    # Initialize tried_urls set if not provided
    if tried_urls is None:
        tried_urls = set()
    
    # Prevent infinite loops - max 3 retries
    MAX_RETRIES = 3
    if retry_count >= MAX_RETRIES:
        raise HTTPException(
            status_code=400,
            detail=f"Unable to download Google Drive file after {MAX_RETRIES} attempts. The file may require manual confirmation or may not be publicly accessible. Please ensure the file is shared with 'Anyone with the link' permission."
        )
    
    # Check if we've already tried this exact URL
    if url in tried_urls:
        raise HTTPException(
            status_code=400,
            detail="Unable to download Google Drive file. The confirmation method is not working. Please try using a direct download link or ensure the file is publicly accessible."
        )
    
    tried_urls.add(url)
    try:
        # Validate URL format (skip if retry)
        if not is_retry:
            parsed_url = urlparse(url)
            if not parsed_url.scheme or not parsed_url.netloc:
                raise HTTPException(
                    status_code=400,
                    detail="Invalid URL format. Please provide a valid URL."
                )
        
        # Handle Google Drive links (only on first attempt or if file_id not provided)
        original_url = url
        if not file_id and "drive.google.com" in url.lower():
            logger.info("Detected Google Drive link, converting to direct download URL")
            # Convert Google Drive share link to direct download link
            file_id_match = re.search(r'/file/d/([a-zA-Z0-9_-]+)', url)
            if file_id_match:
                file_id = file_id_match.group(1)
                download_url = f"https://drive.google.com/uc?export=download&id={file_id}"
                url = download_url
            else:
                # Also try to extract from confirm URLs (retry case)
                file_id_match = re.search(r'[?&]id=([a-zA-Z0-9_-]+)', url)
                if file_id_match:
                    file_id = file_id_match.group(1)
                    # Already a download URL, use as is
                else:
                    raise HTTPException(
                        status_code=400,
                        detail="Invalid Google Drive URL. Please provide a shareable Google Drive link."
                    )
        
        # Handle Loom links
        elif "loom.com" in url.lower() or "loom.share" in url.lower():
            logger.info("Detected Loom link, attempting to extract video URL")
            # Loom videos can be accessed via their API or direct video URL
            # For public videos, we can try to get the video URL
            # This might require the loom.com/share format
            if "/share/" in url:
                # Extract the video ID from Loom URL
                loom_id_match = re.search(r'/share/([a-zA-Z0-9]+)', url)
                if loom_id_match:
                    loom_id = loom_id_match.group(1)
                    # Try to get the video URL (Loom might require different approach)
                    # For now, try the direct video URL format
                    url = f"https://cdn.loom.com/sessions/videos/{loom_id}/transcoded.mp4"
                    logger.info(f"Converted Loom URL to: {url}")
        
        # Determine file extension from filename hint or Content-Type header
        file_extension = None
        if filename_hint:
            file_extension = os.path.splitext(filename_hint)[1].lower()
        
        # Download the video with proper headers
        logger.info(f"Downloading video from URL: {url}")
        # Increase timeout for large files - allow up to 10 minutes for download
        max_size_mb = _get_settings().MAX_VIDEO_SIZE_MB
        # Calculate timeout based on file size limit (roughly 1 minute per 100MB with margin)
        timeout_seconds = max(300.0, (max_size_mb / 100) * 60)  # At least 5 minutes, more for larger limits
        timeout = httpx.Timeout(timeout_seconds, connect=30.0)
        
        async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
            # First, make a HEAD request to check content type and size
            try:
                head_response = await client.head(url)
                head_response.raise_for_status()
                
                # Check if it's a video content type
                content_type = head_response.headers.get("content-type", "").lower()
                content_length = head_response.headers.get("content-length")
                
                if content_length:
                    file_size_mb = int(content_length) / (1024 * 1024)
                    max_size_mb = _get_settings().MAX_VIDEO_SIZE_MB
                    if file_size_mb > max_size_mb:
                        raise HTTPException(
                            status_code=400,
                            detail=f"Video file size ({file_size_mb:.2f} MB) exceeds maximum allowed size ({max_size_mb} MB). Please use a smaller file or increase MAX_VIDEO_SIZE_MB in your configuration."
                        )
                    else:
                        logger.info(f"File size check passed: {file_size_mb:.2f} MB (limit: {max_size_mb} MB)")
                
                # Determine extension from Content-Type if not already set
                if not file_extension:
                    if "video/mp4" in content_type:
                        file_extension = ".mp4"
                    elif "video/webm" in content_type:
                        file_extension = ".webm"
                    elif "video/quicktime" in content_type or "video/mov" in content_type:
                        file_extension = ".mov"
                    elif "video/x-msvideo" in content_type:
                        file_extension = ".avi"
                    else:
                        # Default to mp4 if we can't determine
                        file_extension = ".mp4"
                        logger.warning(f"Could not determine file type from Content-Type: {content_type}, defaulting to .mp4")
                
            except httpx.HTTPStatusError as e:
                # HEAD might not be supported, continue with GET
                logger.warning(f"HEAD request failed, will try GET: {e}")
                file_extension = file_extension or ".mp4"
            
            # Now download the actual video
            async with client.stream("GET", url, follow_redirects=True) as response:
                response.raise_for_status()
                
                # Check Content-Type from GET response if HEAD failed
                content_type = response.headers.get("content-type", "").lower()
                
                # Special handling for Google Drive - check if we got HTML (confirmation page)
                if file_id and "text/html" in content_type:
                    logger.warning(f"Received HTML from Google Drive (confirmation page, attempt {retry_count + 1}/{MAX_RETRIES})")
                    max_size_mb = _get_settings().MAX_VIDEO_SIZE_MB  # Get size limit for error messages
                    
                    # Read more HTML content to get the full page
                    # Google Drive confirmation pages can be large, read more to find download links
                    html_chunk = b""
                    async for chunk in response.aiter_bytes(chunk_size=8192):
                        html_chunk += chunk
                        # Read up to 512KB to ensure we get the full page including any download links
                        if len(html_chunk) >= 524288:  # 512KB
                            break
                    
                    if html_chunk.startswith(b"<!DOCTYPE") or html_chunk.startswith(b"<html") or b"<html" in html_chunk[:1000].lower():
                        # Try to extract the download confirmation token from HTML
                        html_content = html_chunk.decode('utf-8', errors='ignore')
                        
                        logger.debug(f"HTML content preview: {html_content[:1000]}...")
                        
                        # Log if we found "Download anyway" text for debugging
                        if "download anyway" in html_content.lower():
                            logger.info("Found 'Download anyway' text in HTML - attempting to extract download link")
                        
                        # Also check for the virus scan warning specifically
                        if "can't scan this file for viruses" in html_content.lower() or "too large for google to scan" in html_content.lower():
                            logger.info("Detected Google Drive virus scan warning page")
                        
                        # Method 1: Look for the "Download anyway" button specifically
                        # This button appears when Google Drive can't scan large files
                        download_anyway_patterns = [
                            # Link with "Download anyway" text
                            r'<a[^>]*href="([^"]*uc\?export=download[^"]*)"[^>]*>.*?Download anyway.*?</a>',
                            r'<a[^>]*>.*?Download anyway.*?</a>[^>]*href="([^"]*uc\?export=download[^"]*)"',
                            r'Download anyway[^<]*<a[^>]*href="([^"]*uc\?export=download[^"]*)"',
                            # Button with onclick redirecting to download
                            r'<button[^>]*onclick="[^"]*window\.location\.href\s*=\s*[\'"]([^\'"]*uc\?export=download[^\'"]*)[\'"]',
                            r'<button[^>]*>.*?Download anyway.*?</button>.*?window\.location\.href\s*=\s*[\'"]([^\'"]*uc\?export=download[^\'"]*)[\'"]',
                            # Form action with download URL
                            r'<form[^>]*action="([^"]*uc\?export=download[^"]*)"[^>]*>.*?Download anyway.*?</form>',
                            r'Download anyway.*?<form[^>]*action="([^"]*uc\?export=download[^"]*)"',
                            # Generic JavaScript redirect patterns
                            r'window\.location\.href\s*=\s*[\'"]([^\'"]*uc\?export=download[^\'"]*)[\'"]',
                            r'location\.href\s*=\s*[\'"]([^\'"]*uc\?export=download[^\'"]*)[\'"]',
                        ]
                        
                        download_url_found = None
                        for pattern in download_anyway_patterns:
                            match = re.search(pattern, html_content, re.IGNORECASE | re.DOTALL)
                            if match:
                                download_url_found = match.group(1)
                                # Clean up the URL (remove escape sequences if any)
                                download_url_found = download_url_found.replace('\\x3d', '=').replace('\\/', '/')
                                if not download_url_found.startswith('http'):
                                    if download_url_found.startswith('/'):
                                        download_url_found = f"https://drive.google.com{download_url_found}"
                                    else:
                                        download_url_found = f"https://drive.google.com/{download_url_found}"
                                logger.info(f"Found 'Download anyway' button link: {download_url_found}")
                                break
                        
                        # Method 1b: Look for any download link in the confirmation page (if Download anyway not found)
                        if not download_url_found:
                            download_link_patterns = [
                                r'<a[^>]*href="([^"]*uc\?export=download[^"]*)"[^>]*>',
                                r'href="(/uc\?export=download[^"]+)"',
                                r'href="(https://drive\.google\.com/uc\?export=download[^"]+)"',
                                r'action="(/uc\?export=download[^"]+)"',
                                r'action="(https://drive\.google\.com/uc\?export=download[^"]+)"',
                            ]
                            
                            for pattern in download_link_patterns:
                                match = re.search(pattern, html_content, re.IGNORECASE)
                                if match:
                                    download_url_found = match.group(1)
                                    # Clean up the URL
                                    download_url_found = download_url_found.replace('\\x3d', '=').replace('\\/', '/')
                                    if not download_url_found.startswith('http'):
                                        if download_url_found.startswith('/'):
                                            download_url_found = f"https://drive.google.com{download_url_found}"
                                        else:
                                            download_url_found = f"https://drive.google.com/{download_url_found}"
                                    logger.info(f"Found download link in HTML: {download_url_found}")
                                    break
                        
                        # Method 2: Look for JavaScript variables containing download URLs
                        # Google Drive sometimes stores the download URL in JavaScript variables
                        js_url_patterns = [
                            r'var\s+url\s*=\s*["\']([^"\']*uc\?export=download[^"\']*)["\']',
                            r'const\s+url\s*=\s*["\']([^"\']*uc\?export=download[^"\']*)["\']',
                            r'href\s*[:=]\s*["\']([^"\']*uc\?export=download[^"\']*)["\']',
                            r'downloadUrl\s*[:=]\s*["\']([^"\']*uc\?export=download[^"\']*)["\']',
                            r'download_url\s*[:=]\s*["\']([^"\']*uc\?export=download[^"\']*)["\']',
                        ]
                        
                        for pattern in js_url_patterns:
                            match = re.search(pattern, html_content, re.IGNORECASE)
                            if match:
                                js_url = match.group(1)
                                # Clean up the URL
                                js_url = js_url.replace('\\x3d', '=').replace('\\/', '/')
                                if not js_url.startswith('http'):
                                    if js_url.startswith('/'):
                                        js_url = f"https://drive.google.com{js_url}"
                                    else:
                                        js_url = f"https://drive.google.com/{js_url}"
                                if not download_url_found:  # Only use if we didn't find a better one
                                    download_url_found = js_url
                                    logger.info(f"Found download URL in JavaScript: {download_url_found}")
                                break
                        
                        # Method 3: Extract all hidden input fields from the form (PRIORITY - this is the working format)
                        # Google Drive uses hidden inputs for confirm, uuid, at, etc.
                        # This method builds the working URL: https://drive.usercontent.google.com/download
                        hidden_inputs = {}
                        # More flexible pattern that handles different attribute orders and quoted/unquoted values
                        hidden_input_patterns = [
                            r'<input[^>]*type=["\']?hidden["\']?[^>]*name=["\']([^"\']+)["\'][^>]*value=["\']([^"\']+)["\']',
                            r'<input[^>]*name=["\']([^"\']+)["\'][^>]*type=["\']?hidden["\']?[^>]*value=["\']([^"\']+)["\']',
                            r'<input[^>]*type=["\']?hidden["\']?[^>]*name=([^\s>]+)[^>]*value=([^\s>]+)',
                        ]
                        
                        for pattern in hidden_input_patterns:
                            for match in re.finditer(pattern, html_content, re.IGNORECASE):
                                input_name = match.group(1).strip('\'"')
                                input_value = match.group(2).strip('\'"')
                                if input_name not in hidden_inputs:  # Don't overwrite existing values
                                    hidden_inputs[input_name] = input_value
                                    logger.debug(f"Found hidden input: {input_name} = {input_value}")
                        
                        if hidden_inputs:
                            logger.info(f"Extracted {len(hidden_inputs)} hidden input fields from form")
                        
                        # Extract specific important fields
                        confirm_token = hidden_inputs.get('confirm') or hidden_inputs.get('t')
                        uuid_value = hidden_inputs.get('uuid')
                        at_value = hidden_inputs.get('at')
                        authuser_value = hidden_inputs.get('authuser', '0')
                        export_value = hidden_inputs.get('export', '')
                        
                        # Also try alternative patterns for confirm token if not found in hidden inputs
                        if not confirm_token:
                            token_patterns = [
                                r'name="confirm"[^>]*value="([^"]+)"',
                                r'var\s+uc_download_token\s*=\s*["\']([^"\']+)["\']',
                                r'confirm=([a-zA-Z0-9_-]+)',
                                r'confirm\\x3d([a-zA-Z0-9_-]+)',
                                r'uc-download-link[^>]*href="[^"]*confirm=([a-zA-Z0-9_-]+)',
                                r't\.action\s*=\s*["\']([^"\']*uc\?export=download[^"\']*)["\']',
                            ]
                            
                            for pattern in token_patterns:
                                match = re.search(pattern, html_content, re.IGNORECASE)
                                if match:
                                    confirm_token = match.group(1)
                                    logger.info(f"Found confirmation token via pattern: {confirm_token}")
                                    break
                        
                        # PRIORITY: Build the working URL format FIRST: https://drive.usercontent.google.com/download
                        if file_id and confirm_token:
                            # Use the working URL format with all extracted parameters
                            download_params = {
                                'id': file_id,
                                'export': export_value,
                                'authuser': authuser_value,
                                'confirm': confirm_token
                            }
                            
                            if uuid_value:
                                download_params['uuid'] = uuid_value
                            if at_value:
                                download_params['at'] = at_value
                            
                            # Build URL with the working format
                            working_url = f"https://drive.usercontent.google.com/download?{urlencode(download_params)}"
                            logger.info(f"Built working download URL with hidden inputs: {working_url[:100]}...")
                            
                            if working_url not in tried_urls:
                                logger.info(f"Trying working URL format with extracted form values (PRIORITY)")
                                try:
                                    return await download_video_from_url(
                                        working_url, 
                                        output_path, 
                                        filename_hint, 
                                        file_id=file_id, 
                                        is_retry=True,
                                        retry_count=retry_count + 1,
                                        tried_urls=tried_urls
                                    )
                                except HTTPException:
                                    pass  # Try next method
                        
                        # Fallback: Try the found download URL (from Method 1)
                        if download_url_found and download_url_found not in tried_urls:
                            logger.info(f"Retrying with found download link: {download_url_found}")
                            try:
                                return await download_video_from_url(
                                    download_url_found, 
                                    output_path, 
                                    filename_hint, 
                                    file_id=file_id, 
                                    is_retry=True,
                                    retry_count=retry_count + 1,
                                    tried_urls=tried_urls
                                )
                            except HTTPException:
                                pass  # Try next method
                        
                        # Try with extracted confirmation token
                        if confirm_token and confirm_token not in ['t', 'yes']:  # Don't retry generic tokens
                            confirm_url = f"https://drive.google.com/uc?export=download&confirm={confirm_token}&id={file_id}"
                            if confirm_url not in tried_urls:
                                logger.info(f"Retrying with extracted token: {confirm_url}")
                                try:
                                    return await download_video_from_url(
                                        confirm_url, 
                                        output_path, 
                                        filename_hint, 
                                        file_id=file_id, 
                                        is_retry=True,
                                        retry_count=retry_count + 1,
                                        tried_urls=tried_urls
                                    )
                                except HTTPException:
                                    pass  # Try next method
                        
                        # If we've exhausted retries, raise error
                        if retry_count >= MAX_RETRIES - 1:
                            raise HTTPException(
                                status_code=400,
                                detail=f"Unable to download Google Drive file after {MAX_RETRIES} attempts. The file requires manual confirmation for virus scanning or may not be publicly accessible. Please ensure the file is shared with 'Anyone with the link' permission. Alternatively, try downloading the file manually and uploading it directly."
                            )
                        
                        # Last resort: Try generic confirm=t (but only once)
                        if retry_count == 0:
                            confirm_url = f"https://drive.google.com/uc?export=download&confirm=t&id={file_id}"
                            if confirm_url not in tried_urls:
                                logger.info(f"Trying generic confirm=t parameter: {confirm_url}")
                                try:
                                    return await download_video_from_url(
                                        confirm_url, 
                                        output_path, 
                                        filename_hint, 
                                        file_id=file_id, 
                                        is_retry=True,
                                        retry_count=retry_count + 1,
                                        tried_urls=tried_urls
                                    )
                                except HTTPException:
                                    pass
                        
                        # If all methods failed, raise error
                        raise HTTPException(
                            status_code=400,
                            detail=f"Unable to download Google Drive file. The file requires manual confirmation for virus scanning or may not be publicly accessible. Please ensure the file is shared with 'Anyone with the link' permission. Maximum file size: {max_size_mb} MB."
                        )
                
                # Determine file extension from Content-Type if not already set
                if not file_extension or file_extension == ".mp4":
                    if "video/mp4" in content_type:
                        file_extension = ".mp4"
                    elif "video/webm" in content_type:
                        file_extension = ".webm"
                    elif "video/quicktime" in content_type or "video/mov" in content_type:
                        file_extension = ".mov"
                    elif "video/x-msvideo" in content_type:
                        file_extension = ".avi"
                    elif "application/octet-stream" in content_type:
                        # Some servers don't send proper content-type, try to detect from filename or default
                        file_extension = file_extension or ".mp4"
                
                # Update output path with correct extension
                final_output_path = output_path
                if not output_path.endswith(file_extension):
                    final_output_path = os.path.splitext(output_path)[0] + file_extension
                
                # Download with progress tracking and validation
                total_size = 0
                max_size_mb = _get_settings().MAX_VIDEO_SIZE_MB
                max_size_bytes = max_size_mb * 1024 * 1024
                first_chunk_received = False
                first_bytes = b""
                
                with open(final_output_path, "wb") as f:
                    async for chunk in response.aiter_bytes(chunk_size=8192):
                        if not first_chunk_received:
                            first_bytes += chunk[:min(12, len(chunk))]  # Read first 12 bytes for magic number check
                            first_chunk_received = True
                        
                        total_size += len(chunk)
                        
                        # Check size during download
                        if total_size > max_size_bytes:
                            # Clean up partial download
                            try:
                                os.remove(final_output_path)
                            except:
                                pass
                            raise HTTPException(
                                status_code=400,
                                detail=f"Video file size exceeds maximum allowed size ({max_size_mb} MB)"
                            )
                        
                        f.write(chunk)
                
                file_size_mb = total_size / (1024 * 1024)
                logger.info(f"Video downloaded: {final_output_path} (Size: {file_size_mb:.2f} MB)")
                
                # Validate the downloaded file is actually a video file
                if not _is_valid_video_file(final_output_path, first_bytes):
                    try:
                        os.remove(final_output_path)
                    except:
                        pass
                    raise HTTPException(
                        status_code=400,
                        detail="The downloaded file is not a valid video file. The URL may have returned HTML or a corrupted file. Please verify the URL points directly to a video file."
                    )
                
                logger.info(f"Video file validated successfully: {final_output_path}")
                return final_output_path, file_size_mb
        
    except httpx.HTTPStatusError as e:
        status_code = e.response.status_code
        if status_code == 404:
            raise HTTPException(
                status_code=404,
                detail="Video not found at the provided URL. Please verify the URL is correct and accessible."
            )
        elif status_code == 403:
            raise HTTPException(
                status_code=403,
                detail="Access forbidden. The video may be private or require authentication. Please ensure the video is publicly accessible."
            )
        elif status_code == 401:
            raise HTTPException(
                status_code=401,
                detail="Authentication required. The video link may require login credentials."
            )
        else:
            raise HTTPException(
                status_code=400,
                detail=f"Failed to download video: HTTP {status_code} - {str(e)}"
            )
    except httpx.TimeoutException:
        raise HTTPException(
            status_code=408,
            detail="Request timeout. The video download took too long. Please check your connection and try again."
        )
    except httpx.NetworkError as e:
        raise HTTPException(
            status_code=503,
            detail=f"Network error while downloading video: {str(e)}. Please check your internet connection."
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error downloading video from URL: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to download video from URL: {str(e)}"
        )


def setup_routes(app: FastAPI):
    """Setup API routes"""
    
    @app.get("/", response_model=BaseResponse)
    async def root():
        """Root endpoint"""
        return BaseResponse(
            message="AI Service is running",
            timestamp=datetime.now()
        )
    
    @app.get("/health", response_model=HealthCheckResponse)
    async def health_check():
        """Health check endpoint"""
        return HealthCheckResponse(
            service="ai-service",
            status="healthy"
        )
    
    @app.post("/analyze-video", response_model=VideoAnalysisResponse)
    async def analyze_video(file: UploadFile = File(...)):
        """AI Interview Video Analyzer - accepts file upload"""
        start_time = time.time()
        temp_video_path = None
        
        try:
            # Validate file type
            logger.info(f"Validating file type: {file.filename}")
            allowed_extensions = {'.mp4', '.mov', '.avi', '.mkv', '.webm', '.flv', '.wmv', '.m4v'}
            file_extension = os.path.splitext(file.filename)[1].lower()
            
            if file_extension not in allowed_extensions:
                raise HTTPException(
                    status_code=400,
                    detail=f"Unsupported file format. Allowed formats: {', '.join(allowed_extensions)}"
                )
            
            # Check file size
            file_content = await file.read()
            file_size_mb = len(file_content) / (1024 * 1024)
            settings = _get_settings()
            max_size_mb = settings.MAX_VIDEO_SIZE_MB
            
            if file_size_mb > max_size_mb:
                raise HTTPException(
                    status_code=400,
                    detail=f"File size ({file_size_mb:.2f} MB) exceeds maximum allowed size ({max_size_mb} MB)"
                )
            
            # Check if Gemini API key is configured
            if not settings.GEMINI_API_KEY:
                raise HTTPException(
                    status_code=500,
                    detail="GEMINI_API_KEY is not configured. Please set it in your .env file."
                )
            
            # Save uploaded file temporarily
            temp_dir = tempfile.mkdtemp()
            logger.info(f"Created temporary directory: {temp_dir}")
            temp_video_path = os.path.join(temp_dir, f"uploaded_video{file_extension}")
            logger.info(f"Created temporary video path: {temp_video_path}")
            with open(temp_video_path, "wb") as buffer:
                buffer.write(file_content)
            
            # Initialize video analyzer
            analyzer = VideoAnalyzer(
                gemini_api_key=settings.GEMINI_API_KEY,
                whisper_model=settings.WHISPER_MODEL,
                use_alternative_transcription=getattr(settings, 'USE_ALTERNATIVE_TRANSCRIPTION', False),
                transcription_service=getattr(settings, 'TRANSCRIPTION_SERVICE', 'whisper'),
                transcription_api_key=getattr(settings, 'TRANSCRIPTION_API_KEY', None)
            )
            
            # Process video
            result = analyzer.process_video(temp_video_path)
            
            processing_time = time.time() - start_time
            logger.info(f"Video analysis completed in {processing_time:.2f} seconds")
            
            # Extract transcript if present (optional for response)
            transcript = result.pop("transcript", None)
            
            # Build response
            response = VideoAnalysisResponse(
                is_interview=result.get("is_interview", True),
                summary=result.get("summary", ""),
                key_questions=result.get("key_questions", []),
                tone_and_professionalism=result.get("tone_and_professionalism", ""),
                rating=float(result.get("rating", 0)),
                technical_strengths=result.get("technical_strengths", []),
                technical_weaknesses=result.get("technical_weaknesses", []),
                communication_rating=float(result.get("communication_rating", 0)),
                technical_knowledge_rating=float(result.get("technical_knowledge_rating", 0)),
                follow_up_questions=result.get("follow_up_questions", []),
                interviewer_review=result.get("interviewer_review", "Interviewer review not available"),
                transcript=transcript,
                processing_time=processing_time
            )
            
            return response
        
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error analyzing video: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail=f"Failed to analyze video: {str(e)}")
        
        finally:
            # Cleanup temporary file
            if temp_video_path and os.path.exists(temp_video_path):
                try:
                    os.remove(temp_video_path)
                    os.rmdir(os.path.dirname(temp_video_path))
                except Exception as e:
                    logger.warning(f"Failed to cleanup temp file: {e}")
    
    @app.post("/analyze-video-url", response_model=VideoAnalysisResponse)
    async def analyze_video_url(request: VideoUrlRequest):
        """AI Interview Video Analyzer from URL"""
        start_time = time.time()
        temp_video_path = None
        temp_dir = None
        
        try:
            # Validate URL
            if not request.video_url or not request.video_url.strip():
                raise HTTPException(
                    status_code=400,
                    detail="Video URL is required. Please provide a valid video URL."
                )
            
            url = request.video_url.strip()
            logger.info(f"Processing video URL: {url}")
            
            # Check if Gemini API key is configured
            settings = _get_settings()
            if not settings.GEMINI_API_KEY:
                raise HTTPException(
                    status_code=500,
                    detail="GEMINI_API_KEY is not configured. Please set it in your .env file."
                )
            
            # Create temporary directory for video download
            temp_dir = tempfile.mkdtemp()
            logger.info(f"Created temporary directory: {temp_dir}")
            temp_video_base_path = os.path.join(temp_dir, "downloaded_video")
            
            # Download video from URL
            try:
                temp_video_path, file_size_mb = await download_video_from_url(
                    url,
                    temp_video_base_path,
                    filename_hint=request.filename
                )
                logger.info(f"Video downloaded: {temp_video_path} (Size: {file_size_mb:.2f} MB)")
            except HTTPException:
                raise
            except Exception as e:
                logger.error(f"Error downloading video: {e}", exc_info=True)
                raise HTTPException(status_code=500, detail=f"Failed to download video from URL: {str(e)}")
            
            # Validate file extension after download
            file_extension = os.path.splitext(temp_video_path)[1].lower()
            allowed_extensions = {'.mp4', '.mov', '.avi', '.mkv', '.webm', '.flv', '.wmv', '.m4v'}
            
            if file_extension not in allowed_extensions:
                raise HTTPException(
                    status_code=400,
                    detail=f"Unsupported video format: {file_extension}. Allowed formats: {', '.join(allowed_extensions)}"
                )
            
            # Initialize video analyzer
            analyzer = VideoAnalyzer(
                gemini_api_key=settings.GEMINI_API_KEY,
                whisper_model=settings.WHISPER_MODEL,
                use_alternative_transcription=getattr(settings, 'USE_ALTERNATIVE_TRANSCRIPTION', False),
                transcription_service=getattr(settings, 'TRANSCRIPTION_SERVICE', 'whisper'),
                transcription_api_key=getattr(settings, 'TRANSCRIPTION_API_KEY', None)
            )
            
            # Process video
            logger.info("Starting video analysis pipeline...")
            try:
                result = analyzer.process_video(temp_video_path)
            except Exception as e:
                logger.error(f"Error processing video: {e}", exc_info=True)
                raise HTTPException(status_code=500, detail=f"Failed to process video: {str(e)}")
            
            processing_time = time.time() - start_time
            logger.info(f"Video analysis completed in {processing_time:.2f} seconds")
            
            # Extract transcript if present (optional for response)
            transcript = result.pop("transcript", None)
            
            # Build response
            response = VideoAnalysisResponse(
                is_interview=result.get("is_interview", True),
                summary=result.get("summary", ""),
                key_questions=result.get("key_questions", []),
                tone_and_professionalism=result.get("tone_and_professionalism", ""),
                rating=float(result.get("rating", 0)),
                technical_strengths=result.get("technical_strengths", []),
                technical_weaknesses=result.get("technical_weaknesses", []),
                communication_rating=float(result.get("communication_rating", 0)),
                technical_knowledge_rating=float(result.get("technical_knowledge_rating", 0)),
                follow_up_questions=result.get("follow_up_questions", []),
                interviewer_review=result.get("interviewer_review", "Interviewer review not available"),
                transcript=transcript,
                processing_time=processing_time
            )
            
            return response
        
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error analyzing video from URL: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail=f"Failed to analyze video from URL: {str(e)}")
        
        finally:
            # Cleanup temporary file and directory
            if temp_video_path and os.path.exists(temp_video_path):
                try:
                    os.remove(temp_video_path)
                except Exception as e:
                    logger.warning(f"Failed to remove temp video file: {e}")
            
            # Clean up temp directory
            if temp_dir and os.path.exists(temp_dir):
                try:
                    # Remove any remaining files in the directory
                    for file in os.listdir(temp_dir):
                        try:
                            os.remove(os.path.join(temp_dir, file))
                        except:
                            pass
                    os.rmdir(temp_dir)
                    logger.info("Temporary files cleaned up")
                except Exception as e:
                    logger.warning(f"Failed to cleanup temp directory: {e}")

