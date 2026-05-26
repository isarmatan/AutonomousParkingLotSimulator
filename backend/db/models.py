import datetime as dt
from typing import Optional

from sqlalchemy import DateTime, Float, Integer, String, Text
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
    
    average_steps_to_park: Mapped[Optional[float]] = mapped_column(nullable=True)
    average_steps_to_exit: Mapped[Optional[float]] = mapped_column(nullable=True)

    # Extended statistics (nullable — old records have NULL here)
    algorithm: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    config_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    avg_trip_duration_steps: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    max_trip_duration_steps: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    min_trip_duration_steps: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    total_completed_trips: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    avg_planner_ms: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    max_planner_ms: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    planner_call_count: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    cpu_usage_avg_percent: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    cpu_usage_peak_percent: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    memory_usage_avg_mb: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    memory_usage_peak_mb: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    machine_specs_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

