# Copilot Instructions for AI Agents

## Project Overview
This is a Flask-based web application for video processing. It enables users to upload videos, extract audio, generate automatic subtitles (using Faster Whisper), summarize spoken content, synthesize summaries to audio, translate both subtitles and summaries, and download results in various formats.

## Key Components
- `app/server.py`: Flask app entry point. Handles routing, file uploads, and orchestrates the pipeline.
- `app/pipeline.py`: Core logic for audio extraction, transcription, summarization, translation, and TTS. Integrates Faster Whisper, FFmpeg, gTTS, pyttsx3, and Googletrans.
- `app/templates/`: Jinja2 HTML templates for UI (`home.html`, `upload.html`, `workspace.html`).
- `app/static/`: CSS and static media assets.
- `data/`: Stores user-generated files: videos, audio, subtitles, summaries, and state JSONs.

## Data Flow
1. User uploads a video via the web UI.
2. Audio is extracted and saved to `data/audio/`.
3. Transcription and subtitle generation (SRT/VTT) via Faster Whisper.
4. Summarization and translation (Googletrans).
5. TTS audio for summaries (gTTS/pyttsx3).
6. All outputs are saved in `data/outputs/` and `data/audio/`.

## Developer Workflows
- **Run locally:**
  ```powershell
  python -m venv venv; venv\Scripts\activate; pip install -r requirements.txt; python app/server.py
  ```
- **Dependencies:** All Python dependencies are in `requirements.txt`.
- **No explicit test suite**: Manual testing via the web UI is expected.
- **Debugging:** Use print/log statements in `server.py` and `pipeline.py`.

## Project Conventions
- All user uploads and outputs are stored under `data/` with unique IDs in filenames.
- Subtitles: `.srt` (base) and `.vtt` (translated) formats.
- Summaries: `.txt` (text) and `.mp3` (audio) formats.
- State tracking: JSON files in `data/temp/`.
- Minimal frontend logic; most logic is in Python backend.

## Integration Points
- **Faster Whisper**: For transcription. Invoked in `pipeline.py`.
- **FFmpeg**: For audio extraction. Called via subprocess in `pipeline.py`.
- **gTTS/pyttsx3**: For TTS. Used in `pipeline.py`.
- **Googletrans**: For translation. Used in `pipeline.py`.

## Examples
- To add a new output format, extend `pipeline.py` and update `server.py` routes.
- To add a new language, update translation/TTS logic in `pipeline.py` and UI dropdowns in `workspace.html`.

---
If any conventions or workflows are unclear, please ask for clarification or examples from the codebase.