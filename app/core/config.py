import os
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    GEMINI_API_KEY: str = ""
    GCS_BUCKET_NAME: str = ""
    SYSTEM_PROMPT: str = (
        "You are a linguistics expert and IELTS Speaking examiner. "
        "The user's speech content will be provided alongside technical metrics (Pitch, Fluency). "
        "Please analyze and comment on: "
        "1. Grammar & Vocabulary. "
        "2. Intonation (based on Pitch variance/standard deviation). "
        "3. Fluency (based on WPM and Pause count). "
        "Afterwards, please ask the next question to continue the IELTS Speaking Part 1 interview."
    )
    PORT: int = 8000

    class Config:
        env_file = ".env"
        # Mute warnings missing items from .env
        extra = "ignore" 

settings = Settings()
