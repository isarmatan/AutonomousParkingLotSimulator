import asyncio
from typing import Optional, Callable, Dict, Any
from fastapi import WebSocket


class SimulationSession:
    """
    Manages a single live simulation instance.
    Runs the simulation loop as an asyncio Task and streams
    timestep updates over a WebSocket connection.
    """

    def __init__(
        self,
        session_id: str,
        simulation_factory: Callable,
        grid_data: Dict[str, Any],
        max_timesteps: Optional[int],
        step_delay_ms: int,
    ):
        self.session_id = session_id
        self._simulation_factory = simulation_factory
        self.grid_data = grid_data
        self.max_timesteps = max_timesteps if max_timesteps and max_timesteps > 0 else None
        self.step_delay_ms = max(10, step_delay_ms)

        self.simulation = simulation_factory()
        self.websocket: Optional[WebSocket] = None
        self.status = "IDLE"
        self._task: Optional[asyncio.Task] = None
        # Plain bool flags are safe to read/write from any context (no event-loop
        # binding issues that affect asyncio.Event when created in a sync thread).
        self._paused: bool = False
        self._stopped: bool = False

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def connect(self, websocket: WebSocket):
        """Accept the websocket and start the simulation loop."""
        await websocket.accept()
        self.websocket = websocket
        self.status = "RUNNING"
        await self._send({"type": "INIT", "grid": self.grid_data})
        self._task = asyncio.create_task(self._run_loop())

    async def handle_control(self, msg: dict):
        """Process a control message from the frontend."""
        t = msg.get("type")
        if t == "PAUSE":
            self._paused = True
            await self._send_status("PAUSED")
        elif t == "RESUME":
            self._paused = False
            await self._send_status("RUNNING")
        elif t == "STOP":
            self._stopped = True
            self._paused = False  # unblock the poll loop
            await self._send_status("STOPPED")
        elif t == "RESET":
            await self._do_reset()

    async def stop(self):
        """Gracefully stop the simulation loop (called on WS disconnect)."""
        self._stopped = True
        self._paused = False  # unblock the poll loop
        if self._task and not self._task.done():
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

    # ------------------------------------------------------------------
    # Internal loop
    # ------------------------------------------------------------------

    async def _run_loop(self):
        loop = asyncio.get_running_loop()
        try:
            while not self._stopped:
                # Poll while paused (yields control back to the event loop each iteration)
                if self._paused:
                    await asyncio.sleep(0.05)
                    continue

                # Optional timestep cap
                if self.max_timesteps is not None and self.simulation.time >= self.max_timesteps:
                    await self._send_status("COMPLETED")
                    break

                # Run one simulation step in a thread pool to avoid blocking the event loop
                await loop.run_in_executor(None, self.simulation.step)

                await self._send_step()
                await asyncio.sleep(self.step_delay_ms / 1000.0)
        except Exception as e:
            await self._send({"type": "ERROR", "message": str(e)})
        finally:
            self.status = "STOPPED"

    # ------------------------------------------------------------------
    # Reset
    # ------------------------------------------------------------------

    async def _do_reset(self):
        # Stop the current loop
        self._stopped = True
        self._paused = False
        if self._task and not self._task.done():
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

        # Rebuild simulation from scratch
        self.simulation = self._simulation_factory()
        self._stopped = False
        self._paused = False
        self.status = "RUNNING"

        # Re-send INIT so the frontend resets its state
        await self._send({"type": "INIT", "grid": self.grid_data})
        self._task = asyncio.create_task(self._run_loop())

    # ------------------------------------------------------------------
    # Serialization helpers
    # ------------------------------------------------------------------

    async def _send_step(self):
        sim = self.simulation
        pos_map = sim.get_positions_snapshot()

        cars: Dict[str, list] = {}
        for cid, pos in pos_map.items():
            car = sim.all_cars.get(cid)
            is_initial = 1 if (car and getattr(car, "is_initial", False)) else 0
            cars[str(cid)] = [pos[0], pos[1], is_initial]

        avg_park = (
            sim.sum_steps_to_park / sim.arriving_cars_parked_count
            if sim.arriving_cars_parked_count > 0
            else None
        )
        avg_exit = (
            sim.sum_steps_to_exit / sim.total_exit_journeys
            if sim.total_exit_journeys > 0
            else None
        )

        stats = {
            "total_cars": sim.config.initial_cars + sim.arriving_cars_created,
            "total_parked": sim.total_parked,
            "total_failed_plans": sim.total_failed_plans,
            "total_exited": sim.total_exited,
            "arriving_cars_spawned": sim.arriving_cars_created,
            "arriving_cars_parked": sim.arriving_cars_parked_count,
            "average_steps_to_park": avg_park,
            "average_steps_to_exit": avg_exit,
        }

        await self._send({"type": "STEP", "t": sim.time, "cars": cars, "stats": stats})

    async def _send_status(self, status: str):
        self.status = status
        await self._send({"type": "STATUS", "status": status})

    async def _send(self, data: dict):
        if self.websocket:
            try:
                await self.websocket.send_json(data)
            except Exception:
                pass
