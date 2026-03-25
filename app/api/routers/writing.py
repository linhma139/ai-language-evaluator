from fastapi import APIRouter, HTTPException
from models import WritingRequest, WritingFeedback
from writing.writing_service import evaluate_writing_with_local_llm
from core.logger import logger

router = APIRouter(prefix="/writing", tags=["Writing"])

@router.post("/evaluate", response_model=WritingFeedback)
async def evaluate_writing(request: WritingRequest):
    """
    Evaluate Writing (IELTS/TOEIC) using Local LLM, returning scores + detailed feedback.
    """
    try:
        feedback = await evaluate_writing_with_local_llm(request)
        return feedback
    except Exception as e:
        logger.error(f"Error evaluating writing: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to evaluate writing")
