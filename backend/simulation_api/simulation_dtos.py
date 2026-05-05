from typing import Dict, List, Literal, Optional, Any, Tuple
from pydantic import BaseModel, Field

# --- Request DTOs ---

class SimulationRulesDTO(BaseModel):
    num_entries: int
    num_exits: int
    num_parking_spots: int

class SimulationRequest(BaseModel):
    # Grid source configuration
    source: Literal["generate", "load"]
    
    # For source="generate"
    width: Optional[int] = None
    height: Optional[int] = None
    rules: Optional[SimulationRulesDTO] = None
    
    # For source="load"
    parkingLotId: Optional[str] = None

    # Simulation parameters
    planning_horizon: int = 100
    goal_reserve_horizon: int = 200
    arrival_lambda: float = 0.3
    max_arriving_cars: int = 30
    initial_cars: int = 5
    exit_rate: float = 0.02

    # Safety stop
    max_steps: int = 1000

# --- Response DTOs ---

class TimestepStatsDTO(BaseModel):
    # Cumulative counters at this timestep
    total_cars: int
    total_parked: int
    total_failed_plans: int

    total_exited: int
    arriving_cars_spawned: int
    arriving_cars_parked: int

    # Averages at this timestep
    average_steps_to_park: Optional[float] = None
    average_steps_to_exit: Optional[float] = None

class TimestepDTO(BaseModel):
    t: int
    # cars: car_id -> [x, y]
    cars: Dict[str, List[int]]
    stats: TimestepStatsDTO

class SimulationMetaDTO(BaseModel):
    total_steps: int
    status: str = "COMPLETED"
    message: Optional[str] = None
    
    # Metrics
    total_cars: int
    total_parked: int
    total_failed_plans: int

    initial_cars_configured: int
    total_exited: int

    arriving_cars_spawned: int
    arriving_cars_parked: int

    average_steps_to_park: Optional[float] = None
    average_steps_to_exit: Optional[float] = None

class SimulationHistoryItemDTO(BaseModel):
    id: str
    name: Optional[str] = "Untitled"
    created_at: Any
    parking_lot_id: Optional[str]
    grid_width: Optional[int]
    grid_height: Optional[int]
    
    initial_cars_configured: int

    total_steps: int
    total_cars: int
    total_parked: int
    total_failed_plans: int
    status: str

    total_exited: int
    arriving_cars_spawned: int
    arriving_cars_parked: int

    average_steps_to_park: Optional[float]
    average_steps_to_exit: Optional[float]

class SimulationSaveRequest(BaseModel):
    name: str
    request: SimulationRequest
    meta: SimulationMetaDTO
    grid_width: int
    grid_height: int

class SimulationResponse(BaseModel):
    grid: Dict[str, Any]
    timesteps: List[TimestepDTO]
    meta: SimulationMetaDTO


# --- Live Simulation DTOs ---

class LiveSimulationRequest(BaseModel):
    # Grid source configuration (same as SimulationRequest)
    source: Literal["generate", "load"]

    # For source="generate"
    width: Optional[int] = None
    height: Optional[int] = None
    rules: Optional[SimulationRulesDTO] = None

    # For source="load"
    parkingLotId: Optional[str] = None

    # Simulation parameters
    planning_horizon: int = 50
    goal_reserve_horizon: int = 200
    arrival_lambda: float = 0.3
    exit_rate: float = 0.02             # per-car probability per step to leave
    initial_cars: int = 5               # cars present at t=0 (all start parked)
    max_arriving_cars: int = 0          # 0 = unlimited

    # Lifelong controls
    max_timesteps: int = 0              # 0 = run until stopped by client
    step_delay_ms: int = 100            # milliseconds between timesteps
    algorithm: str = "priority"         # "priority" | "lacam0" (Phase 3)


class SessionInitResponse(BaseModel):
    session_id: str
    grid: Dict[str, Any]
