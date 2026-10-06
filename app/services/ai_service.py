import os
import re
import logging
from pathlib import Path
from dotenv import load_dotenv
import httpx
from datetime import datetime
from pypdf import PdfReader

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

# â”€â”€ Load portfolio knowledge base once at import time â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
_KB_PATH = Path(__file__).parent.parent.parent / "Data" / "portfolio_knowledge.txt"
_PDF_PATH = Path(__file__).parent.parent.parent / "Data" / "Farhad_Billah_AI_Engineer.pdf"
_PDF_CONTEXT_LIMIT = 5000


def _load_knowledge_base() -> str:
    """Load the authored portfolio notes and text extracted from the CV."""
    sources = []
    try:
        sources.append(_KB_PATH.read_text(encoding="utf-8"))
    except Exception as exc:
        logger.warning(f"Could not load portfolio knowledge base: {exc}")

    try:
        reader = PdfReader(str(_PDF_PATH))
        pdf_text = "\n".join(page.extract_text() or "" for page in reader.pages).strip()
        if pdf_text:
            # Keep the request below Groq's token-per-minute limit while still
            # making the bundled CV available to the assistant.
            pdf_context = pdf_text[:_PDF_CONTEXT_LIMIT]
            sources.append(f"--- CV PDF ---\n{pdf_context}")
            logger.info(
                f"CV PDF loaded ({len(pdf_text)} chars; {len(pdf_context)} chars in prompt)"
            )
    except Exception as exc:
        logger.warning(f"Could not load CV PDF: {exc}")

    return "\n\n".join(sources)


try:
    PORTFOLIO_KNOWLEDGE = _load_knowledge_base()
    logger.info(f"Portfolio knowledge base loaded ({len(PORTFOLIO_KNOWLEDGE)} chars)")
except Exception as e:
    PORTFOLIO_KNOWLEDGE = ""
    logger.warning(f"Could not load portfolio knowledge base: {e}")

SYSTEM_PROMPT = f"""You are Farhad's personal AI assistant, embedded on Md. Farhad Billah's portfolio website.
Your job is to answer questions about Farhad warmly and accurately, acting like a knowledgeable friend who knows everything about him.

PORTFOLIO KNOWLEDGE BASE:
{PORTFOLIO_KNOWLEDGE}

RESPONSE RULES:
- Answer personal, background, education, career, skills, projects, research, contact, and other questions about Farhad Billah using the knowledge sources above.
- Interpret the user's intended meaning even when their message contains spelling mistakes, grammar mistakes, missing words, unusual word order, or informal phrasing. Silently correct obvious mistakes while understanding the question; do not criticize or mention the mistakes.
- If the intended meaning is reasonably clear, answer it directly. Only ask a brief clarification question when multiple meanings are genuinely possible.
- If a personal detail is not present in those sources, say clearly that the information is not available rather than refusing to answer or inventing it.
- If asked something NOT related to Farhad (e.g. general coding questions, weather, sports), politely say: "I am Farhad's personal assistant and I can only answer questions about him. Is there something you would like to know about Farhad's work, projects, or background?"
- Be warm, friendly, and conversational â€” not robotic.
- Keep answers concise unless the user asks for details.
- When mentioning projects, include the live link if available.
- When mentioning research papers, include the DOI/link.
- Do NOT use emojis or emoticons anywhere in your response.
- Do NOT use asterisks like * or ** or bullet asterisks in your response. Use plain text formatting.
- Do NOT include <think> tags or internal reasoning in your response.
- Do NOT make up information not present in the knowledge base.
- Respond in the same language the user writes in (English or Bengali).
"""


class AIService:
    def __init__(self):
        self.groq_api_key = os.getenv("GROQ_API_KEY")
        self.groq_model = os.getenv("GROQ_MODEL", "openai/gpt-oss-120b")
        self.last_model_used = self.groq_model
        self.use_groq = True

        logger.info(f"AIService initialized â€” chat model: {self.groq_model}")
        if not self.groq_api_key:
            logger.warning("GROQ_API_KEY not set")

    # â”€â”€ Chat â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

    async def generate_response(self, user_input: str) -> dict:
        """Generate a portfolio-aware chat response via Groq."""
        if not self.groq_api_key:
            return {"success": False, "error": "GROQ_API_KEY not configured"}

        url = "https://api.groq.com/openai/v1/chat/completions"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.groq_api_key}",
        }
        payload = {
            "model": self.groq_model,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_input},
            ],
            "max_tokens": 800,
            "temperature": 0.6,
        }

        try:
            start = datetime.now()
            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.post(url, json=payload, headers=headers)

            elapsed = (datetime.now() - start).total_seconds()
            logger.info(f"Groq chat response in {elapsed:.2f}s â€” status {resp.status_code}")

            if resp.status_code == 200:
                data = resp.json()
                text = data["choices"][0]["message"]["content"]
                # Strip thinking tags if model returns them
                text = re.sub(r"<think>[\s\S]*?</think>", "", text).strip()
                # Remove markdown emphasis while retaining list structure.
                text = re.sub(r"\*{1,3}([^*]+)\*{1,3}", r"\1", text)
                text = re.sub(r"(?m)^\s*\*\s+", "- ", text)
                # Remove emojis and special symbol pictographs
                text = re.sub(r"[\U0001F600-\U0001F64F\U0001F300-\U0001F5FF\U0001F680-\U0001F6FF\U0001F700-\U0001F77F\U0001F780-\U0001F7FF\U0001F800-\U0001F8FF\U0001F900-\U0001F9FF\U0001FA00-\U0001FA6F\U0001FA70-\U0001FAFF\U00002600-\U000026FF\U00002700-\U000027BF\U00002300-\U000023FF\U00002B50\u200D\uFE0F]", "", text)
                text = text.strip()
                self.last_model_used = self.groq_model
                return {"success": True, "response": text}
            else:
                err = f"Groq API error {resp.status_code}: {resp.text}"
                logger.error(err)
                return {"success": False, "error": err}

        except Exception as exc:
            logger.error(f"Exception calling Groq chat API: {exc}")
            return {"success": False, "error": str(exc)}

    # â”€â”€ Speech-to-Text (Groq Whisper) â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

    async def transcribe_audio(self, audio_bytes: bytes, filename: str = "audio.webm") -> dict:
        """Transcribe audio using Groq's Whisper API."""
        if not self.groq_api_key:
            return {"success": False, "error": "GROQ_API_KEY not configured"}

        url = "https://api.groq.com/openai/v1/audio/transcriptions"
        headers = {"Authorization": f"Bearer {self.groq_api_key}"}

        # Determine MIME type from filename
        ext = filename.rsplit(".", 1)[-1].lower()
        mime_map = {
            "webm": "audio/webm",
            "mp4": "audio/mp4",
            "m4a": "audio/mp4",
            "wav": "audio/wav",
            "mp3": "audio/mpeg",
            "ogg": "audio/ogg",
        }
        mime = mime_map.get(ext, "audio/webm")

        try:
            start = datetime.now()
            async with httpx.AsyncClient(timeout=60.0) as client:
                resp = await client.post(
                    url,
                    headers=headers,
                    files={"file": (filename, audio_bytes, mime)},
                    data={"model": "whisper-large-v3", "response_format": "json"},
                )

            elapsed = (datetime.now() - start).total_seconds()
            logger.info(f"Groq Whisper response in {elapsed:.2f}s â€” status {resp.status_code}")

            if resp.status_code == 200:
                data = resp.json()
                transcript = data.get("text", "").strip()
                logger.info(f"Transcription: {transcript[:100]}")
                return {"success": True, "transcript": transcript}
            else:
                err = f"Whisper API error {resp.status_code}: {resp.text}"
                logger.error(err)
                return {"success": False, "error": err}

        except Exception as exc:
            logger.error(f"Exception calling Groq Whisper API: {exc}")
            return {"success": False, "error": str(exc)}
