"""
POST /api/voice/transcribe — Voice transcription using Whisper API.
"""

from fastapi import APIRouter, UploadFile, File

from router import transcribe_audio

router = APIRouter()


@router.post("/voice/transcribe")
async def voice_transcribe(audio: UploadFile = File(...)):
    """Transcribe uploaded audio using OpenAI Whisper."""
    audio_bytes = await audio.read()
    text = transcribe_audio(audio_bytes)
    return {"text": text}
