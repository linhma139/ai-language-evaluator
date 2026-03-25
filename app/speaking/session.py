import time
import uuid
from typing import Dict, Optional
from models import Session, Message

class SessionManager:
    def __init__(self):
        self.sessions: Dict[str, Session] = {}
        self.max_duration = 300  # 5 minutes
        self.max_questions = 12

    def create_session(self, system_prompt: str) -> str:
        session_id = str(uuid.uuid4())
        self.sessions[session_id] = Session(
            id=session_id,
            start=time.time(),
            count=0,
            history=[Message(role="system", content=system_prompt)]
        )
        return session_id

    def get_session(self, session_id: str) -> Optional[Session]:
        return self.sessions.get(session_id)

    def add_message(self, session_id: str, role: str, content: str):
        session = self.sessions.get(session_id)
        if session:
            session.history.append(Message(role=role, content=content))
            if role == 'assistant':
                session.count += 1

    def increment_count(self, session_id: str):
        session = self.sessions.get(session_id)
        if session:
            session.count += 1

    def should_end_session(self, session_id: str, last_question: str) -> bool:
        session = self.sessions.get(session_id)
        if not session:
            return True
        
        elapsed = time.time() - session.start
        over_time = elapsed > self.max_duration
        over_limit = session.count >= self.max_questions
        explicitly_ended = "end of part 1" in last_question.lower()
        
        return over_time or over_limit or explicitly_ended

    def cleanup_old_sessions(self):
        one_hour_ago = time.time() - 3600
        # Create a list of keys to delete to avoid runtime errors during iteration
        expired_ids = [sid for sid, s in self.sessions.items() if s.start < one_hour_ago]
        for sid in expired_ids:
            del self.sessions[sid]