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

def is_gibberish(text: str) -> bool:
    """
    Detect if the text is gibberish using simple heuristics:
    1. Vowel ratio (English is usually 35-45%)
    2. Character repetition (e.g. 'aaaaa')
    3. Word repetition (e.g. 'test test test')
    4. Max word length
    """
    words = text.split()
    if not words:
        return True
    
    alpha_only = re.sub(r'[^a-zA-Z]', '', text).lower()
    if not alpha_only:
        # If text has content but no letters, it's not a valid essay
        return len(text.strip()) > 0

    # 1. Vowel ratio check
    vowels = "aeiou"
    vowel_count = sum(1 for char in alpha_only if char in vowels)
    vowel_ratio = vowel_count / len(alpha_only)
    if vowel_ratio < 0.15 or vowel_ratio > 0.80:
        return True

    # 2. Maximum word length check
    max_word_len = max(len(word) for word in words)
    if max_word_len > 40:
        return True

    # 3. Character repetition check (e.g., "aaaaaaa")
    if re.search(r'(.)\1{5,}', alpha_only):
        return True

    # 4. Word repetition check
    if len(words) > 10:
        from collections import Counter
        word_counts = Counter(words)
        most_common_word, count = word_counts.most_common(1)[0]
        if count / len(words) > 0.6: 
            return True

    return False

def count_words(text: str) -> int:
    """Simple word count by splitting on whitespace, ignoring punctuation."""
    # Remove punctuation for more accurate word count
    clean_text = re.sub(r'[^\w\s]', ' ', text)
    return len(clean_text.split())

# Keywords that indicate IELTS Task 1 (data description)
_TASK1_KEYWORDS = [
    "graph", "chart", "diagram", "table", "map", "process",
    "figure", "pie chart", "bar chart", "line graph", "flow chart",
    "illustration", "summarize the information", "summarise the information",
    "describe the", "the chart below", "the graph below", "the table below",
    "the diagram below", "the map below", "the figure below",
    "the charts below", "the graphs below", "the tables below",
]

# Keywords that indicate IELTS Task 2 (essay/opinion)
_TASK2_KEYWORDS = [
    "discuss both views", "to what extent", "do you agree or disagree",
    "agree or disagree", "advantages and disadvantages",
    "what are the causes", "what are the reasons",
    "some people think", "some people believe", "some people say",
    "give your opinion", "outweigh", "positive or negative",
    "is this a positive or negative", "what is your opinion",
]

def classify_task_type(question: str, raw_task_type: str) -> str:
    """
    Classify the IELTS writing task type based on keywords in the question.
    Falls back to raw_task_type parsing if no keywords match.

    Returns: "Task 1" or "Task 2"
    """
    raw_lower = raw_task_type.lower()

    # If task_type already explicit, trust it
    if "task 1" in raw_lower:
        return "Task 1"
    if "task 2" in raw_lower:
        return "Task 2"

    # Otherwise, classify from question content
    q_lower = question.lower()

    for kw in _TASK1_KEYWORDS:
        if kw in q_lower:
            return "Task 1"

    for kw in _TASK2_KEYWORDS:
        if kw in q_lower:
            return "Task 2"

    # Default to Task 2 (essay) as it is the more common writing task
    return "Task 2"

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

    # Check if this is a writing task at all
    is_writing = any(kw in task_type for kw in ["task 1", "task 2", "writing", "essay"])

    if not is_writing:
        # Non-writing question types: only check for gibberish
        if is_gibberish(content):
            return WritingFeedback(
                attempt_id=request.attempt_id,
                response_id=request.response_id,
                overall_score=1.0,
                sub_scores={k: 1.0 for k in ["Task Achievement", "Coherence & Cohesion", "Lexical Resource", "Grammatical Range & Accuracy"]},
                detailed_feedback=(
                    "### Early Exit Analysis\n"
                    "The provided content appears to be nonsensical or contains excessive repetitive characters. "
                    "A valid academic response is required for evaluation."
                ),
                corrected_version="Please provide a meaningful response to receive feedback.",
                corrections=[]
            )
        return None

    # Classify task type from question keywords
    classified = classify_task_type(request.question, request.task_type)

    if classified == "Task 1":
        thresholds = TASK1_THRESHOLDS
        task_name = "Task 1"
        min_recommended = 150
    else:
        thresholds = TASK2_THRESHOLDS
        task_name = "Task 2"
        min_recommended = 250

    # Check for gibberish first
    if is_gibberish(content):
        return WritingFeedback(
            attempt_id=request.attempt_id,
            response_id=request.response_id,
            overall_score=1.0,
            sub_scores={
                "Task Achievement": 1.0,
                "Coherence & Cohesion": 1.0,
                "Lexical Resource": 1.0,
                "Grammatical Range & Accuracy": 1.0,
            },
            detailed_feedback=(
                f"### Early Exit Analysis\n"
                f"**Status:** Nonsensical Content Detected\n\n"
                f"The response provided does not contain meaningful English sentences or is highly repetitive. "
                f"According to {request.exam_type} standards, such responses cannot be assessed and are assigned the lowest band score."
            ),
            corrected_version=(
                f"**Recommendation:** Please ensure your {task_name} response is written in clear, meaningful English."
            ),
            corrections=[]
        )

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
                    f"**Note:** According to official {request.exam_type} standards, an essay with significantly low word count "
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
