import os
import time
import asyncio
from datetime import datetime, timedelta
from fastapi import APIRouter, UploadFile, File, Form, HTTPException, Depends
from models import StartSessionRequest, FirstQuestionRequest, FinalReport, FinalReportRequest
from core.config import settings
from core.logger import logger

from speaking.services_audio import preprocess_audio
from speaking.services_analysis import analyze_audio
from speaking.services_synthesis import synthesize_data
from speaking.services_asr import transcribe_audio

from api.deps import get_session_manager, get_gemini_service, get_storage_bucket

router = APIRouter(prefix="/session", tags=["Speaking"])

@router.post("/start")
async def start_session(
    request: StartSessionRequest, 
    session_manager = Depends(get_session_manager)
):
    final_prompt = request.systemPrompt if request.systemPrompt else settings.SYSTEM_PROMPT
    session_id = session_manager.create_session(final_prompt)
    logger.info(f"Started new speaking session: {session_id}")
    return {"sessionId": session_id}

@router.post("/first-question")
async def first_question(
    request: FirstQuestionRequest,
    session_manager = Depends(get_session_manager),
    gemini_service = Depends(get_gemini_service)
):
    session = session_manager.get_session(request.sessionId)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    
    try:
        system_prompt_content = session.history[0].content
        question = await gemini_service.generate_first_question(system_prompt_content)
        
        session_manager.add_message(request.sessionId, "assistant", question)
        return {"question": question, "done": False}
    except Exception as e:
        logger.error(f"Error generating first question: {e}", exc_info=True)
        if "429" in str(e):
             raise HTTPException(status_code=429, detail="Rate limit exceeded. Please wait a moment.")
        raise HTTPException(status_code=500, detail="Failed to generate question")

@router.post("/answer")
async def answer(
    file: UploadFile = File(...),
    sessionid: str = Form(...),
    session_manager = Depends(get_session_manager),
    gemini_service = Depends(get_gemini_service),
    bucket = Depends(get_storage_bucket)
):
    session = session_manager.get_session(sessionid)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    
    upload_dir = f"uploads/{sessionid}"
    os.makedirs(upload_dir, exist_ok=True)

    try:
        timestamp = int(time.time() * 1000)
        user_msg_count = len([m for m in session.history if m.role == 'user'])
        answer_number = user_msg_count + 1
        
        original_filename = f"answer_{answer_number:02d}_{timestamp}_orig.webm"
        original_path = os.path.join(upload_dir, original_filename)
        
        with open(original_path, "wb") as f:
            f.write(await file.read())
            
        clean_path = await asyncio.to_thread(preprocess_audio, original_path)
        clean_filename = os.path.basename(clean_path)
        
        destination = f"uploads/{sessionid}/{clean_filename}"
        blob = bucket.blob(destination)
        
        await asyncio.to_thread(blob.upload_from_filename, clean_path)
        
        blob.metadata = {
            "sessionId": sessionid,
            "answerNumber": str(answer_number),
            "uploadedAt": datetime.now().isoformat(),
            "type": "cleaned_audio"
        }
        blob.patch()
        
        signed_url = blob.generate_signed_url(version="v4", expiration=timedelta(hours=1), method="GET")
        gcs_uri = f"gs://{settings.GCS_BUCKET_NAME}/{destination}"
        
        transcript_task = transcribe_audio(gcs_uri, 'LINEAR16' if clean_path.endswith('.wav') else 'WEBM_OPUS') 
        analysis_task = asyncio.to_thread(analyze_audio, clean_path)
        
        transcript_res, acoustic_res = await asyncio.gather(transcript_task, analysis_task)
        
        synthesis_result = synthesize_data(transcript_res, acoustic_res)
        transcript_text = synthesis_result['transcript']
        analysis_summary = synthesis_result['summary_text']
        
        full_user_input = f"{transcript_text}\n\n[SYSTEM INFO]\n{analysis_summary}"
        logger.info(f"Sending to Gemini for session {sessionid}:\n{full_user_input}")

        session_manager.increment_count(sessionid)
        session_manager.add_message(sessionid, "user", full_user_input)
        
        next_question = await gemini_service.generate_content(session.history)
        session_manager.add_message(sessionid, "assistant", next_question)
        
        done = session_manager.should_end_session(sessionid, next_question)
        
        return {
            "transcript": transcript_text,
            "analysis": synthesis_result['metrics'],
            "question": next_question,
            "done": done,
            "audioUrl": signed_url,
            "answerNumber": answer_number,
            "feedback": analysis_summary
        }

    except Exception as e:
        logger.error(f"Processing error in answer route: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Server error: {str(e)}")

@router.post("/end", response_model=FinalReport)
async def end_session_report(
    request: FinalReportRequest,
    session_manager = Depends(get_session_manager),
    gemini_service = Depends(get_gemini_service)
):
    session = session_manager.get_session(request.sessionId)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
        
    try:
        report = await gemini_service.generate_final_report(session.history)
        return report
    except Exception as e:
        logger.error(f"Error generating report: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to generate final report")
