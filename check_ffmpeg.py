"""
FFmpeg Installation Checker
Checks if ffmpeg is installed and accessible from Python
"""
import subprocess
import sys
import os


def check_ffmpeg():
    """Check if ffmpeg is installed and accessible"""
    print("[*] Checking FFmpeg installation...\n")
    
    try:
        # Try to run ffmpeg -version
        result = subprocess.run(
            ["ffmpeg", "-version"],
            capture_output=True,
            text=True,
            check=True,
            timeout=5
        )
        
        # Extract version info
        version_line = result.stdout.split('\n')[0]
        print("[+] FFmpeg is installed and working!")
        print(f"   {version_line}\n")
        
        # Check common installation paths
        common_paths = [
            r"C:\ffmpeg\bin\ffmpeg.exe",
            r"C:\Program Files\ffmpeg\bin\ffmpeg.exe",
            r"C:\tools\ffmpeg\bin\ffmpeg.exe",
        ]
        
        found_path = None
        for path in common_paths:
            if os.path.exists(path):
                found_path = path
                print(f"[*] Found at: {found_path}")
                break
        
        if not found_path:
            # Check PATH
            path_dirs = os.environ.get("PATH", "").split(os.pathsep)
            for path_dir in path_dirs:
                ffmpeg_path = os.path.join(path_dir, "ffmpeg.exe")
                if os.path.exists(ffmpeg_path):
                    print(f"[*] Found at: {ffmpeg_path}")
                    break
        
        return True
        
    except FileNotFoundError:
        print("[-] FFmpeg is NOT installed or not in PATH")
        print("\n[*] Installation Options:\n")
        
        print("Option 1: Using winget (Recommended)")
        print("   Run in PowerShell (as Admin):")
        print("   winget install FFmpeg\n")
        
        print("Option 2: Using Chocolatey")
        print("   Run in PowerShell (as Admin):")
        print("   choco install ffmpeg\n")
        
        print("Option 3: Manual Installation")
        print("   1. Download from: https://www.gyan.dev/ffmpeg/builds/")
        print("   2. Extract to C:\\ffmpeg")
        print("   3. Add C:\\ffmpeg\\bin to PATH")
        print("   4. Restart terminal\n")
        
        print("[*] Full guide: See INSTALL_FFMPEG_WINDOWS.md")
        return False
        
    except subprocess.TimeoutExpired:
        print("[!] FFmpeg check timed out")
        return False
        
    except subprocess.CalledProcessError as e:
        print(f"[-] FFmpeg error: {e.stderr}")
        return False
        
    except Exception as e:
        print(f"[-] Unexpected error: {e}")
        return False


def check_python_path():
    """Check if ffmpeg can be found from Python PATH"""
    print("\n[*] Checking Python PATH...")
    python_path = os.environ.get("PATH", "")
    path_dirs = python_path.split(os.pathsep)
    
    ffmpeg_found = False
    for path_dir in path_dirs:
        if "ffmpeg" in path_dir.lower():
            print(f"   [+] Found in PATH: {path_dir}")
            ffmpeg_found = True
            
    if not ffmpeg_found:
        print("   [!] FFmpeg directory not found in PATH")
        print("   [*] You may need to restart your terminal/IDE after installation")


if __name__ == "__main__":
    print("=" * 60)
    print("FFmpeg Installation Checker")
    print("=" * 60)
    print()
    
    is_installed = check_ffmpeg()
    check_python_path()
    
    print("\n" + "=" * 60)
    if is_installed:
        print("[+] Status: Ready to use video analyzer!")
    else:
        print("[-] Status: Please install FFmpeg first")
    print("=" * 60)

