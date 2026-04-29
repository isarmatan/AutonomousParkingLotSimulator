"""FastAPI application entrypoint.

This file exists to expose a clean HTTP API for the frontend (editor + simulation
configuration).

Run locally with:
    uvicorn api_app:app --reload
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from editor.editor_router import router as editor_router
from simulation_api.simulation_router import router as simulation_router
from db.database import init_db

app = FastAPI()

# Enable CORS for frontend integration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # For development, allow all. In production, specify ["http://localhost:3000"]
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(editor_router)
app.include_router(simulation_router)


@app.on_event("startup")
def _startup() -> None:
    # Ensure the SQLite DB file + tables exist before serving requests.
    init_db()
