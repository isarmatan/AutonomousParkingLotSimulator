import json
import uuid
from typing import List, Dict, Any
from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session

from core.simulation_core import SimulationCore, SimulationConfig
from core.lacam0_simulation_core import LaCAM0SimulationCore
from core.parking_manager import ParkingManager
from core.lacam0_parking_manager import LaCAM0ParkingManager
from planning.ghost_exit_manager import GhostExitManager
from planning import planner_manager
from planning.reservation_table import ReservationTable
from planning.lacam0_batch_planner import LaCAM0BatchPlanner
from generator.grid import Grid
from generator.cell import CellType
from generator.parking_lot_generator import ParkingLotGenerator, GeneratorRules

from db.deps import get_db
from db.parking_lot_repository import ParkingLotRepository, grid_to_json_dict
from db.simulation_repository import SimulationRepository

from .simulation_dtos import (
    SimulationRequest,
    SimulationResponse,
    TimestepDTO,
    TimestepStatsDTO,
    SimulationMetaDTO,
    SimulationHistoryItemDTO,
    SimulationSaveRequest,
    LiveSimulationRequest,
    SessionInitResponse,
)
from .simulation_session import SimulationSession
from . import simulation_manager

router = APIRouter(prefix="/simulation", tags=["simulation"])

@router.get("/history", response_model=List[SimulationHistoryItemDTO])
def get_simulation_history(limit: int = 50, db: Session = Depends(get_db)):
    repo = SimulationRepository(db)
    return repo.list_history(limit)

@router.post("/save", response_model=SimulationHistoryItemDTO)
def save_simulation_result(req: SimulationSaveRequest, db: Session = Depends(get_db)):
    repo = SimulationRepository(db)
    
    parking_lot_id = None
    if req.request.source == "load":
        parking_lot_id = req.request.parkingLotId

    saved_record = repo.save_result(
        req=req.request,
        meta=req.meta,
        parking_lot_id=parking_lot_id,
        grid_width=req.grid_width,
        grid_height=req.grid_height,
        name=req.name
    )
    
    # Return as DTO
    return saved_record

@router.delete("/{simulation_id}", response_model=Dict[str, bool])
def delete_simulation_result(simulation_id: str, db: Session = Depends(get_db)):
    repo = SimulationRepository(db)
    success = repo.delete_result(simulation_id)
    if not success:
        raise HTTPException(status_code=404, detail="Simulation result not found")
    return {"ok": True}

def _extract_cells(grid: Grid):
    parking_cells = []
    exit_cells = []
    entry_cells = []

    for row in grid.cells:
        for cell in row:
            if cell.type == CellType.PARKING:
                parking_cells.append((cell.x, cell.y))
            elif cell.type == CellType.EXIT:
                exit_cells.append((cell.x, cell.y))
            elif cell.type == CellType.ENTRY:
                entry_cells.append((cell.x, cell.y))

    return parking_cells, exit_cells, entry_cells

def _acquire_grid(req, db: Session):
    """Shared helper: build a Grid from a generate or load request."""
    if req.source == "generate":
        if not req.width or not req.height or not req.rules:
            raise HTTPException(
                status_code=422,
                detail="Width, height, and rules are required for 'generate' source",
            )
        rules = GeneratorRules(
            num_entries=req.rules.num_entries,
            num_exits=req.rules.num_exits,
            num_parking_spots=req.rules.num_parking_spots,
        )
        try:
            generator = ParkingLotGenerator(req.width, req.height, rules)
            return generator.generate()
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Generation failed: {str(e)}")

    elif req.source == "load":
        if not req.parkingLotId:
            raise HTTPException(
                status_code=422,
                detail="parkingLotId is required for 'load' source",
            )
        repo = ParkingLotRepository(db)
        grid = repo.load_grid(req.parkingLotId)
        if grid is None:
            raise HTTPException(status_code=404, detail="Parking lot not found")
        return grid

    raise HTTPException(status_code=422, detail="Invalid source")


@router.post("/start", response_model=SessionInitResponse)
def start_simulation(req: LiveSimulationRequest, db: Session = Depends(get_db)):
    """
    Create a live simulation session.
    Returns a session_id and the grid JSON.
    The client should then open ws://.../simulation/ws/{session_id}.
    """
    grid = _acquire_grid(req, db)

    parking_cells, exit_cells, entry_cells = _extract_cells(grid)
    total_spots = len(parking_cells)

    if req.initial_cars > total_spots:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Requested {req.initial_cars} initial cars, "
                f"but grid only has {total_spots} parking spots."
            ),
        )

    # Treat max_arriving_cars=0 as unlimited
    effective_max_arriving = req.max_arriving_cars if req.max_arriving_cars > 0 else 999_999

    def simulation_factory():
        cfg = SimulationConfig(
            planning_horizon=req.planning_horizon,
            goal_reserve_horizon=req.goal_reserve_horizon,
            arrival_lambda=req.arrival_lambda,
            exit_rate=req.exit_rate,
            initial_cars=req.initial_cars,
            max_arriving_cars=effective_max_arriving,
        )
        if req.algorithm == "lacam0":
            ghost_mgr = GhostExitManager(grid.width, grid.height, exit_cells)
            pm = LaCAM0ParkingManager(
                grid=grid,
                parking_cells=parking_cells,
                exit_cells=exit_cells,
                entry_cells=entry_cells,
                ghost_exit_manager=ghost_mgr,
            )
            batch_planner = LaCAM0BatchPlanner()
            return LaCAM0SimulationCore(
                grid=grid,
                parking_manager=pm,
                config=cfg,
                batch_planner=batch_planner,
                ghost_exit_manager=ghost_mgr,
            )
        pm = ParkingManager(
            grid=grid,
            parking_cells=parking_cells,
            exit_cells=exit_cells,
            entry_cells=entry_cells,
        )
        rt = ReservationTable()
        planner = planner_manager.create_planner(
            algorithm=req.algorithm,
            grid=grid,
            reservation_table=rt,
            planning_horizon=req.planning_horizon,
        )
        return SimulationCore(
            grid=grid,
            parking_manager=pm,
            planner=planner,
            config=cfg,
        )

    session_id = str(uuid.uuid4())
    session = SimulationSession(
        session_id=session_id,
        simulation_factory=simulation_factory,
        grid_data=grid_to_json_dict(grid),
        max_timesteps=req.max_timesteps,
        step_delay_ms=req.step_delay_ms,
    )
    simulation_manager.add_session(session)

    return SessionInitResponse(session_id=session_id, grid=grid_to_json_dict(grid))


@router.post("/run", response_model=SimulationResponse)
def run_simulation(req: SimulationRequest, db: Session = Depends(get_db)):
    # 1. Acquire Grid
    grid: Grid = None
    
    if req.source == "generate":
        if not req.width or not req.height or not req.rules:
            raise HTTPException(
                status_code=422, 
                detail="Width, height, and rules are required for 'generate' source"
            )
        
        rules = GeneratorRules(
            num_entries=req.rules.num_entries,
            num_exits=req.rules.num_exits,
            num_parking_spots=req.rules.num_parking_spots
        )
        try:
            generator = ParkingLotGenerator(req.width, req.height, rules)
            grid = generator.generate()
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Generation failed: {str(e)}")
            
    elif req.source == "load":
        if not req.parkingLotId:
            raise HTTPException(
                status_code=422, 
                detail="parkingLotId is required for 'load' source"
            )
        
        repo = ParkingLotRepository(db)
        grid = repo.load_grid(req.parkingLotId)
        if grid is None:
            raise HTTPException(status_code=404, detail="Parking lot not found")
            
    else:
        raise HTTPException(status_code=422, detail="Invalid source")

    # 2. Setup Simulation Components
    parking_cells, exit_cells, entry_cells = _extract_cells(grid)
    
    total_spots = len(parking_cells)
    if req.initial_cars > total_spots:
        raise HTTPException(
            status_code=400,
            detail=f"Requested {req.initial_cars} initial cars, but grid only has {total_spots} parking spots."
        )

    parking_manager = ParkingManager(
        grid=grid,
        parking_cells=parking_cells,
        exit_cells=exit_cells,
        entry_cells=entry_cells
    )
    
    reservation_table = ReservationTable()

    planner = planner_manager.create_planner(
        algorithm="priority",
        grid=grid,
        reservation_table=reservation_table,
        planning_horizon=req.planning_horizon,
    )

    config = SimulationConfig(
        planning_horizon=req.planning_horizon,
        goal_reserve_horizon=req.goal_reserve_horizon,
        arrival_lambda=req.arrival_lambda,
        exit_rate=req.exit_rate,
        initial_cars=req.initial_cars,
        max_arriving_cars=req.max_arriving_cars,
    )
    
    simulation = SimulationCore(
        grid=grid,
        parking_manager=parking_manager,
        planner=planner,
        config=config
    )
    
    # 3. Run Loop
    timesteps: List[TimestepDTO] = []
    
    # Initial state (t=0)
    # SimulationCore initialized cars at t=0 in __init__, so we capture it before stepping.
    
    def capture_step():
        pos_map = simulation.get_positions_snapshot()
        # Convert keys to str and values to list for JSON
        cars_dict = {str(cid): [pos[0], pos[1]] for cid, pos in pos_map.items()}
        
        # Calculate Current Stats
        avg_park = 0.0
        if simulation.arriving_cars_parked_count > 0:
            avg_park = simulation.sum_steps_to_park / simulation.arriving_cars_parked_count

        avg_exit = 0.0
        if simulation.total_exit_journeys > 0:
            avg_exit = simulation.sum_steps_to_exit / simulation.total_exit_journeys

        stats = TimestepStatsDTO(
            total_cars=simulation.config.initial_cars + simulation.arriving_cars_created,
            total_parked=simulation.total_parked,
            total_failed_plans=simulation.total_failed_plans,
            total_exited=simulation.total_exited,
            arriving_cars_spawned=simulation.arriving_cars_created,
            arriving_cars_parked=simulation.arriving_cars_parked_count,
            average_steps_to_park=avg_park,
            average_steps_to_exit=avg_exit
        )

        timesteps.append(TimestepDTO(t=simulation.time, cars=cars_dict, stats=stats))

    capture_step()
    
    # Run loop similar to SimulationCore.run() but with step cap
    completed = False
    for _ in range(req.max_steps):
        simulation.step()
        capture_step()
        
        # Termination check
        if not simulation.active_cars:
            if simulation.arriving_cars_created >= config.max_arriving_cars:
                completed = True
                break
            if config.arrival_lambda == 0:
                completed = True
                break
                
    # 4. Construct Response
    status = "COMPLETED" if completed else "MAX_STEPS_REACHED"
    message = None
    if not completed:
        message = f"Simulation stopped after reaching max_steps ({req.max_steps}) without completing all tasks."

    avg_park = 0.0
    if simulation.arriving_cars_parked_count > 0:
        avg_park = simulation.sum_steps_to_park / simulation.arriving_cars_parked_count

    avg_exit = 0.0
    if simulation.total_exit_journeys > 0:
        avg_exit = simulation.sum_steps_to_exit / simulation.total_exit_journeys

    meta = SimulationMetaDTO(
        total_steps=simulation.time,
        total_cars=simulation.config.initial_cars + simulation.arriving_cars_created,
        total_parked=simulation.total_parked,
        total_failed_plans=simulation.total_failed_plans,
        status=status,
        message=message,
        initial_cars_configured=req.initial_cars,
        total_exited=simulation.total_exited,
        arriving_cars_spawned=simulation.arriving_cars_created,
        arriving_cars_parked=simulation.arriving_cars_parked_count,
        average_steps_to_park=avg_park,
        average_steps_to_exit=avg_exit
    )
    
    # 5. Persist Result -> REMOVED (Moved to manual save endpoint)
    # sim_repo = SimulationRepository(db)
    # sim_repo.save_result(...)
    
    return SimulationResponse(
        grid=grid_to_json_dict(grid),
        timesteps=timesteps,
        meta=meta
    )
