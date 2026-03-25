import google.generativeai as genai
from google.api_core import exceptions
import asyncio
import time
from typing import List
from models import Message
from core.logger import logger

class GeminiService:
    def __init__(self, api_key: str):
        genai.configure(api_key=api_key)
        self.model_name = "gemini-2.0-flash-exp"
        self.max_retries = 3
        self.base_delay = 1.0

    async def _retry_with_backoff(self, func, *args, retries=None):
        if retries is None:
            retries = self.max_retries
            
        try:
            return await func(*args)
        except exceptions.ResourceExhausted as e:
            # Handle 429/Quota errors
            if retries > 0:
                delay = self.base_delay * (2 ** (self.max_retries - retries))
                logger.warning(f"⚠️ Rate limit hit, retrying in {delay}s... ({retries} left)")
                await asyncio.sleep(delay)
                return await self._retry_with_backoff(func, *args, retries=retries - 1)
            raise e

    async def generate_content(self, messages: List[Message]) -> str:
        model = genai.GenerativeModel(self.model_name)
        
        conversation = "\n".join([f"{m.role.upper()}: {m.content}" for m in messages])
        
        prompt = f"""
{conversation}
Continue the IELTS Speaking Part 1 interview. 
Ask ONE short question only.
If you already asked 10–12 questions or it's been 4–5 minutes, end with:
"That's the end of Part 1."
"""
        async def call_api():
            response = await model.generate_content_async(prompt)
            return response.text.strip()

        return await self._retry_with_backoff(call_api)

    async def generate_final_report(self, history: List[Message]) -> 'FinalReport':
        # Lazy import to avoid circular dependency
        from models import FinalReport
        
        model = genai.GenerativeModel(
            self.model_name,
            generation_config={"response_mime_type": "application/json"}
        )
        
        # Format conversation
        conversation = ""
        for m in history:
            role = m.role.upper()
            content = m.content
            conversation += f"{role}: {content}\n\n"
            
        prompt = f"""
You are an expert IELTS Examiner. Review the following Speaking Test Session and provide a final assessment.

SESSION HISTORY:
{conversation}

INSTRUCTIONS:
1. Analyze the candidate's performance based on the 4 IELTS criteria: 
   - Fluency and Coherence
   - Lexical Resource
   - Grammatical Range and Accuracy
   - Pronunciation
   (Note: Use the embedded [SYSTEM INFO] in User messages for acoustic details like Pitch and Pauses).
2. Assign a band score (0.0 - 9.0) for each criterion and an Overall Score.
3. Provide detailed, constructive suggestions for improvement in Markdown format.

OUTPUT SCHEMA (JSON):
{{
    "overall_score": float,
    "fluency_coherence": float,
    "lexical_resource": float,
    "grammatical_range": float,
    "pronunciation": float,
    "suggestions": "string (markdown)"
}}
"""
        async def call_api():
            response = await model.generate_content_async(prompt)
            return response.text.strip()

        json_str = await self._retry_with_backoff(call_api)
        
        # Clean markdown code blocks if present
        if "```json" in json_str:
            json_str = json_str.split("```json")[1].split("```")[0].strip()
        elif "```" in json_str:
            json_str = json_str.split("```")[1].split("```")[0].strip()
            
        import json
        data = json.loads(json_str)
        return FinalReport(**data)

    async def generate_first_question(self, system_prompt: str) -> str:
        model = genai.GenerativeModel(self.model_name)
        
        prompt = f"""
SYSTEM: {system_prompt}

Start the IELTS Speaking Part 1 interview. Ask your first question.
"""
        async def call_api():
            response = await model.generate_content_async(prompt)
            return response.text.strip()

        return await self._retry_with_backoff(call_api)