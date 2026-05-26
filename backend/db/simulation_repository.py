import uuid
from typing import List, Optional
from sqlalchemy import select
from sqlalchemy.orm import Session
from .models import SimulationResultModel
from simulation_api.simulation_dtos import SimulationMetaDTO, SimulationRequest

class SimulationRepository:
    def __init__(self, db: Session):
        self._db = db

    def save_result(self, req: SimulationRequest, meta: SimulationMetaDTO, parking_lot_id: Optional[str] = None, grid_width: int = 0, grid_height: int = 0, name: Optional[str] = "Untitled") -> SimulationResultModel:
        model = SimulationResultModel(
            id=str(uuid.uuid4()),
            name=name,
            
            # Context
            parking_lot_id=parking_lot_id,
            grid_width=grid_width,
            grid_height=grid_height,

            # Config Summary
            initial_active_cars_configured=req.initial_active_cars,
            max_arriving_cars_configured=req.max_arriving_cars,

            # High Level Stats
            total_steps=meta.total_steps,
            total_cars=meta.total_cars,
            total_parked=meta.total_parked,
            total_failed_plans=meta.total_failed_plans,
            status=meta.status,

            # Detailed Stats
            initial_active_cars_exited=meta.initial_active_cars_exited,
            arriving_cars_spawned=meta.arriving_cars_spawned,
            arriving_cars_parked=meta.arriving_cars_parked,

            average_steps_to_park=meta.average_steps_to_park,
            average_steps_to_exit=meta.average_steps_to_exit
        )
        self._db.add(model)
        self._db.commit()
        self._db.refresh(model)
        return model

    def save_snapshot(self, data: dict) -> SimulationResultModel:
        """Persist a live-simulation snapshot to DB."""
        model = SimulationResultModel(
            id=str(uuid.uuid4()),
            name=data.get("name", "Untitled"),
            parking_lot_id=data.get("parking_lot_id"),
            grid_width=data.get("grid_width", 0),
            grid_height=data.get("grid_height", 0),
            initial_active_cars_configured=data.get("initial_cars", 0),
            max_arriving_cars_configured=data.get("max_arriving_cars", 0),
            total_steps=data.get("total_steps", 0),
            total_cars=data.get("total_cars", 0),
            total_parked=data.get("total_parked", 0),
            total_failed_plans=data.get("total_failed_plans", 0),
            status=data.get("status", "PAUSED"),
            initial_active_cars_exited=data.get("total_exited", 0),
            arriving_cars_spawned=data.get("arriving_cars_spawned", 0),
            arriving_cars_parked=data.get("arriving_cars_parked", 0),
            average_steps_to_park=data.get("average_steps_to_park"),
            average_steps_to_exit=data.get("average_steps_to_exit"),
            algorithm=data.get("algorithm"),
            config_json=data.get("config_json"),
            avg_trip_duration_steps=data.get("avg_trip_duration_steps"),
            max_trip_duration_steps=data.get("max_trip_duration_steps"),
            min_trip_duration_steps=data.get("min_trip_duration_steps"),
            total_completed_trips=data.get("total_completed_trips"),
            avg_planner_ms=data.get("avg_planner_ms"),
            max_planner_ms=data.get("max_planner_ms"),
            planner_call_count=data.get("planner_call_count"),
            cpu_usage_avg_percent=data.get("cpu_usage_avg_percent"),
            cpu_usage_peak_percent=data.get("cpu_usage_peak_percent"),
            memory_usage_avg_mb=data.get("memory_usage_avg_mb"),
            memory_usage_peak_mb=data.get("memory_usage_peak_mb"),
            machine_specs_json=data.get("machine_specs_json"),
        )
        self._db.add(model)
        self._db.commit()
        self._db.refresh(model)
        return model

    def list_history(self, limit: int = 50) -> List[SimulationResultModel]:
        stmt = select(SimulationResultModel).order_by(SimulationResultModel.created_at.desc()).limit(limit)
        return list(self._db.scalars(stmt))

    def delete_result(self, simulation_id: str) -> bool:
        stmt = select(SimulationResultModel).where(SimulationResultModel.id == simulation_id)
        result = self._db.scalar(stmt)
        if result:
            self._db.delete(result)
            self._db.commit()
            return True
        return False
