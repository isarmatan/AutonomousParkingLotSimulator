import json
from typing import List, Dict, Any
from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session

from core.simulation_core import SimulationCore, SimulationConfig
from core.parking_manager import ParkingManager
from planning.priority_planner import PriorityPlanner
from planning.reservation_table import ReservationTable
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
    SimulationSaveRequest
)

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
    requested_initial_cars = req.initial_parked_cars + req.initial_active_cars
    
    if requested_initial_cars > total_spots:
        raise HTTPException(
            status_code=400,
            detail=f"Requested {requested_initial_cars} initial cars (parked + active), but grid only has {total_spots} parking spots."
        )

    parking_manager = ParkingManager(
        grid=grid,
        parking_cells=parking_cells,
        exit_cells=exit_cells,
        entry_cells=entry_cells
    )
    
    reservation_table = ReservationTable()
    
    priority_planner = PriorityPlanner(
        grid=grid,
        reservation_table=reservation_table,
        planning_horizon=req.planning_horizon
    )
    
    config = SimulationConfig(
        planning_horizon=req.planning_horizon,
        goal_reserve_horizon=req.goal_reserve_horizon,
        arrival_lambda=req.arrival_lambda,
        max_arriving_cars=req.max_arriving_cars,
        initial_parked_cars=req.initial_parked_cars,
        initial_active_cars=req.initial_active_cars,
        initial_active_exit_rate=req.initial_active_exit_rate
    )
    
    simulation = SimulationCore(
        grid=grid,
        parking_manager=parking_manager,
        priority_planner=priority_planner,
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
        if simulation.initial_active_cars_exited_count > 0:
            avg_exit = simulation.sum_steps_to_exit / simulation.initial_active_cars_exited_count

        stats = TimestepStatsDTO(
            total_cars=simulation.total_arrived + simulation.config.initial_parked_cars, # Total cars involved so far
            total_parked=simulation.total_parked,
            total_failed_plans=simulation.total_failed_plans,
            
            initial_active_cars_exited=simulation.initial_active_cars_exited_count,
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
    if simulation.initial_active_cars_exited_count > 0:
        avg_exit = simulation.sum_steps_to_exit / simulation.initial_active_cars_exited_count

    meta = SimulationMetaDTO(
        total_steps=simulation.time,
        total_cars=simulation.total_arrived + simulation.total_parked, # Approximation of total involved
        total_parked=simulation.total_parked,
        total_failed_plans=simulation.total_failed_plans,
        status=status,
        message=message,
        
        # New Metrics
        initial_active_cars_configured=req.initial_active_cars,
        initial_active_cars_exited=simulation.initial_active_cars_exited_count,
        
        max_arriving_cars_configured=req.max_arriving_cars,
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
