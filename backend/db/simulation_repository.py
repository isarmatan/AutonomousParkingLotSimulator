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
