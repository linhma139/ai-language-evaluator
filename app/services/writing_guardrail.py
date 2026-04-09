import re
from typing import Optional
from schemas.writing import WritingRequest, WritingFeedback

# IELTS Band Descriptors thresholds for low word counts
# (limit, band_score, reason)
TASK1_THRESHOLDS = [
    (20, 1.0, "The response is too short to accurately assess language use and task fulfillment."),
    (50, 2.0, "The response is extremely limited, providing only very basic information."),
    (100, 3.0, "The response provides limited information and suffers from significant repetition.")
]

TASK2_THRESHOLDS = [
    (20, 1.0, "The response does not relate to the prompt or is too short to evaluate."),
    (80, 2.0, "The response provides hardly any direct answering of the prompt."),
    (150, 3.0, "The response contains few ideas which are not adequately developed.")
]

def count_words(text: str) -> int:
    """Simple word count by splitting on whitespace, ignoring punctuation."""
    # Remove punctuation for more accurate word count
    clean_text = re.sub(r'[^\w\s]', ' ', text)
    return len(clean_text.split())

def check_word_count_guardrail(request: WritingRequest) -> Optional[WritingFeedback]:
    """
    Check if the word count falls into the low band categories (0-3).
    Returns WritingFeedback if guardrail is triggered (Early Exit), else None.
    """
    content = request.content
    task_type = request.task_type.lower()
    word_count = count_words(content)

    thresholds = []
    task_name = ""
    min_recommended = 0

    if "task 1" in task_type:
        thresholds = TASK1_THRESHOLDS
        task_name = "Task 1"
        min_recommended = 150
    elif "task 2" in task_type or "essay" in task_type:
        thresholds = TASK2_THRESHOLDS
        task_name = "Task 2"
        min_recommended = 250
    else:
        # No guardrail defined for other task types
        return None

    for limit, band, reason in thresholds:
        if word_count <= limit:
            return WritingFeedback(
                attempt_id=request.attempt_id,
                response_id=request.response_id,
                overall_score=band,
                sub_scores={
                    "Task Achievement": band,
                    "Coherence & Cohesion": band,
                    "Lexical Resource": band,
                    "Grammatical Range & Accuracy": band,
                },
                detailed_feedback=(
                    f"### Early Exit Analysis\n"
                    f"**Word Count:** {word_count} words\n\n"
                    f"{reason}\n\n"
                    f"**Note:** According to official IELTS Band Descriptors, an essay with significantly low word count "
                    f"cannot be fully assessed for proficiency and is capped at lower bands. "
                    f"A full AI evaluation was skipped to ensure consistency with examiner standards."
                ),
                corrected_version=(
                    f"**Recommendation:** Your {task_name} response is underweight. "
                    f"Please aim for at least {min_recommended} words for a better score."
                ),
                corrections=[]
            )
    
    return None
