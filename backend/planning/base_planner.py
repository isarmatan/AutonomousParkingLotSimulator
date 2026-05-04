from abc import ABC, abstractmethod


class BasePlanner(ABC):
    """
    Abstract interface for MAPF planners.

    All planners must implement:
      - plan_for_car   : plan a single-agent path and return success/failure
      - cancel_plan    : free any reservations held by a car
      - reservation_table : expose the underlying ReservationTable so
                            SimulationCore can perform goal-reservation bookkeeping

    Batch planners (e.g. LaCAM0) should override:
      - uses_batch_planning : return True
      - replan_all          : plan for all active cars at once
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

    @property
    def uses_batch_planning(self) -> bool:
        """
        If True, SimulationCore will call replan_all() at the start of each
        step instead of calling plan_for_car() per-car inside _advance_cars().
        Priority Planner returns False (default). LaCAM0 returns True.
        """
        return False

    def replan_all(
        self,
        active_cars: list,
        current_time: int,
        parked_positions: set,
    ) -> bool:
        """
        Batch-plan for all active cars simultaneously.

        Default implementation: loop plan_for_car() per car.
        Batch planners (LaCAM0) override this to run a MAPF solver.

        Returns True if at least one car received a path.
        """
        success = False
        for car in active_cars:
            if car.has_goal():
                ok = self.plan_for_car(car, current_time)
                success = success or ok
        return success
