# core/lns2_parking_manager.py
from typing import Optional, Tuple

from core.parking_manager import ParkingManager

Position = Tuple[int, int]


class LNS2ParkingManager(ParkingManager):
    """
    LNS2-specific parking manager.

    Identical to ParkingManager for PARK intent.
    For EXIT intent, delegates goal assignment to a GhostExitManager so that
    every exiting car receives a UNIQUE ghost planner goal instead of the
    shared physical exit cell — a requirement of the LNS2 solver.

    The base ParkingManager (used by all other algorithms) is NOT modified.
    """

    def __init__(self, grid, parking_cells, exit_cells, entry_cells, ghost_exit_manager):
        super().__init__(grid, parking_cells, exit_cells, entry_cells)
        self.ghost_exit_manager = ghost_exit_manager

    def assign_goal(self, car, current_time) -> Optional[Position]:
        if car.intent == "PARK":
            return self.choose_free_parking_spot(car)

        if car.intent == "EXIT":
            if self.ghost_exit_manager is not None:
                return self.ghost_exit_manager.assign_ghost_goal(car)
            return self.choose_exit_cell(car)

        return None
