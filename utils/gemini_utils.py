# utils/gemini_utils.py
import os
from dotenv import load_dotenv
import google.generativeai as genai

# load .env if present
load_dotenv()

# Model to use
GEMINI_MODEL = "gemini-2.5-flash"

def configure_gemini(api_key: str | None = None):
    """
    Configure google.generativeai with an API key.
    Reads GEMINI_API_KEY from environment if api_key not provided.
    """
    key = api_key or os.environ.get("GEMINI_API_KEY")
    if not key:
        raise RuntimeError("GEMINI_API_KEY not set. Set environment variable or pass it to configure_gemini().")
    genai.configure(api_key=key)

def gemini_generate(prompt: str, max_output_chars: int = 5000) -> str:
    """
    Send prompt to Gemini and return plain text response.
    Uses the google.generativeai SDK's GenerativeModel.generate_content.
    """
    model = genai.GenerativeModel(GEMINI_MODEL)
    response = model.generate_content(prompt)
    # response.text should contain the reply for this SDK version
    return getattr(response, "text", "") or ""
