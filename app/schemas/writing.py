from pydantic import BaseModel
from typing import List, Optional, Literal, Dict

class WritingRequest(BaseModel):
    attempt_id: str
    response_id: str
    exam_type: Literal["IELTS", "TOEIC"]
    task_type: str  # e.g., "Task 1", "Task 2", "Email", "Essay"
    question: str
    content: str
    target_score: Optional[float] = None

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
