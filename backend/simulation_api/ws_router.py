from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from . import simulation_manager

ws_router = APIRouter()


@ws_router.websocket("/simulation/ws/{session_id}")
async def simulation_websocket(websocket: WebSocket, session_id: str):
    """
    WebSocket endpoint for a live simulation session.

    The client first calls POST /simulation/start to obtain a session_id,
    then connects here. The backend immediately sends an INIT message and
    starts streaming STEP messages. The client can send control messages
    (PAUSE / RESUME / STOP / RESET) at any time.
    """
    session = simulation_manager.get_session(session_id)
    if session is None:
        await websocket.close(code=4004)
        return

    await session.connect(websocket)

    try:
        while True:
            data = await websocket.receive_json()
            await session.handle_control(data)
    except WebSocketDisconnect:
        await session.stop()
    finally:
        simulation_manager.remove_session(session_id)
