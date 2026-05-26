import asyncio
import json
import platform
import sys
from typing import Optional, Callable, Dict, Any
from fastapi import WebSocket

try:
    import psutil as _psutil
    _PSUTIL_OK = True
except ImportError:
    _psutil = None  # type: ignore
    _PSUTIL_OK = False


def _collect_machine_specs() -> dict:
    specs = {
        "os": platform.platform(),
        "python": sys.version.split()[0],
        "cpu_model": platform.processor() or "unknown",
    }
    if _PSUTIL_OK:
        try:
            specs["cpu_logical"] = _psutil.cpu_count(logical=True)
            specs["cpu_physical"] = _psutil.cpu_count(logical=False)
            specs["ram_total_gb"] = round(_psutil.virtual_memory().total / (1024 ** 3), 1)
        except Exception:
            pass
    return specs


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
        algorithm: str = "priority",
        config_snapshot: Optional[dict] = None,
        parking_lot_id: Optional[str] = None,
        grid_width: int = 0,
        grid_height: int = 0,
    ):
        self.session_id = session_id
        self._simulation_factory = simulation_factory
        self.grid_data = grid_data
        self.max_timesteps = max_timesteps if max_timesteps and max_timesteps > 0 else None
        self.step_delay_ms = max(10, step_delay_ms)

        self.algorithm = algorithm
        self.config_snapshot = config_snapshot or {}
        self.parking_lot_id = parking_lot_id
        self.grid_width = grid_width
        self.grid_height = grid_height

        self.simulation = simulation_factory()
        self.websocket: Optional[WebSocket] = None
        self.status = "IDLE"
        self._task: Optional[asyncio.Task] = None
        # Plain bool flags are safe to read/write from any context (no event-loop
        # binding issues that affect asyncio.Event when created in a sync thread).
        self._paused: bool = False
        self._stopped: bool = False

        self._psutil_process = _psutil.Process() if _PSUTIL_OK else None
        self._cpu_last: Optional[float] = None
        self._mem_last_mb: Optional[float] = None
        self._cpu_peak: float = 0.0
        self._mem_peak_mb: float = 0.0
        self._cpu_sum: float = 0.0
        self._mem_sum: float = 0.0
        self._system_sample_count: int = 0
        self._machine_specs: dict = _collect_machine_specs()

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

        avg_trip = (
            sim.sum_trip_durations / sim.total_completed_trips
            if sim.total_completed_trips > 0 else None
        )
        avg_planner_ms = (
            sim.sum_planner_ms / sim.planner_call_count
            if sim.planner_call_count > 0 else None
        )

        if self._psutil_process and sim.time % 20 == 0:
            try:
                cpu = self._psutil_process.cpu_percent(interval=None)
                mem_mb = self._psutil_process.memory_info().rss / (1024 * 1024)
                self._cpu_last = round(cpu, 1)
                self._mem_last_mb = round(mem_mb, 1)
                self._system_sample_count += 1
                self._cpu_sum += cpu
                self._mem_sum += mem_mb
                if cpu > self._cpu_peak:
                    self._cpu_peak = cpu
                if mem_mb > self._mem_peak_mb:
                    self._mem_peak_mb = mem_mb
            except Exception:
                pass

        stats = {
            "total_cars": sim.config.initial_cars + sim.arriving_cars_created,
            "total_parked": sim.total_parked,
            "total_failed_plans": sim.total_failed_plans,
            "total_exited": sim.total_exited,
            "arriving_cars_spawned": sim.arriving_cars_created,
            "arriving_cars_parked": sim.arriving_cars_parked_count,
            "average_steps_to_park": avg_park,
            "average_steps_to_exit": avg_exit,
            "avg_trip_duration": avg_trip,
            "max_trip_duration": sim.max_trip_duration if sim.total_completed_trips > 0 else None,
            "min_trip_duration": sim.min_trip_duration,
            "avg_planner_ms": avg_planner_ms,
            "max_planner_ms": sim.max_planner_ms if sim.planner_call_count > 0 else None,
            "cpu_percent": self._cpu_last,
            "memory_mb": self._mem_last_mb,
        }

        await self._send({"type": "STEP", "t": sim.time, "cars": cars, "stats": stats, "events": list(sim.pending_events)})

    def build_snapshot(self, name: str = "Untitled") -> dict:
        """Build a stats snapshot dict suitable for DB persistence."""
        sim = self.simulation
        avg_park = (
            sim.sum_steps_to_park / sim.arriving_cars_parked_count
            if sim.arriving_cars_parked_count > 0 else None
        )
        avg_exit = (
            sim.sum_steps_to_exit / sim.total_exit_journeys
            if sim.total_exit_journeys > 0 else None
        )
        avg_trip = (
            sim.sum_trip_durations / sim.total_completed_trips
            if sim.total_completed_trips > 0 else None
        )
        avg_planner = (
            sim.sum_planner_ms / sim.planner_call_count
            if sim.planner_call_count > 0 else None
        )
        cpu_avg = (
            self._cpu_sum / self._system_sample_count
            if self._system_sample_count > 0 else None
        )
        mem_avg = (
            self._mem_sum / self._system_sample_count
            if self._system_sample_count > 0 else None
        )
        max_arriving = sim.config.max_arriving_cars
        if max_arriving >= 999_999:
            max_arriving = 0
        status = "COMPLETED" if self.status == "COMPLETED" else "PAUSED"
        return {
            "name": name,
            "algorithm": self.algorithm,
            "parking_lot_id": self.parking_lot_id,
            "grid_width": self.grid_width,
            "grid_height": self.grid_height,
            "config_json": json.dumps(self.config_snapshot),
            "initial_cars": sim.config.initial_cars,
            "max_arriving_cars": max_arriving,
            "total_steps": sim.time,
            "total_cars": sim.config.initial_cars + sim.arriving_cars_created,
            "total_parked": sim.total_parked,
            "total_failed_plans": sim.total_failed_plans,
            "status": status,
            "total_exited": sim.total_exited,
            "arriving_cars_spawned": sim.arriving_cars_created,
            "arriving_cars_parked": sim.arriving_cars_parked_count,
            "average_steps_to_park": avg_park,
            "average_steps_to_exit": avg_exit,
            "avg_trip_duration_steps": avg_trip,
            "max_trip_duration_steps": sim.max_trip_duration if sim.total_completed_trips > 0 else None,
            "min_trip_duration_steps": sim.min_trip_duration,
            "total_completed_trips": sim.total_completed_trips,
            "avg_planner_ms": avg_planner,
            "max_planner_ms": sim.max_planner_ms if sim.planner_call_count > 0 else None,
            "planner_call_count": sim.planner_call_count,
            "cpu_usage_avg_percent": round(cpu_avg, 1) if cpu_avg is not None else None,
            "cpu_usage_peak_percent": round(self._cpu_peak, 1) if self._system_sample_count > 0 else None,
            "memory_usage_avg_mb": round(mem_avg, 1) if mem_avg is not None else None,
            "memory_usage_peak_mb": round(self._mem_peak_mb, 1) if self._system_sample_count > 0 else None,
            "machine_specs_json": json.dumps(self._machine_specs),
        }

    async def _send_status(self, status: str):
        self.status = status
        await self._send({"type": "STATUS", "status": status})

    async def _send(self, data: dict):
        if self.websocket:
            try:
                await self.websocket.send_json(data)
            except Exception:
                pass
