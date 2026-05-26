from typing import List, Tuple, Optional

Position = Tuple[int, int]
TimedPosition = Tuple[int, int, int]  # (x, y, t)

class Car:
    def __init__(
        self,
        car_id: int,
        start: Position,
        intent: str,
        goal: Optional[Position] = None,
        priority: Optional[int] = None
    ):
        self.car_id = car_id
        self.start = start
        self.goal = goal
        self.priority = priority
        self.intent = intent   # "PARK" or "EXIT"
        self.path: List[TimedPosition] = []
        self.current_step = 0 
        self._position = start
        self.last_plan_fail_time = -1000 # Initialize far in past
        self.plan_fail_count = 0
        self.blocked_count = 0

        # Metrics
        self.spawn_time: int = -1
        self.park_time: Optional[int] = None
        self.exit_time: Optional[int] = None
        self.is_initial: bool = False

    def has_goal(self) -> bool:
        return self.goal is not None

    def set_path(self, path: List[TimedPosition]):
        self.path = path
        self.current_step = 0 
        # Optionally reset position if path starts now? 
        # But usually planning starts from current position.

    def has_path(self) -> bool:
        return len(self.path) > 0

    def is_finished(self) -> bool:
        return self.current_step >= len(self.path)

    def get_position_at_time(self, t: int) -> Optional[Position]:
        if not self.path:
            return None
        for x, y, time in self.path:
            if time == t:
                return (x, y)
        return None

    def step(self, current_time: int) -> Optional[Position]:
        target_time = current_time + 1
        
        # 1. Fast forward if we fell behind
        while self.current_step < len(self.path):
             x, y, t = self.path[self.current_step]
             if t < target_time:
                 self.current_step += 1
             else:
                 break
                 
        # 2. Check current match
        if self.current_step < len(self.path):
             x, y, t = self.path[self.current_step]
             
             if t == target_time:
                 # Perfect match
                 self._position = (x, y)
                 self.current_step += 1
                 return (x, y)
             
             elif t > target_time:
                 # Future path, stay put
                 return self._position
        
        # Finished path (or no path)
        if self.has_path() and self.current_step >= len(self.path):
             # Path completed
             return None
             
        return self._position

    def peek_at_next_step(self, current_time: int) -> Optional[Position]:
        """
        Look at where the car *wants* to be at current_time + 1
        without changing state.
        """
        target_time = current_time + 1
        idx = self.current_step
        
        # Fast forward simulation (local only)
        while idx < len(self.path):
             x, y, t = self.path[idx]
             if t < target_time:
                 idx += 1
             else:
                 break
        
        if idx < len(self.path):
             x, y, t = self.path[idx]
             if t == target_time:
                 return (x, y)
             # If t > target_time, we stay put
             return self._position
             
        return None

    def clear_path(self):
        self.path = []
        self.current_step = 0

    @property
    def current_position(self) -> Position:
        """
        Returns the car's current spatial position.
        """
        return self._position