import os
import json
import re
from typing import Any
from dotenv import load_dotenv
from core.logger import logger

from models import WritingRequest, WritingFeedback

load_dotenv()




import httpx
import re

async def evaluate_writing_with_local_llm(request: WritingRequest) -> WritingFeedback:
    """Call Local LLM (via gRPC) to evaluate Writing and return WritingFeedback."""
    
    # Create a prompt with an appropriate system prompt
    prompt = f"""<|system|>
Role: IELTS Academic Writing Tutor. Score writing and suggest improvements.
Weights: Task 1=1/3, Task 2=2/3.
Criteria (25% each, overall=average): Task Achievement/Response(TA/TR), Coherence&Cohesion(CC), Lexical Resource(LR), Grammar(GRA).
Band Descriptors (9 to 4):
9: Fully addressed, effortless cohesion, natural wide vocab, flexible accurate grammar.
8: Sufficiently addressed, logical sequence, precise vocab, few errors.
7: Clear position/progression, adequate flexible vocab, good complex grammar control.
6: Addresses all parts, coherent, adequate vocab, mixed simple/complex grammar, some errors.
5: Partially addressed, lacks progression, limited vocab, frequent grammar errors.
4: Minimal response, incoherent, basic vocab, predominant errors.
Feedback focus: Task completion, clear overview/key features, paragraphing, vocabulary, and grammar/punctuation.<|end|>
<|user|>
Please evaluate this IELTS {request.task_type} essay.

Question:
{request.question}

Essay:
{request.content}<|end|>
<|assistant|>
"""

    try:
        import sys
        import os
        current_dir = os.path.dirname(__file__)
        if current_dir not in sys.path:
            sys.path.insert(0, current_dir)
            
        import grpc
        import llm_pb2
        import llm_pb2_grpc

        async with grpc.aio.insecure_channel('localhost:50051') as channel:
            stub = llm_pb2_grpc.LLMServiceStub(channel)
            
            request_grpc = llm_pb2.GenerateRequest(
                prompt=prompt,
                temperature=0.2,
                max_tokens=2048
            )
            
            response = await stub.Generate(request_grpc)
            # The response_text data from the gRPC server will be returned
            response_text = response.text
            
            # Initialize default values
            overall = 0.0
            ta_score = 0.0
            cc_score = 0.0
            lr_score = 0.0
            gra_score = 0.0

            # Use Regex to parse the score. Typical pattern in Phi-3 output: "- Overall Band Score: 6.5"
            match_overall = re.search(r"Overall (?:Band )?Score:\s*([\d.]+)", response_text, re.IGNORECASE)
            match_ta = re.search(r"Task Achievement(?: / Response)?:?\s*([\d.]+)", response_text, re.IGNORECASE)
            match_cc = re.search(r"Coherence and Cohesion:?\s*([\d.]+)", response_text, re.IGNORECASE)
            match_lr = re.search(r"Lexical Resource:?\s*([\d.]+)", response_text, re.IGNORECASE)
            match_gra = re.search(r"Grammatical Range and Accuracy:?\s*([\d.]+)", response_text, re.IGNORECASE)

            if match_overall: overall = float(match_overall.group(1))
            if match_ta: ta_score = float(match_ta.group(1))
            if match_cc: cc_score = float(match_cc.group(1))
            if match_lr: lr_score = float(match_lr.group(1))
            if match_gra: gra_score = float(match_gra.group(1))
            
            # Extract the Detailed Feedback portion (strip the score block above if possible, or take it verbatim)
            detailed_feedback = response_text
            feedback_split = re.split(r"### Detailed Feedback:|Detailed Feedback:", response_text, flags=re.IGNORECASE)
            if len(feedback_split) > 1:
                detailed_feedback = feedback_split[1].strip()

            return WritingFeedback(
                overall_score=overall,
                sub_scores={
                    "Task Achievement": ta_score,
                    "Coherence & Cohesion": cc_score,
                    "Lexical Resource": lr_score,
                    "Grammatical Range & Accuracy": gra_score
                },
                detailed_feedback=detailed_feedback,
                corrected_version="",  # Phi-3 does not return a JSON standard corrected essay
                corrections=[]         # Phi-3 does not return a JSON array for corrections
            )
    except Exception as e:
        logger.error(f"Error calling Local LLM gRPC: {e}", exc_info=True)
        return WritingFeedback(
            overall_score=0.0,
            sub_scores={},
            detailed_feedback=f"Error connecting to local AI Model: {str(e)}",
            corrected_version="",
            corrections=[]
        )


