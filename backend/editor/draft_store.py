import copy
import threading
import uuid
from dataclasses import dataclass
from typing import Dict, Optional

from generator.grid import Grid


@dataclass(frozen=True)
class Draft:
    """A server-owned editing session.

    The frontend holds only the `draft_id`; the authoritative grid lives on the
    backend.
    """

    draft_id: str
    grid: Grid


class DraftStore:
    """In-memory storage for editor drafts (MVP).

    Why this exists:
    - Supports server-owned drafts without requiring DB/Redis initially.
    - Easy to replace later with Redis or a DB table.

    Note: This store is process-local. If you run multiple backend instances,
    you should move drafts to Redis/DB.
    """

    def __init__(self):
        self._lock = threading.Lock()
        self._drafts: Dict[str, Grid] = {}

    def create(self, grid: Grid) -> Draft:
        draft_id = str(uuid.uuid4())
        with self._lock:
            self._drafts[draft_id] = grid
        return Draft(draft_id=draft_id, grid=grid)

    def get(self, draft_id: str) -> Optional[Grid]:
        with self._lock:
            return self._drafts.get(draft_id)

    def set(self, draft_id: str, grid: Grid) -> bool:
        with self._lock:
            if draft_id not in self._drafts:
                return False
            self._drafts[draft_id] = grid
            return True
