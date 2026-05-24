from typing import Dict, List, Literal, Optional, Any, Tuple
from pydantic import BaseModel, ConfigDict, Field

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

    # Trip duration
    avg_trip_duration: Optional[float] = None
    max_trip_duration: Optional[int] = None
    min_trip_duration: Optional[int] = None

    # Planner runtime
    avg_planner_ms: Optional[float] = None
    max_planner_ms: Optional[float] = None

    # System resources
    cpu_percent: Optional[float] = None
    memory_mb: Optional[float] = None

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
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: Optional[str] = "Untitled"
    created_at: Any
    parking_lot_id: Optional[str]
    grid_width: Optional[int]
    grid_height: Optional[int]

    initial_cars_configured: int = Field(default=0, validation_alias="initial_active_cars_configured")

    total_steps: int
    total_cars: int
    total_parked: int
    total_failed_plans: int
    status: str

    total_exited: int = Field(default=0, validation_alias="initial_active_cars_exited")
    arriving_cars_spawned: int
    arriving_cars_parked: int

    average_steps_to_park: Optional[float]
    average_steps_to_exit: Optional[float]

    algorithm: Optional[str] = None
    avg_trip_duration_steps: Optional[float] = None
    max_trip_duration_steps: Optional[int] = None
    min_trip_duration_steps: Optional[int] = None
    total_completed_trips: Optional[int] = None
    avg_planner_ms: Optional[float] = None
    max_planner_ms: Optional[float] = None
    planner_call_count: Optional[int] = None
    cpu_usage_avg_percent: Optional[float] = None
    cpu_usage_peak_percent: Optional[float] = None
    memory_usage_avg_mb: Optional[float] = None
    memory_usage_peak_mb: Optional[float] = None
    machine_specs_json: Optional[str] = None

class SnapshotRequest(BaseModel):
    name: str = "Untitled"

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


# --- Headless Simulation DTOs ---

class HeadlessSimulationRequest(BaseModel):
    source: Literal["generate", "load"]
    width: Optional[int] = None
    height: Optional[int] = None
    rules: Optional[SimulationRulesDTO] = None
    parkingLotId: Optional[str] = None

    planning_horizon: int = 50
    goal_reserve_horizon: int = 200
    arrival_lambda: float = 0.3
    exit_rate: float = 0.02
    initial_cars: int = 5
    max_arriving_cars: int = 0  # 0 = unlimited
    algorithm: str = "priority"
    max_steps: int  # required — validated in endpoint


class HeadlessResultDTO(BaseModel):
    mode: str = "headless"
    algorithm: str
    max_steps: int
    completed_steps: int
    stopped_reason: str  # "max_steps_reached" | "all_cars_completed"
    status: str          # "COMPLETED" | "MAX_STEPS_REACHED"

    grid_width: int
    grid_height: int
    parking_lot_id: Optional[str] = None

    initial_cars_configured: int
    max_arriving_cars_configured: int
    total_cars: int
    total_parked: int
    total_failed_plans: int
    total_exited: int
    arriving_cars_spawned: int
    arriving_cars_parked: int

    average_steps_to_park: Optional[float] = None
    average_steps_to_exit: Optional[float] = None
    avg_trip_duration_steps: Optional[float] = None
    max_trip_duration_steps: Optional[int] = None
    min_trip_duration_steps: Optional[int] = None
    total_completed_trips: int = 0

    avg_planner_ms: Optional[float] = None
    max_planner_ms: Optional[float] = None
    planner_call_count: int = 0

    cpu_usage_avg_percent: Optional[float] = None
    cpu_usage_peak_percent: Optional[float] = None
    memory_usage_avg_mb: Optional[float] = None
    memory_usage_peak_mb: Optional[float] = None
    machine_specs: Optional[Dict[str, Any]] = None


class HeadlessSaveRequest(BaseModel):
    name: str = "Untitled"
    result: HeadlessResultDTO
    config_json: Optional[str] = None


# --- Comparison Simulation DTOs ---

class ComparisonRequest(BaseModel):
    source: Literal["generate", "load"]
    width: Optional[int] = None
    height: Optional[int] = None
    rules: Optional[SimulationRulesDTO] = None
    parkingLotId: Optional[str] = None

    planning_horizon: int = 50
    goal_reserve_horizon: int = 200
    arrival_lambda: float = 0.3
    exit_rate: float = 0.02
    initial_cars: int = 5
    max_arriving_cars: int = 0
    max_steps: int  # required

    algorithms: List[str]  # exactly 2 (extensible for future 3rd algorithm)


class ComparisonResultDTO(BaseModel):
    results: List[HeadlessResultDTO]
