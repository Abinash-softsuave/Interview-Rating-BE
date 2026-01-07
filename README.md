# AI Video Analyzer Service

An AI-powered service built with Python and FastAPI for video analysis, transcription, and interview evaluation. The service can analyze video files or videos from URLs (Google Drive, Loom, etc.) to extract transcripts and provide detailed interview analysis using Google Gemini AI.

## Project Structure

```
Pyhton_AI_Project/
├── app/
│   ├── controller/          # API route handlers
│   │   └── main_controller.py
│   ├── db/                  # Database configuration
│   │   └── database.py
│   ├── models/              # Database models
│   │   └── models.py
│   └── services/            # Business logic
│       └── main_service.py  # Video analyzer and AI models
├── logs/                    # Application logs
├── main.py                  # Application entry point
├── schemas.py               # Pydantic request/response models
├── requirements.txt         # Python dependencies
└── .env                     # Environment variables (create this)
```

## Features

- 🎥 Video upload and analysis from files or URLs
- 🔊 Audio extraction using FFmpeg
- 📝 Speech transcription using OpenAI Whisper
- 🤖 AI-powered interview analysis using Google Gemini
- 🔗 Support for Google Drive and Loom video links
- 📊 Detailed analysis including ratings, strengths, weaknesses, and follow-up questions

## Prerequisites

### 1. Python 3.10 - 3.13

**Windows:**

- Download from [python.org](https://www.python.org/downloads/)
- Or use: `choco install python` (if Chocolatey is installed)

**macOS:**

```bash
brew install python@3.13
```

**Linux (Ubuntu/Debian):**

```bash
sudo apt update
sudo apt install python3.13 python3.13-venv
```

### 2. FFmpeg

FFmpeg is required for audio extraction from video files.

**Windows:**

- Download from https://ffmpeg.org/download.html
- Extract and add to PATH
- Or use: `choco install ffmpeg` (if Chocolatey is installed)

**macOS:**

```bash
brew install ffmpeg
```

**Linux (Ubuntu/Debian):**

```bash
sudo apt update
sudo apt install ffmpeg
```

**Verify Installation:**

```bash
ffmpeg -version
```

### 3. Google Gemini API Key

1. Go to [Google AI Studio](https://makersuite.google.com/app/apikey)
2. Sign in with your Google account
3. Click "Create API Key"
4. Copy the API key

## Installation

### 1. Clone the Repository

```bash
git clone <repository-url>
cd Pyhton_AI_Project
```

### 2. Create Virtual Environment

**Windows:**

```bash
python -m venv venv
venv\Scripts\activate
```

**Linux/Mac:**

```bash
python3 -m venv venv
source venv/bin/activate
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

**Note:** Whisper (local transcription) pulls large model files on first use. On serverless platforms like Vercel, prefer the API-based transcription options below to keep build size small.

### 4. Configure Environment Variables

Create a `.env` file in the project root:

```env
# Google Gemini API Key (Required)
GEMINI_API_KEY=your_gemini_api_key_here

# Whisper Model (tiny, base, small, medium, large) - only if you install Whisper locally
WHISPER_MODEL=base

# Maximum video file size in MB
MAX_VIDEO_SIZE_MB=500

# Service Configuration
SERVICE_NAME=ai-service
DEBUG=True
LOG_LEVEL=INFO

# Alternative Transcription (Recommended for serverless)
USE_ALTERNATIVE_TRANSCRIPTION=True
TRANSCRIPTION_SERVICE=assemblyai
TRANSCRIPTION_API_KEY=your_assemblyai_api_key
```

## Running the Service

### Start the Service

```bash
python main.py
```

Or using uvicorn directly:

```bash
uvicorn main:app --reload --port 8001
```

The service will be available at:

- API: http://localhost:8001
- Documentation: http://localhost:8001/docs
- Health Check: http://localhost:8001/health

## API Endpoints

### Root

- **GET** `/` - Service status

### Health Check

- **GET** `/health` - Service health status

### Video Analysis

#### Upload Video File

- **POST** `/analyze-video`
- **Content-Type**: `multipart/form-data`
- **Body**: Video file (file field named `file`)
- **Supported formats**: mp4, mov, avi, mkv, webm, flv, wmv, m4v

#### Analyze Video from URL

- **POST** `/analyze-video-url`
- **Content-Type**: `application/json`
- **Body**:

```json
{
  "video_url": "https://drive.google.com/file/d/.../view",
  "filename": "optional_filename.mp4"
}
```

- **Supported URL types**:
  - Google Drive share links
  - Loom video links
  - Direct video URLs

### Response Format

```json
{
  "is_interview": true,
  "summary": "Concise summary of the discussion",
  "key_questions": ["Question 1", "Question 2"],
  "tone_and_professionalism": "Description of tone",
  "rating": 8.5,
  "technical_strengths": ["Strength 1", "Strength 2"],
  "technical_weaknesses": ["Weakness 1"],
  "communication_rating": 8.0,
  "technical_knowledge_rating": 9.0,
  "follow_up_questions": ["Question 1", "Question 2"],
  "transcript": "Full transcript text...",
  "processing_time": 45.2
}
```

## Usage Examples

### Using cURL

**File Upload:**

```bash
curl -X POST "http://localhost:8001/analyze-video" \
  -H "accept: application/json" \
  -H "Content-Type: multipart/form-data" \
  -F "file=@/path/to/your/video.mp4"
```

**URL Analysis:**

```bash
curl -X POST "http://localhost:8001/analyze-video-url" \
  -H "Content-Type: application/json" \
  -d '{"video_url": "https://drive.google.com/file/d/..."}'
```

### Using Python

```python
import requests

# File upload
url = "http://localhost:8001/analyze-video"
with open("interview_video.mp4", "rb") as f:
    files = {"file": f}
    response = requests.post(url, files=files)
    print(response.json())

# URL analysis
url = "http://localhost:8001/analyze-video-url"
data = {
    "video_url": "https://drive.google.com/file/d/.../view"
}
response = requests.post(url, json=data)
print(response.json())
```

### Using Interactive Docs

1. Start the service: `python main.py`
2. Open browser: http://localhost:8001/docs
3. Find the endpoint you want to use
4. Click "Try it out"
5. Upload a file or provide a URL
6. Click "Execute"

## How It Works

1. **Video Input**: Accepts video file or URL
2. **Video Download**: If URL provided, downloads video (supports Google Drive, Loom)
3. **File Validation**: Checks file format and size
4. **Audio Extraction**: Uses FFmpeg to extract audio as WAV (16kHz, mono)
5. **Transcription**: Uses OpenAI Whisper model to transcribe audio
6. **Analysis**: Sends transcript to Google Gemini API for detailed analysis
7. **Response**: Returns structured JSON with analysis results
8. **Cleanup**: Automatically deletes temporary files

## Model Selection Guide

| Model  | Size    | Speed   | Accuracy  | Use Case                 |
| ------ | ------- | ------- | --------- | ------------------------ |
| tiny   | 39 MB   | Fastest | Basic     | Quick tests, development |
| base   | 74 MB   | Fast    | Good      | **Recommended default**  |
| small  | 244 MB  | Medium  | Better    | Production (balanced)    |
| medium | 769 MB  | Slow    | Very Good | High accuracy needed     |
| large  | 1550 MB | Slowest | Best      | Maximum accuracy         |

## Alternative Transcription Services (serverless-friendly default)

For Vercel and other serverless platforms, use API-based transcription to avoid large local models:

1. Set `USE_ALTERNATIVE_TRANSCRIPTION=True` in `.env`
2. Choose a service: `TRANSCRIPTION_SERVICE=assemblyai` (recommended) or `google`
3. Set the API key: `TRANSCRIPTION_API_KEY=your_api_key`
4. Do **not** install `openai-whisper` unless you need local transcription on a VM

## Performance Notes

- First transcription will be slower (model download)
- Larger Whisper models are more accurate but slower
- Processing time depends on video length and model size
- For production, consider caching Whisper models

## Troubleshooting

### FFmpeg not found

- Ensure FFmpeg is installed and in PATH
- Restart terminal after installing FFmpeg

### Whisper model download fails

- Check internet connection
- Try a smaller model (tiny or base)
- Manually download from: https://github.com/openai/whisper#available-models-and-languages

### Gemini API errors

- Verify API key is correct in `.env` file
- Check API quota/limits
- Ensure API is enabled in Google Cloud Console

### Out of memory errors

- Use smaller Whisper model (tiny or base)
- Process shorter videos
- Increase system RAM

### Google Drive download issues

- Ensure the file is shared with "Anyone with the link" permission
- Some large files require manual confirmation for virus scanning
- Try using a direct download link instead

## Security Notes

- Videos are stored temporarily and deleted after processing
- Never commit API keys to version control
- Use environment variables for sensitive configuration
- Consider adding authentication for production use
- Validate and sanitize all user inputs

## Development

### Project Structure

- `app/controller/` - API route handlers
- `app/db/` - Database configuration and settings
- `app/models/` - Database models (if needed)
- `app/services/` - Business logic (video analyzer, AI models)
- `schemas.py` - Pydantic request/response models
- `main.py` - Application entry point

### Adding New Features

1. Add business logic in `app/services/main_service.py`
2. Add route handlers in `app/controller/main_controller.py`
3. Add request/response models in `schemas.py`
4. Update `main.py` if needed

## License

[Your License Here]

## Contributing

[Your Contributing Guidelines Here]
