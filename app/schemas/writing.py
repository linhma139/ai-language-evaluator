from typing import List, Optional, Literal, Dict
from pydantic import BaseModel, field_validator

class WritingRequest(BaseModel):
    attempt_id: str
    response_id: str
    exam_type: str  # e.g., "IELTS", "TOEIC", or variations like "IELTS_ACADEMIC"
    task_type: str  # e.g., "Task 1", "Task 2", "Email", "Essay"
    question: str
    content: str
    target_score: Optional[float] = None

    @field_validator("exam_type", mode="before")
    @classmethod
    def validate_exam_type(cls, v: str) -> str:
        if not isinstance(v, str):
            raise ValueError("exam_type must be a string")
        
        v_upper = v.upper()
        if "IELTS" in v_upper:
            return "IELTS"
        if "TOEIC" in v_upper:
            return "TOEIC"
            
        raise ValueError("exam_type must contain either 'IELTS' or 'TOEIC'")

class ErrorCorrection(BaseModel):
    original_text: str
    corrected_text: str
    explanation: str
    error_type: str  # Grammar, Vocabulary, Coherence, etc.

class WritingFeedback(BaseModel):
    attempt_id: str
    response_id: str
    overall_score: float
    sub_scores: Dict[str, float]  # IELTS: TA/TR, CC, LR, GRA | TOEIC: Grammar, Vocab, Organization
    detailed_feedback: str
    corrected_version: str  # Fully rewritten essay
    corrections: List[ErrorCorrection]  # List of specific errors

class WritingResultEvent(BaseModel):
    status: Literal["success", "error"]
    attempt_id: str
    response_id: str
    data: Optional[WritingFeedback] = None
    error_code: Optional[str] = None
    error_message: Optional[str] = None
