from fastapi import APIRouter, HTTPException, UploadFile, File
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from app.services.ai_service import AIService
import logging
import re

# ── Setup ────────────────────────────────────────────────────────────────────
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

router = APIRouter()
ai_service = AIService()


# ── Request/Response Models ──────────────────────────────────────────────────

class ChatRequest(BaseModel):
    message: str
    session_id: str = "default"


class ChatResponse(BaseModel):
    success: bool
    response: str


# ── Chat Endpoint (/api/v1/chat) ─────────────────────────────────────────────

@router.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """
    Text-based chat endpoint.
    Answers questions about Farhad Billah using the portfolio knowledge base.
    """
    logger.info(f"[/chat] message={request.message!r}")

    if not request.message.strip():
        raise HTTPException(status_code=400, detail="Message cannot be empty")

    result = await ai_service.generate_response(request.message)

    if result["success"]:
        return ChatResponse(success=True, response=result["response"])
    else:
        logger.error(f"[/chat] AI error: {result['error']}")
        # Surface a helpful error instead of a misleading "I apologize" message
        raise HTTPException(
            status_code=503,
            detail=f"AI service error: {result['error']}"
        )


# ── Voice Endpoint (/api/v1/voice) ───────────────────────────────────────────

@router.post("/voice")
async def process_voice(audio_file: UploadFile = File(...)):
    """
    Voice endpoint: audio → Groq Whisper STT → portfolio AI → text response.
    Returns transcript + AI response as JSON.
    """
    logger.info(f"[/voice] received file: {audio_file.filename}, type: {audio_file.content_type}")

    # Read uploaded audio
    audio_bytes = await audio_file.read()
    if not audio_bytes:
        raise HTTPException(status_code=400, detail="Empty audio file received")

    # Step 1: Speech-to-Text via Groq Whisper
    filename = audio_file.filename or "audio.webm"
    stt_result = await ai_service.transcribe_audio(audio_bytes, filename=filename)

    if not stt_result["success"]:
        logger.error(f"[/voice] STT failed: {stt_result['error']}")
        raise HTTPException(status_code=502, detail=f"Transcription failed: {stt_result['error']}")

    transcript = stt_result["transcript"]
    logger.info(f"[/voice] transcript: {transcript!r}")

    if not transcript.strip():
        return JSONResponse(content={
            "success": False,
            "transcript": "",
            "response": "I couldn't hear anything clearly. Could you please try again?"
        })

    # Step 2: Generate portfolio-aware AI response
    ai_result = await ai_service.generate_response(transcript)

    if not ai_result["success"]:
        logger.error(f"[/voice] AI error: {ai_result['error']}")
        raise HTTPException(status_code=503, detail=f"AI error: {ai_result['error']}")

    return JSONResponse(content={
        "success": True,
        "transcript": transcript,
        "response": ai_result["response"]
    })


# ── Info Endpoints ────────────────────────────────────────────────────────────

@router.get("/models")
async def get_models():
    """Get information about the active AI model configuration."""
    return {
        "current_model": ai_service.last_model_used,
        "groq_model": ai_service.groq_model,
        "groq_api_configured": bool(ai_service.groq_api_key),
        "whisper_model": "whisper-large-v3",
        "knowledge_base_loaded": bool(ai_service.groq_api_key),
    }


@router.get("/health")
async def health():
    """Health check endpoint."""
    return {"status": "ok", "service": "Farhad Billah Personal Chatbot"}