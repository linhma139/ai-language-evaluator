from google.cloud import storage
from speaking.session import SessionManager
from speaking.services_llm import GeminiService
from core.config import settings
from core.logger import logger

# Initialize global instances for the entire app
session_manager = SessionManager()

# Initialize gemini_service only if API_KEY is present
gemini_service = None
if settings.GEMINI_API_KEY:
    gemini_service = GeminiService(settings.GEMINI_API_KEY)

# Initialize GCS Client
storage_client = None
try:
    storage_client = storage.Client()
except Exception as e:
    logger.warning(f"Note: Cannot initialize Google Cloud Storage Client. Ignore if running local dev test (Error: {e})")

def get_session_manager() -> SessionManager:
    return session_manager

def get_gemini_service() -> GeminiService:
    if not gemini_service:
        raise ValueError("GEMINI_API_KEY is not configured")
    return gemini_service

def get_storage_bucket():
    if not storage_client or not settings.GCS_BUCKET_NAME:
        raise ValueError("GCS_BUCKET_NAME or Client is not configured")
    return storage_client.bucket(settings.GCS_BUCKET_NAME)
