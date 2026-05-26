import sys
from pathlib import Path
import tkinter as tk
from tkinter import ttk, messagebox

ROOT = Path(__file__).resolve().parent
sys.path.append(str(ROOT))

from core.simulation_core import SimulationCore, SimulationConfig
from core.parking_manager import ParkingManager
from planning.priority_planner import PriorityPlanner
from planning.reservation_table import ReservationTable
from generator.cell import CellType
from generator.parking_lot_generator import ParkingLotGenerator, GeneratorRules


def _extract_cells(grid):
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


def _grid_to_ascii(grid) -> str:
    mapping = {
        CellType.WALL: "#",
        CellType.ROAD: ".",
        CellType.PARKING: "P",
        CellType.ENTRY: "E",
        CellType.EXIT: "X",
    }

    lines = []
    for y in range(grid.height):
        row_chars = []
        for x in range(grid.width):
            row_chars.append(mapping.get(grid.get_cell(x, y).type, "?"))
        lines.append("".join(row_chars))
    return "\n".join(lines)


class StepperApp:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("Parking Simulation Stepper")

        self.sim = None
        self.grid = None
        self.log_path = None
        self.initial_exit_ids = set()
        self._is_over = False
        self._animating = False

        self.cell_size = 32
        self.margin = 10
        self.canvas = None
        self.canvas_items = {}

        self._build_ui()

    def _build_ui(self):
        frm = ttk.Frame(self.root, padding=12)
        frm.grid(row=0, column=0, sticky="nsew")

        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)

        frm.columnconfigure(0, weight=0)
        frm.columnconfigure(1, weight=1)
        frm.rowconfigure(0, weight=1)

        left = ttk.Frame(frm)
        left.grid(row=0, column=0, sticky="ns")
        left.columnconfigure(1, weight=1)

        right = ttk.Frame(frm)
        right.grid(row=0, column=1, sticky="nsew", padx=(12, 0))
        right.columnconfigure(0, weight=1)
        right.rowconfigure(0, weight=1)

        self.vars = {
            "seed": tk.StringVar(value="123"),
            "log_file": tk.StringVar(value="stepper_log.txt"),
            "width": tk.StringVar(value="15"),
            "height": tk.StringVar(value="10"),
            "num_entries": tk.StringVar(value="1"),
            "num_exits": tk.StringVar(value="1"),
            "num_parking_spots": tk.StringVar(value="25"),
            "planning_horizon": tk.StringVar(value="80"),
            "goal_reserve_horizon": tk.StringVar(value="200"),
            "arrival_lambda": tk.StringVar(value="0.3"),
            "max_arriving_cars": tk.StringVar(value="5"),
            "initial_parked_cars": tk.StringVar(value="4"),
            "initial_active_cars": tk.StringVar(value="3"),
            "initial_active_exit_rate": tk.StringVar(value="1.0"),
        }

        row = 0
        ttk.Label(left, text="Config").grid(row=row, column=0, columnspan=2, sticky="w")
        row += 1

        for key, label in [
            ("seed", "Seed"),
            ("log_file", "Log file"),
            ("width", "Grid width"),
            ("height", "Grid height"),
            ("num_entries", "#Entries"),
            ("num_exits", "#Exits"),
            ("num_parking_spots", "#Parking spots"),
            ("planning_horizon", "Planning horizon"),
            ("goal_reserve_horizon", "Goal reserve horizon"),
            ("arrival_lambda", "Arrival lambda"),
            ("max_arriving_cars", "Max arriving cars"),
            ("initial_parked_cars", "Initial parked cars"),
            ("initial_active_cars", "Initial active cars"),
            ("initial_active_exit_rate", "Initial exit rate (0-1)"),
        ]:
            ttk.Label(left, text=label).grid(row=row, column=0, sticky="w")
            ttk.Entry(left, textvariable=self.vars[key]).grid(row=row, column=1, sticky="ew")
            row += 1

        btns = ttk.Frame(left)
        btns.grid(row=row, column=0, columnspan=2, sticky="ew", pady=(10, 0))
        btns.columnconfigure(0, weight=1)
        btns.columnconfigure(1, weight=1)
        btns.columnconfigure(2, weight=1)

        ttk.Button(btns, text="Initialize", command=self.on_initialize).grid(row=0, column=0, sticky="ew")
        self.next_btn = ttk.Button(btns, text="Next Step", command=self.on_next_step, state="disabled")
        self.next_btn.grid(row=0, column=1, sticky="ew")
        ttk.Button(btns, text="Log Current State", command=self.on_log_state).grid(row=0, column=2, sticky="ew")

        ttk.Button(btns, text="Compute Capacity", command=self.on_compute_capacity).grid(
            row=1, column=0, columnspan=3, sticky="ew", pady=(6, 0)
        )

        row += 1

        self.status_var = tk.StringVar(value="Not initialized")
        ttk.Label(left, textvariable=self.status_var).grid(row=row, column=0, columnspan=2, sticky="w", pady=(10, 0))

        self.canvas = tk.Canvas(right, bg="white", highlightthickness=1, highlightbackground="#cccccc")
        xscroll = ttk.Scrollbar(right, orient="horizontal", command=self.canvas.xview)
        yscroll = ttk.Scrollbar(right, orient="vertical", command=self.canvas.yview)
        self.canvas.configure(xscrollcommand=xscroll.set, yscrollcommand=yscroll.set)
        self.canvas.grid(row=0, column=0, sticky="nsew")
        yscroll.grid(row=0, column=1, sticky="ns")
        xscroll.grid(row=1, column=0, sticky="ew")

    def _parse_int(self, key: str) -> int:
        return int(self.vars[key].get().strip())

    def _parse_float(self, key: str) -> float:
        return float(self.vars[key].get().strip())

    def on_initialize(self):
        try:
            seed = self._parse_int("seed")
            log_file = self.vars["log_file"].get().strip()
            width = self._parse_int("width")
            height = self._parse_int("height")

            rules_cfg = dict(
                num_entries=self._parse_int("num_entries"),
                num_exits=self._parse_int("num_exits"),
                num_parking_spots=self._parse_int("num_parking_spots"),
            )

            sim_cfg = dict(
                planning_horizon=self._parse_int("planning_horizon"),
                goal_reserve_horizon=self._parse_int("goal_reserve_horizon"),
                arrival_lambda=self._parse_float("arrival_lambda"),
                max_arriving_cars=self._parse_int("max_arriving_cars"),
                initial_parked_cars=self._parse_int("initial_parked_cars"),
                initial_active_cars=self._parse_int("initial_active_cars"),
                initial_active_exit_rate=self._parse_float("initial_active_exit_rate"),
            )

            self.log_path = (ROOT / log_file).resolve()

            import random
            random.seed(seed)

            rules = GeneratorRules(**rules_cfg)
            generator = ParkingLotGenerator(width=width, height=height, rules=rules)
            grid = generator.generate()

            parking_cells, exit_cells, entry_cells = _extract_cells(grid)

            # Validation: Ensure we don't request more initial cars than spots
            total_spots = len(parking_cells)
            requested_initial = sim_cfg["initial_parked_cars"] + sim_cfg["initial_active_cars"]
            if requested_initial > total_spots:
                raise ValueError(f"Configuration Error: Requested {requested_initial} initial cars (parked + active), but the grid only has {total_spots} parking spots.")

            parking_manager = ParkingManager(
                grid=grid,
                parking_cells=parking_cells,
                exit_cells=exit_cells,
                entry_cells=entry_cells,
            )

            reservation_table = ReservationTable()
            planner = PriorityPlanner(
                grid=grid,
                reservation_table=reservation_table,
                planning_horizon=sim_cfg["planning_horizon"],
            )

            config = SimulationConfig(**sim_cfg)
            sim = SimulationCore(
                grid=grid,
                parking_manager=parking_manager,
                priority_planner=planner,
                config=config,
            )

            self.sim = sim
            self.grid = grid

            self.initial_exit_ids = {cid for cid, c in sim.active_cars.items() if getattr(c, "intent", None) == "EXIT"}
            self._is_over = False
            self.next_btn.configure(state="normal")

            with open(self.log_path, "w", encoding="utf-8") as f:
                f.write("Parking Simulation Stepper Log\n")
                f.write("==============================\n\n")
                f.write(f"seed={seed}\n")
                f.write(f"grid={width}x{height}\n")
                f.write(f"rules={rules_cfg}\n")
                f.write(f"sim_cfg={sim_cfg}\n\n")
                f.write("Grid legend: #=WALL, .=ROAD, P=PARKING, E=ENTRY, X=EXIT\n")
                f.write(_grid_to_ascii(grid) + "\n\n")

            self.status_var.set(f"Initialized. time={self.sim.time}. Log: {self.log_path}")
            self._append_state("INITIAL")
            self._draw_grid()
            self._apply_snapshot(self.sim.get_positions_snapshot())
            self._check_and_finalize_if_over()

        except Exception as e:
            messagebox.showerror("Init failed", str(e))

    def on_compute_capacity(self):
        """
        Dry-run: compute the maximum number of initial EXIT cars that can be spawned and planned
        at time 0, given the current grid/config.

        This is exact for the current implementation because it uses the same spawn logic
        (_get_free_road_cell) and the same planner/reservation table.
        """
        try:
            seed = self._parse_int("seed")
            width = self._parse_int("width")
            height = self._parse_int("height")

            rules_cfg = dict(
                num_entries=self._parse_int("num_entries"),
                num_exits=self._parse_int("num_exits"),
                num_parking_spots=self._parse_int("num_parking_spots"),
            )

            sim_cfg = dict(
                planning_horizon=self._parse_int("planning_horizon"),
                goal_reserve_horizon=self._parse_int("goal_reserve_horizon"),
                arrival_lambda=0.0,
                max_arriving_cars=0,
                initial_parked_cars=self._parse_int("initial_parked_cars"),
                initial_active_cars=0,
            )

            requested_initial_active = self._parse_int("initial_active_cars")

            import random
            random.seed(seed)

            rules = GeneratorRules(**rules_cfg)
            generator = ParkingLotGenerator(width=width, height=height, rules=rules)
            grid = generator.generate()

            parking_cells, exit_cells, entry_cells = _extract_cells(grid)

            parking_manager = ParkingManager(
                grid=grid,
                parking_cells=parking_cells,
                exit_cells=exit_cells,
                entry_cells=entry_cells,
            )

            reservation_table = ReservationTable()
            planner = PriorityPlanner(
                grid=grid,
                reservation_table=reservation_table,
                planning_horizon=sim_cfg["planning_horizon"],
            )

            config = SimulationConfig(**sim_cfg)
            sim = SimulationCore(
                grid=grid,
                parking_manager=parking_manager,
                priority_planner=planner,
                config=config,
            )

            road_cells = 0
            for x in range(grid.width):
                for y in range(grid.height):
                    if grid.get_cell(x, y).type == CellType.ROAD:
                        road_cells += 1

            spawned_ok = 0
            failed_plans = 0
            spawned_total = 0

            # Hard cap to avoid infinite loops
            hard_cap = road_cells
            for _ in range(hard_cap):
                start = sim._get_free_road_cell()
                if start is None:
                    break

                car = sim.parking_manager.create_active_car(start, intent="EXIT")
                sim._handle_new_car(car, start_time=0)

                spawned_total += 1
                if car.has_path():
                    spawned_ok += 1
                else:
                    failed_plans += 1

            msg = (
                f"Grid: {width}x{height}\n"
                f"Road cells: {road_cells}\n"
                f"Entries: {rules_cfg['num_entries']}, Exits: {rules_cfg['num_exits']}, Parking spots: {rules_cfg['num_parking_spots']}\n\n"
                f"Initial parked cars: {sim_cfg['initial_parked_cars']}\n"
                f"Requested initial EXIT cars: {requested_initial_active}\n\n"
                f"Max initial EXIT cars that can be SPAWNED at t=0: {spawned_total}\n"
                f"Of those, planned successfully at t=0: {spawned_ok}\n"
                f"Failed to plan at t=0: {failed_plans}"
            )
            messagebox.showinfo("Spawn Capacity", msg)

        except Exception as e:
            messagebox.showerror("Compute Capacity failed", str(e))

    def _is_sim_over(self) -> bool:
        if self.sim is None:
            return False

        # Done when:
        # 1) all initial EXIT cars have exited
        # 2) all arriving cars were spawned
        # 3) no active cars remain (so no one is still moving/parking/exiting)
        initial_exit_done = self.initial_exit_ids.issubset(self.sim.exited_car_ids)
        arrivals_done = self.sim.arriving_cars_created >= self.sim.config.max_arriving_cars
        no_active = len(self.sim.active_cars) == 0
        return initial_exit_done and arrivals_done and no_active

    def _check_and_finalize_if_over(self):
        if self.sim is None:
            return
        if self._is_over:
            return
        if not self._is_sim_over():
            return

        self._is_over = True
        self._append_state("OVER")
        self.next_btn.configure(state="disabled")
        self.status_var.set(f"Simulation over at time={self.sim.time}. Log: {self.log_path}")
        messagebox.showinfo("Simulation over", f"Simulation over at time={self.sim.time}.\nLog written to:\n{self.log_path}")

    def _append_state(self, label: str):
        if self.sim is None:
            return

        active_ids = set(self.sim.active_cars.keys())
        snapshot = self.sim.get_positions_snapshot()

        def car_status(cid: int) -> str:
            if cid in self.sim.exited_car_ids:
                return "EXITED"
            if cid in active_ids:
                return "ACTIVE"
            if cid in snapshot:
                return "PARKED"
            return "UNKNOWN"

        def car_pos(cid: int):
            if cid in snapshot:
                return snapshot[cid]
            car = self.sim.all_cars.get(cid)
            if car is None:
                return None
            return car.current_position

        all_ids = sorted(self.sim.all_cars.keys())

        with open(self.log_path, "a", encoding="utf-8") as f:
            f.write(f"--- {label} ---\n")
            f.write(f"time={self.sim.time}\n")
            f.write(f"counts: total_known={len(all_ids)}, active={len(self.sim.active_cars)}, parked={self.sim.total_parked}, exited={len(self.sim.exited_car_ids)}\n")
            f.write(
                f"arrivals: created={self.sim.arriving_cars_created}/{self.sim.config.max_arriving_cars}, "
                f"lambda={self.sim.config.arrival_lambda}, total_arrived={self.sim.total_arrived}\n"
            )
            f.write(
                f"initial: parked={self.sim.config.initial_parked_cars}, active={self.sim.config.initial_active_cars}\n"
            )
            for cid in all_ids:
                car = self.sim.all_cars[cid]
                pos = car_pos(cid)
                status = car_status(cid)
                f.write(
                    f"car {cid}: status={status}, pos={pos}, intent={car.intent}, goal={car.goal}, has_path={car.has_path()}\n"
                )
            f.write("\n")

    def _cell_to_pixel(self, x: int, y: int):
        px = self.margin + x * self.cell_size
        py = self.margin + y * self.cell_size
        return px, py

    def _draw_grid(self):
        if self.canvas is None or self.grid is None:
            return

        self.canvas.delete("all")
        self.canvas_items = {}

        w = self.margin * 2 + self.grid.width * self.cell_size
        h = self.margin * 2 + self.grid.height * self.cell_size
        self.canvas.configure(scrollregion=(0, 0, w, h))

        colors = {
            CellType.WALL: "#2b2b2b",
            CellType.ROAD: "#ffffff",
            CellType.PARKING: "#fff4cc",
            CellType.ENTRY: "#d9f7d9",
            CellType.EXIT: "#ffd6d6",
        }

        for y in range(self.grid.height):
            for x in range(self.grid.width):
                cell = self.grid.get_cell(x, y)
                px, py = self._cell_to_pixel(x, y)
                self.canvas.create_rectangle(
                    px,
                    py,
                    px + self.cell_size,
                    py + self.cell_size,
                    fill=colors.get(cell.type, "#ffffff"),
                    outline="#e0e0e0",
                )

    def _car_draw_style(self, cid: int, car) -> tuple:
        if cid in self.sim.exited_car_ids:
            return ("#000000", "#ffffff")

        if cid in self.sim.active_cars:
            return ("#1e90ff", "#ffffff")

        if getattr(car, "intent", None) == "PARK":
            return ("#2e7d32", "#ffffff")

        return ("#616161", "#ffffff")

    def _ensure_car_item(self, cid: int, pos, car):
        if self.canvas is None:
            return

        fill, text_color = self._car_draw_style(cid, car)
        px, py = self._cell_to_pixel(pos[0], pos[1])
        cx = px + self.cell_size / 2
        cy = py + self.cell_size / 2
        r = max(10, int(self.cell_size * 0.35))

        if cid not in self.canvas_items:
            oval = self.canvas.create_oval(cx - r, cy - r, cx + r, cy + r, fill=fill, outline="#000000")
            txt = self.canvas.create_text(cx, cy, text=str(cid), fill=text_color, font=("Arial", max(8, int(self.cell_size * 0.28)), "bold"))
            self.canvas_items[cid] = (oval, txt)
        else:
            oval, txt = self.canvas_items[cid]
            self.canvas.itemconfigure(oval, fill=fill)
            self.canvas.itemconfigure(txt, fill=text_color)
            self.canvas.coords(oval, cx - r, cy - r, cx + r, cy + r)
            self.canvas.coords(txt, cx, cy)

    def _apply_snapshot(self, snapshot):
        if self.sim is None or self.canvas is None:
            return

        to_remove = [cid for cid in self.canvas_items.keys() if cid not in snapshot]
        for cid in to_remove:
            oval, txt = self.canvas_items.pop(cid)
            self.canvas.delete(oval)
            self.canvas.delete(txt)

        for cid, pos in snapshot.items():
            car = self.sim.all_cars.get(cid)
            if car is None:
                continue
            self._ensure_car_item(cid, pos, car)

    def _animate_transition(self, prev_snapshot, next_snapshot):
        if self.sim is None or self.canvas is None:
            return

        moving = {}
        for cid, next_pos in next_snapshot.items():
            prev_pos = prev_snapshot.get(cid)
            if prev_pos is not None and prev_pos != next_pos:
                moving[cid] = (prev_pos, next_pos)

        self._apply_snapshot(prev_snapshot)

        frames = 10
        delay = 25

        def draw_frame(i: int):
            if self.sim is None or self.canvas is None:
                return

            if i > frames:
                self._apply_snapshot(next_snapshot)
                self._animating = False
                if not self._is_over:
                    self.next_btn.configure(state="normal")
                return

            alpha = i / frames
            for cid, (p0, p1) in moving.items():
                car = self.sim.all_cars.get(cid)
                if car is None:
                    continue

                x = p0[0] + (p1[0] - p0[0]) * alpha
                y = p0[1] + (p1[1] - p0[1]) * alpha
                px = self.margin + x * self.cell_size
                py = self.margin + y * self.cell_size
                cx = px + self.cell_size / 2
                cy = py + self.cell_size / 2
                r = max(10, int(self.cell_size * 0.35))

                self._ensure_car_item(cid, p1, car)
                oval, txt = self.canvas_items[cid]
                self.canvas.coords(oval, cx - r, cy - r, cx + r, cy + r)
                self.canvas.coords(txt, cx, cy)

            self.root.after(delay, lambda: draw_frame(i + 1))

        draw_frame(1)

    def on_next_step(self):
        if self.sim is None:
            messagebox.showwarning("Not initialized", "Click Initialize first")
            return

        if self._is_over:
            messagebox.showinfo("Simulation over", f"Simulation already finished at time={self.sim.time}.")
            return

        if self._animating:
            return

        prev_snapshot = self.sim.get_positions_snapshot()
        self.sim.step()
        self.status_var.set(f"Stepped. time={self.sim.time}. Log: {self.log_path}")
        next_snapshot = self.sim.get_positions_snapshot()
        self._animating = True
        self.next_btn.configure(state="disabled")
        self._animate_transition(prev_snapshot, next_snapshot)
        self._append_state("STEP")
        self._check_and_finalize_if_over()

    def on_log_state(self):
        if self.sim is None:
            messagebox.showwarning("Not initialized", "Click Initialize first")
            return

        self._append_state("STATE")
        self.status_var.set(f"State logged. time={self.sim.time}. Log: {self.log_path}")
        self._check_and_finalize_if_over()


def main():
    root = tk.Tk()
    app = StepperApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
