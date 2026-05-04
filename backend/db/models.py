import datetime as dt

from sqlalchemy import DateTime, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from .database import Base


class ParkingLotModel(Base):
    """Persisted (globally shared) parking lot definition.

    This is intentionally a *simple* table:
    - The grid is stored as JSON text in `grid_json` (width/height + cells),
      which avoids a complex relational schema for every cell.
    - `name` is unique so the frontend can display a global list of saved lots
      and users can select by name.
    """

    __tablename__ = "parking_lots"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    name: Mapped[str] = mapped_column(String(120), unique=True, index=True, nullable=False)
    grid_json: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, default=dt.datetime.utcnow, nullable=False)


class SimulationResultModel(Base):
    """Persisted record of a simulation run."""
    __tablename__ = "simulation_results"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, default=dt.datetime.utcnow, nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=True)
    
    # Context
    parking_lot_id: Mapped[str] = mapped_column(String(36), nullable=True) # If loaded from saved lot
    grid_width: Mapped[int] = mapped_column(nullable=True)
    grid_height: Mapped[int] = mapped_column(nullable=True)

    # Config Summary
    initial_active_cars_configured: Mapped[int] = mapped_column(nullable=False)
    max_arriving_cars_configured: Mapped[int] = mapped_column(nullable=False)
    
    # High Level Stats
    total_steps: Mapped[int] = mapped_column(nullable=False)
    total_cars: Mapped[int] = mapped_column(nullable=False)
    total_parked: Mapped[int] = mapped_column(nullable=False)
    total_failed_plans: Mapped[int] = mapped_column(nullable=False)
    status: Mapped[str] = mapped_column(String(50), nullable=False)
    
    # Detailed Stats
    initial_active_cars_exited: Mapped[int] = mapped_column(nullable=False)
    arriving_cars_spawned: Mapped[int] = mapped_column(nullable=False)
    arriving_cars_parked: Mapped[int] = mapped_column(nullable=False)
    
    average_steps_to_park: Mapped[float] = mapped_column(nullable=True)
    average_steps_to_exit: Mapped[float] = mapped_column(nullable=True)

