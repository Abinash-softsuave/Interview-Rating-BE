"""
Main Service - Video Analyzer and AI Models
"""
import os
import json
import tempfile
import subprocess
from pathlib import Path
from typing import Dict, Any, Optional
from loguru import logger

# Try to import dependencies with helpful error messages
try:
    import google.generativeai as genai
except ImportError:
    raise ImportError(
        "google-generativeai is not installed. "
        "Install it with: pip install google-generativeai"
    )

# Whisper - Optional with fallback
try:
    import whisper
    WHISPER_AVAILABLE = True
except ImportError:
    WHISPER_AVAILABLE = False
    logger.warning(
        "openai-whisper is not available. "
        "Local transcription will be disabled. "
        "Install with: pip install openai-whisper (requires Python 3.10-3.13)"
    )

# AI Models imports
from typing import Dict, Any


# ==================== Alternative Transcription Services ====================
class TranscriptionService:
    """Base class for transcription services"""
    
    def transcribe(self, audio_path: str) -> str:
        """Transcribe audio file"""
        raise NotImplementedError


class GoogleSpeechToText(TranscriptionService):
    """Google Speech-to-Text API"""
    
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key
        try:
            from google.cloud import speech_v1
            self.client = speech_v1.SpeechClient()
        except ImportError:
            raise ImportError(
                "google-cloud-speech is not installed. "
                "Install with: pip install google-cloud-speech"
            )
    
    def transcribe(self, audio_path: str) -> str:
        """Transcribe using Google Speech-to-Text"""
        import io
        from google.cloud import speech_v1
        
        with io.open(audio_path, "rb") as audio_file:
            content = audio_file.read()
        
        audio = speech_v1.RecognitionAudio(content=content)
        config = speech_v1.RecognitionConfig(
            encoding=speech_v1.RecognitionConfig.AudioEncoding.LINEAR16,
            sample_rate_hertz=16000,
            language_code="en-US",
        )
        
        response = self.client.recognize(config=config, audio=audio)
        
        transcript = ""
        for result in response.results:
            transcript += result.alternatives[0].transcript + " "
        
        return transcript.strip()


class AssemblyAITranscription(TranscriptionService):
    """AssemblyAI Transcription API"""
    
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv("ASSEMBLYAI_API_KEY")
        if not self.api_key:
            raise ValueError("ASSEMBLYAI_API_KEY is required")
        
        try:
            import assemblyai as aai
            aai.settings.api_key = self.api_key
            self.transcriber = aai.Transcriber()
        except ImportError:
            raise ImportError(
                "assemblyai is not installed. "
                "Install with: pip install assemblyai"
            )
    
    def transcribe(self, audio_path: str) -> str:
        """Transcribe using AssemblyAI"""
        import assemblyai as aai
        
        transcript = self.transcriber.transcribe(audio_path)
        if transcript.error:
            raise Exception(f"Transcription error: {transcript.error}")
        
        return transcript.text


def get_transcription_service(service_name: str, api_key: Optional[str] = None):
    """
    Get transcription service instance
    
    Args:
        service_name: Name of service (google, assemblyai)
        api_key: API key for the service
    
    Returns:
        TranscriptionService instance
    """
    if service_name.lower() == "google":
        return GoogleSpeechToText(api_key)
    elif service_name.lower() == "assemblyai":
        return AssemblyAITranscription(api_key)
    else:
        raise ValueError(f"Unknown transcription service: {service_name}")


# ==================== AI Models ====================
class AIModel:
    """Base class for AI models"""
    def __init__(self, model_name: str):
        self.model_name = model_name
        self.model = None
        self.loaded = False
    
    def load_model(self):
        """Load the AI model"""
        logger.info(f"Model {self.model_name} loaded")
        self.loaded = True
    
    def predict(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """Perform prediction/inference"""
        if not self.loaded:
            self.load_model()
        
        # Placeholder return
        return {
            "prediction": "Placeholder prediction",
            "confidence": 0.95,
            "input_processed": input_data
        }


class ModelRegistry:
    """Registry to manage multiple AI models"""
    def __init__(self):
        self.models: Dict[str, AIModel] = {}
    
    def register_model(self, model_name: str, model: AIModel):
        """Register a model"""
        self.models[model_name] = model
        logger.info(f"Registered model: {model_name}")
    
    def get_model(self, model_name: str) -> Optional[AIModel]:
        """Get a registered model"""
        if model_name not in self.models:
            logger.warning(f"Model {model_name} not found, using default")
            return self.models.get("default")
        return self.models[model_name]
    
    def list_models(self) -> list:
        """List all registered models"""
        return list(self.models.keys())


# Global model registry
model_registry = ModelRegistry()


def initialize_models():
    """Initialize all models"""
    # Register default model
    default_model = AIModel("default")
    model_registry.register_model("default", default_model)
    logger.info("Models initialized")


def get_model(model_name: str = "default") -> AIModel:
    """Get a model from the registry"""
    return model_registry.get_model(model_name)


# ==================== Video Analyzer ====================
class VideoAnalyzer:
    """Handles video analysis workflow"""
    
    def __init__(
        self, 
        gemini_api_key: str, 
        whisper_model: str = "base",
        use_alternative_transcription: bool = False,
        transcription_service: str = "whisper",
        transcription_api_key: Optional[str] = None
    ):
        """
        Initialize the video analyzer
        
        Args:
            gemini_api_key: Google Gemini API key
            whisper_model: Whisper model size (tiny, base, small, medium, large)
            use_alternative_transcription: Use API-based transcription instead of Whisper
            transcription_service: Service to use (whisper, google, assemblyai)
            transcription_api_key: API key for alternative transcription service
        """
        self.gemini_api_key = gemini_api_key
        self.whisper_model_name = whisper_model
        self.whisper_model = None
        self.use_alternative_transcription = use_alternative_transcription
        self.transcription_service_name = transcription_service
        self.transcription_api_key = transcription_api_key
        self.alternative_transcriber = None
        
        genai.configure(api_key=gemini_api_key)
        
        # Initialize alternative transcription if needed
        if use_alternative_transcription:
            try:
                self.alternative_transcriber = get_transcription_service(
                    transcription_service, 
                    transcription_api_key
                )
                logger.info(f"Alternative transcription service '{transcription_service}' initialized")
            except Exception as e:
                logger.warning(f"Failed to initialize alternative transcription: {e}")
    
    def load_whisper_model(self):
        """Load Whisper model (lazy loading)"""
        if not WHISPER_AVAILABLE:
            raise Exception(
                "Whisper is not available. "
                "Please install openai-whisper (requires Python 3.10-3.13) "
                "or use an alternative transcription method."
            )
        
        if self.whisper_model is None:
            logger.info(f"Loading Whisper model: {self.whisper_model_name}")
            try:
                self.whisper_model = whisper.load_model(self.whisper_model_name)
                logger.info("Whisper model loaded successfully")
            except Exception as e:
                logger.error(f"Failed to load Whisper model: {e}")
                raise
    
    def extract_audio(self, video_path: str, output_audio_path: str) -> str:
        """Extract audio from video file using ffmpeg"""
        try:
            logger.info(f"Extracting audio from video: {video_path}")
            
            # Check if ffmpeg is available
            try:
                subprocess.run(
                    ["ffmpeg", "-version"],
                    capture_output=True,
                    check=True
                )
            except (subprocess.CalledProcessError, FileNotFoundError):
                raise Exception("ffmpeg is not installed. Please install ffmpeg first.")
            
            # Extract audio using ffmpeg
            cmd = [
                "ffmpeg",
                "-i", video_path,
                "-vn",  # No video
                "-acodec", "pcm_s16le",  # PCM 16-bit little-endian
                "-ar", "16000",  # 16kHz sample rate (optimal for Whisper)
                "-ac", "1",  # Mono channel
                "-y",  # Overwrite output file
                output_audio_path
            ]
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=True
            )
            
            logger.info(f"Audio extracted successfully to: {output_audio_path}")
            return output_audio_path
        
        except subprocess.CalledProcessError as e:
            logger.error(f"FFmpeg error: {e.stderr}")
            raise Exception(f"Failed to extract audio: {e.stderr}")
        except Exception as e:
            logger.error(f"Error extracting audio: {e}")
            raise
    
    def transcribe_audio(self, audio_path: str) -> str:
        """Transcribe audio using Whisper model or alternative method"""
        try:
            logger.info(f"Transcribing audio: {audio_path}")
            
            # Use alternative transcription if configured
            if self.use_alternative_transcription and self.alternative_transcriber:
                logger.info(f"Using {self.transcription_service_name} for transcription")
                transcript = self.alternative_transcriber.transcribe(audio_path)
                logger.info(f"Transcription completed using {self.transcription_service_name}. Length: {len(transcript)} characters")
                return transcript
            
            # Try Whisper
            if WHISPER_AVAILABLE:
                self.load_whisper_model()
                result = self.whisper_model.transcribe(audio_path)
                transcript = result["text"].strip()
                logger.info(f"Transcription completed using Whisper. Length: {len(transcript)} characters")
                return transcript
            else:
                # No transcription available
                error_msg = (
                    "No transcription service available. "
                    "Options:\n"
                    "1. Install openai-whisper (requires Python 3.10-3.13): pip install openai-whisper\n"
                    "2. Configure alternative transcription service in settings"
                )
                logger.error(error_msg)
                raise Exception(error_msg)
        
        except Exception as e:
            logger.error(f"Error transcribing audio: {e}")
            raise
    
    def analyze_with_gemini(self, transcript: str) -> Dict[str, Any]:
        """Analyze transcript using Google Gemini API"""
        try:
            logger.info("Sending transcript to Gemini for analysis")
            
            # List available models and find one that supports generateContent
            available_models = []
            preferred_models = ['gemini-1.5-flash-latest', 'gemini-2.0-flash-exp', 'gemini-1.5-pro', 'gemini-pro']
            
            try:
                logger.info("Listing available Gemini models...")
                for model in genai.list_models():
                    if 'generateContent' in model.supported_generation_methods:
                        model_name = model.name.replace('models/', '')
                        available_models.append(model_name)
                        logger.info(f"Found available model: {model_name}")
            except Exception as e:
                logger.warning(f"Could not list models: {e}. Will try predefined models.")
            
            # Build list of models to try (preferred models first, then any available)
            model_names = []
            
            # Add preferred models that are available
            for preferred in preferred_models:
                if available_models and preferred in available_models:
                    model_names.append(preferred)
                elif not available_models:  # If we couldn't list, try anyway
                    model_names.append(preferred)
            
            # Add other available models that weren't in preferred list
            if available_models:
                for model in available_models:
                    if model not in model_names:
                        model_names.append(model)
            
            # Fallback if no models found
            if not model_names:
                model_names = preferred_models + ['gemini-1.5-flash']
            
            logger.info(f"Will try models in order: {model_names}")
            
            # Create analysis prompt
            prompt = f"""Analyze the following interview transcript and provide a detailed analysis in JSON format.

Transcript:
{transcript}

Please provide your analysis in the following JSON structure:
{{
    "is_interview": true/false,
    "summary": "Concise summary of the discussion",
    "key_questions": ["Question 1", "Question 2", ...],
    "tone_and_professionalism": "Description of tone and professionalism",
    "rating": 0-10,
    "technical_strengths": ["Strength 1", "Strength 2", ...],
    "technical_weaknesses": ["Weakness 1", "Weakness 2", ...],
    "communication_rating": 0-10,
    "technical_knowledge_rating": 0-10,
    "follow_up_questions": ["Question 1", "Question 2", ...],
    "interviewer_review": "Review and evaluation of the INTERVIEWER's performance: Assess how well the interviewer conducted the interview. Evaluate the quality of questions asked, questioning techniques (open-ended vs closed, leading questions, clarity), interviewer's communication style, ability to probe deeper, active listening skills, professionalism, whether they covered all necessary topics, fairness in their approach, and overall interviewing effectiveness. This should focus on the interviewer's skills and conduct, NOT the candidate's performance."
}}

Focus on:
- React.js, Node.js, and general software engineering knowledge
- Technical communication skills
- Problem-solving approach
- Code quality discussions
- System design understanding

Return only valid JSON, no additional text or markdown formatting."""

            # Try to generate analysis - if model fails, try next one
            response = None
            last_error = None
            
            for model_name in model_names:
                try:
                    logger.info(f"Attempting to generate content with model: {model_name}")
                    model = genai.GenerativeModel(model_name)
                    response = model.generate_content(prompt)
                    logger.info(f"Successfully generated content with model: {model_name}")
                    break
                except Exception as e:
                    error_str = str(e).lower()
                    last_error = e
                    # Check if it's a model not found error
                    if "not found" in error_str or "404" in error_str or "is not found" in error_str:
                        logger.warning(f"Model {model_name} not found (404), trying next model...")
                        continue
                    else:
                        # Different error, might be API key or other issue
                        logger.error(f"Error with model {model_name}: {e}")
                        if model_name == model_names[-1]:  # Last model, re-raise
                            raise
                        continue
            
            if response is None:
                available_info = f"Available models: {', '.join(available_models)}" if available_models else "Could not list available models"
                raise Exception(
                    f"Failed to generate content with any available Gemini model. "
                    f"{available_info}. "
                    f"Tried models: {', '.join(model_names)}. "
                    f"Last error: {last_error}. "
                    f"Please check your API key and verify model availability."
                )
            
            # Parse response
            response_text = response.text.strip()
            
            # Remove markdown code blocks if present
            if response_text.startswith("```json"):
                response_text = response_text[7:]
            if response_text.startswith("```"):
                response_text = response_text[3:]
            if response_text.endswith("```"):
                response_text = response_text[:-3]
            response_text = response_text.strip()
            
            # Try to parse JSON
            analysis = json.loads(response_text)
            
            logger.info("Gemini analysis completed successfully")
            return analysis
        
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse Gemini response as JSON: {e}")
            logger.error(f"Response: {response_text[:500]}")
            # Return a fallback response
            return {
                "is_interview": True,
                "summary": "Analysis completed but response parsing failed",
                "key_questions": [],
                "tone_and_professionalism": "Unable to determine",
                "rating": 5.0,
                "technical_strengths": [],
                "technical_weaknesses": [],
                "communication_rating": 5.0,
                "technical_knowledge_rating": 5.0,
                "follow_up_questions": [],
                "interviewer_review": "Unable to generate interviewer performance review due to response parsing error"
            }
        except Exception as e:
            logger.error(f"Error analyzing with Gemini: {e}")
            raise
    
    def process_video(self, video_file_path: str) -> Dict[str, Any]:
        """
        Complete video processing pipeline:
        1. Extract audio
        2. Transcribe audio
        3. Analyze with Gemini
        
        Args:
            video_file_path: Path to uploaded video file
        
        Returns:
            Complete analysis results
        """
        temp_audio_path = None
        
        try:
            # Create temporary directory for audio
            temp_dir = tempfile.mkdtemp()
            temp_audio_path = os.path.join(temp_dir, "extracted_audio.wav")
            
            # Step 1: Extract audio
            self.extract_audio(video_file_path, temp_audio_path)
            
            # Step 2: Transcribe
            transcript = self.transcribe_audio(temp_audio_path)
            
            # Step 3: Analyze with Gemini
            analysis = self.analyze_with_gemini(transcript)
            
            # Combine results
            result = {
                "transcript": transcript,
                **analysis
            }
            
            return result
        
        finally:
            # Cleanup temporary files
            if temp_audio_path and os.path.exists(temp_audio_path):
                try:
                    os.remove(temp_audio_path)
                    os.rmdir(os.path.dirname(temp_audio_path))
                except Exception as e:
                    logger.warning(f"Failed to cleanup temp files: {e}")

