from abc import ABC, abstractmethod


class BasePlanner(ABC):
    """
    Abstract interface for MAPF planners.

    All planners must implement:
      - plan_for_car   : plan a single-agent path and return success/failure
      - cancel_plan    : free any reservations held by a car
      - reservation_table : expose the underlying ReservationTable so
                            SimulationCore can perform goal-reservation bookkeeping
    """

    @abstractmethod
    def plan_for_car(
        self,
        car,
        current_time: int,
        obstacles=None,
        obstacle_persistence: int = 20,
    ) -> bool:
        """
        Compute and attach a path for *car* starting at *current_time*.
        Returns True on success, False if no path could be found.
        """

    @abstractmethod
    def cancel_plan(self, car) -> None:
        """
        Cancel the current plan for *car*, releasing its reserved cells.
        """

    @property
    @abstractmethod
    def reservation_table(self):
        """
        The ReservationTable used internally by this planner.
        SimulationCore uses it directly for goal-cell bookkeeping.
        """
