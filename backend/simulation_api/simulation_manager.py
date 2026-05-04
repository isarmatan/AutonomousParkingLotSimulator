from typing import Dict, Optional
from .simulation_session import SimulationSession

_sessions: Dict[str, SimulationSession] = {}


def add_session(session: SimulationSession) -> None:
    _sessions[session.session_id] = session


def get_session(session_id: str) -> Optional[SimulationSession]:
    return _sessions.get(session_id)


def remove_session(session_id: str) -> None:
    _sessions.pop(session_id, None)
