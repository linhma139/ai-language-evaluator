import re
import httpx
from pathlib import Path
from typing import Optional
from core.logger import logger
from core.config import settings
from schemas.writing import WritingRequest, WritingFeedback

# Shared HTTP client - reuse connection pool across requests
_http_client: httpx.AsyncClient | None = None

# Load prompt template once at module level
_PROMPT_TEMPLATE_PATH = Path(__file__).parent / "prompt_template.txt"
_SYSTEM_PROMPT = _PROMPT_TEMPLATE_PATH.read_text(encoding="utf-8")


def _get_http_client() -> httpx.AsyncClient:
    """Get or create a shared async HTTP client."""
    global _http_client
    if _http_client is None or _http_client.is_closed:
        _http_client = httpx.AsyncClient(timeout=settings.LLM_TIMEOUT)
    return _http_client


async def close_http_client() -> None:
    """Gracefully close the shared HTTP client."""
    global _http_client
    if _http_client and not _http_client.is_closed:
        await _http_client.aclose()
        _http_client = None


def _parse_score(pattern: str, text: str, label: str, log_prefix: str) -> float:
    """Parse a score from LLM output with warning on failure."""
    match = re.search(pattern, text, re.IGNORECASE)
    if match:
        return float(match.group(1))
    logger.warning(f"{log_prefix} Failed to parse \'{label}\' from LLM output")
    return 0.0


async def evaluate_writing_with_local_llm(
    request: WritingRequest,
    correlation_id: Optional[str] = None,
) -> WritingFeedback:
    """Call REST API (Ollama) to evaluate Writing and return WritingFeedback."""

    log_prefix = f"[cid={correlation_id}]" if correlation_id else ""

    prompt = (
        _SYSTEM_PROMPT + "\n"
        "<|user|>\n"
        f"Please evaluate this IELTS {request.task_type} essay.\n\n"
        f"Question:\n{request.question}\n\n"
        f"Essay:\n{request.content}<|end|>\n"
        "<|assistant|>\n"
    )

    try:
        client = _get_http_client()
        payload = {
            "model": settings.LLM_MODEL_NAME,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": 0.2,
                "num_ctx": 3080,
            },
        }

        logger.info(f"{log_prefix} Sending evaluation request to {settings.LLM_API_URL}")
        response = await client.post(settings.LLM_API_URL, json=payload)
        response.raise_for_status()

        response_data = response.json()
        response_text = response_data.get("response", "")

        # Parse scores with warnings on failure
        overall = _parse_score(
            r"Overall (?:Band )?Score:\s*([\d.]+)", response_text, "Overall Score", log_prefix
        )
        ta_score = _parse_score(
            r"Task Achievement(?: / Response)?:?\s*([\d.]+)", response_text, "Task Achievement", log_prefix
        )
        cc_score = _parse_score(
            r"Coherence and Cohesion:?\s*([\d.]+)", response_text, "Coherence & Cohesion", log_prefix
        )
        lr_score = _parse_score(
            r"Lexical Resource:?\s*([\d.]+)", response_text, "Lexical Resource", log_prefix
        )
        gra_score = _parse_score(
            r"Grammatical Range and Accuracy:?\s*([\d.]+)", response_text, "Grammar", log_prefix
        )

        # Log warning if all scores are 0 (likely parse failure)
        if overall == 0.0 and ta_score == 0.0:
            logger.warning(
                f"{log_prefix} All scores parsed as 0.0 - LLM output may be malformed. "
                f"Raw output (first 300 chars): {response_text[:300]}"
            )

        # Extract detailed feedback
        detailed_feedback = response_text
        feedback_split = re.split(
            r"### Detailed Feedback:|Detailed Feedback:", response_text, flags=re.IGNORECASE
        )
        if len(feedback_split) > 1:
            detailed_feedback = feedback_split[1].strip()

        return WritingFeedback(
            overall_score=overall,
            sub_scores={
                "Task Achievement": ta_score,
                "Coherence & Cohesion": cc_score,
                "Lexical Resource": lr_score,
                "Grammatical Range & Accuracy": gra_score,
            },
            detailed_feedback=detailed_feedback,
            corrected_version="",
            corrections=[],
        )

    except httpx.TimeoutException as e:
        logger.error(f"{log_prefix} LLM timeout after {settings.LLM_TIMEOUT}s: {e}")
        raise

    except httpx.ConnectError as e:
        logger.error(f"{log_prefix} Cannot connect to LLM at {settings.LLM_API_URL}: {e}")
        raise

    except Exception as e:
        logger.error(f"{log_prefix} Error calling LLM API: {e}", exc_info=True)
        raise
