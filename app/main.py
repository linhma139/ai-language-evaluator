import os
import asyncio
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import sys

# Fix Import Error when running from root
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from core.logger import logger
from core.config import settings
from api.router import api_router
from api.deps import get_session_manager

app = FastAPI(
    title="IELTS & TOEIC AI Server",
    description="Professional Microservice for Evaluating English Speaking and Writing",
    version="2.0.0"
)

# --- MIDDLEWARE ---
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serve static UI at /ui
app.mount("/ui", StaticFiles(directory="./ui", html=True), name="ui")

# --- BACKGROUND TASKS ---
async def cleanup_loop():
    """Background task to clean up old sessions every hour"""
    session_manager = get_session_manager()
    while True:
        await asyncio.sleep(3600)
        session_manager.cleanup_old_sessions()
        logger.info("Executed old session cleanup.")

@app.on_event("startup")
async def startup_event():
    logger.info("Starting up API Server...")
    # Start the background session cleanup task
    asyncio.create_task(cleanup_loop())

@app.get("/")
async def root():
    return {"status": "ok", "message": "FastAPI AI Server is running"}

# --- INCLUDE API ROUTERS ---
app.include_router(api_router)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=settings.PORT, reload=True)