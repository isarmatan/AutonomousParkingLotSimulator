import sys
import json
import urllib.request
import urllib.error
import tkinter as tk
from tkinter import ttk, messagebox
from pathlib import Path
import threading

# Constants
API_URL = "http://127.0.0.1:8000"

class StepperAppV2:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("Parking Simulation Stepper V2 (Client Mode)")

        # State
        self.grid_data = None
        self.timesteps = []  # List of {t, cars}
        self.meta = {}
        self.current_step_index = -1
        self.saved_lots = [] # List of dicts

        # Visualization config
        self.cell_size = 32
        self.margin = 10
        self.canvas_items = {} # car_id -> (oval, text)

        self._build_ui()
        self._fetch_saved_lots()

    def _build_ui(self):
        frm = ttk.Frame(self.root, padding=12)
        frm.grid(row=0, column=0, sticky="nsew")

        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        frm.columnconfigure(0, weight=0)
        frm.columnconfigure(1, weight=1)
        frm.rowconfigure(0, weight=1)

        # --- Left Panel: Config ---
        left = ttk.Frame(frm)
        left.grid(row=0, column=0, sticky="ns")
        left.columnconfigure(0, weight=1)

        # --- Right Panel: Canvas ---
        right = ttk.Frame(frm)
        right.grid(row=0, column=1, sticky="nsew", padx=(12, 0))
        right.columnconfigure(0, weight=1)
        right.rowconfigure(0, weight=1)

        # --- Config Variables ---
        self.vars = {
            # Gen Rules
            "width": tk.StringVar(value="15"),
            "height": tk.StringVar(value="10"),
            "num_entries": tk.StringVar(value="1"),
            "num_exits": tk.StringVar(value="1"),
            "num_parking_spots": tk.StringVar(value="25"),
            
            # Load Config
            "selected_lot_id": tk.StringVar(),
            
            # Sim Params
            "planning_horizon": tk.StringVar(value="80"),
            "goal_reserve_horizon": tk.StringVar(value="200"),
            "arrival_lambda": tk.StringVar(value="0.3"),
            "max_arriving_cars": tk.StringVar(value="5"),
            "initial_parked_cars": tk.StringVar(value="4"),
            "initial_active_cars": tk.StringVar(value="3"),
            "initial_active_exit_rate": tk.StringVar(value="1.0"),
            "max_steps": tk.StringVar(value="500"),
        }

        # --- Notebook for Source (Generate vs Load) ---
        self.notebook = ttk.Notebook(left)
        self.notebook.grid(row=0, column=0, sticky="ew", pady=(0, 10))

        # Tab 1: Generate
        tab_gen = ttk.Frame(self.notebook, padding=10)
        self.notebook.add(tab_gen, text="Generate")
        
        gen_fields = [
            ("width", "Grid Width"),
            ("height", "Grid Height"),
            ("num_entries", "# Entries"),
            ("num_exits", "# Exits"),
            ("num_parking_spots", "# Parking Spots"),
        ]
        
        for i, (key, label) in enumerate(gen_fields):
            ttk.Label(tab_gen, text=label).grid(row=i, column=0, sticky="w")
            ttk.Entry(tab_gen, textvariable=self.vars[key], width=10).grid(row=i, column=1, sticky="ew")

        # Tab 2: Load
        tab_load = ttk.Frame(self.notebook, padding=10)
        self.notebook.add(tab_load, text="Load Saved")
        
        ttk.Label(tab_load, text="Select Parking Lot:").grid(row=0, column=0, sticky="w", pady=(0, 5))
        self.lot_combo = ttk.Combobox(tab_load, textvariable=self.vars["selected_lot_id"], state="readonly", width=25)
        self.lot_combo.grid(row=1, column=0, sticky="ew")
        
        ttk.Button(tab_load, text="Refresh List", command=self._fetch_saved_lots).grid(row=2, column=0, sticky="ew", pady=(5,0))

        # --- Simulation Params ---
        sim_frame = ttk.LabelFrame(left, text="Simulation Parameters", padding=10)
        sim_frame.grid(row=1, column=0, sticky="ew", pady=(0, 10))
        
        sim_fields = [
            ("planning_horizon", "Planning Horizon"),
            ("goal_reserve_horizon", "Goal Reserve"),
            ("arrival_lambda", "Arrival Lambda"),
            ("max_arriving_cars", "Max Arrivals"),
            ("initial_parked_cars", "Init. Parked"),
            ("initial_active_cars", "Init. Active"),
            ("initial_active_exit_rate", "Init. Exit Rate"),
            ("max_steps", "Max Steps"),
        ]

        for i, (key, label) in enumerate(sim_fields):
            ttk.Label(sim_frame, text=label).grid(row=i, column=0, sticky="w")
            ttk.Entry(sim_frame, textvariable=self.vars[key], width=10).grid(row=i, column=1, sticky="ew")

        # --- Action Buttons ---
        btns = ttk.Frame(left)
        btns.grid(row=2, column=0, sticky="ew", pady=(5, 0))
        btns.columnconfigure(0, weight=1)
        btns.columnconfigure(1, weight=1)

        ttk.Button(btns, text="Run Simulation (POST)", command=self.on_run_simulation).grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 5))
        
        self.prev_btn = ttk.Button(btns, text="< Prev", command=self.on_prev_step, state="disabled")
        self.prev_btn.grid(row=1, column=0, sticky="ew")
        
        self.next_btn = ttk.Button(btns, text="Next >", command=self.on_next_step, state="disabled")
        self.next_btn.grid(row=1, column=1, sticky="ew")

        # --- Status ---
        self.status_var = tk.StringVar(value="Ready. API URL: " + API_URL)
        ttk.Label(left, textvariable=self.status_var, wraplength=200).grid(row=3, column=0, sticky="w", pady=(15, 0))

        # --- Canvas ---
        self.canvas = tk.Canvas(right, bg="white", highlightthickness=1, highlightbackground="#cccccc")
        xscroll = ttk.Scrollbar(right, orient="horizontal", command=self.canvas.xview)
        yscroll = ttk.Scrollbar(right, orient="vertical", command=self.canvas.yview)
        self.canvas.configure(xscrollcommand=xscroll.set, yscrollcommand=yscroll.set)
        
        self.canvas.grid(row=0, column=0, sticky="nsew")
        yscroll.grid(row=0, column=1, sticky="ns")
        xscroll.grid(row=1, column=0, sticky="ew")

    def _fetch_saved_lots(self):
        def worker():
            try:
                with urllib.request.urlopen(f"{API_URL}/editor/saved") as response:
                    if response.status == 200:
                        data = json.loads(response.read().decode("utf-8"))
                        items = data.get("items", [])
                        self.saved_lots = items
                        # Update combo in main thread
                        self.root.after(0, self._update_combo_values)
            except Exception as e:
                print(f"Failed to fetch saved lots: {e}")

        threading.Thread(target=worker, daemon=True).start()

    def _update_combo_values(self):
        values = [f"{item['name']} ({item['id'][:8]}...)" for item in self.saved_lots]
        self.lot_combo['values'] = values
        if values:
            self.lot_combo.current(0)

    def _parse_int(self, key: str) -> int:
        return int(self.vars[key].get().strip())

    def _parse_float(self, key: str) -> float:
        return float(self.vars[key].get().strip())

    def on_run_simulation(self):
        try:
            # Determine source based on active tab
            current_tab = self.notebook.index(self.notebook.select())
            
            payload = {
                "planning_horizon": self._parse_int("planning_horizon"),
                "goal_reserve_horizon": self._parse_int("goal_reserve_horizon"),
                "arrival_lambda": self._parse_float("arrival_lambda"),
                "max_arriving_cars": self._parse_int("max_arriving_cars"),
                "initial_parked_cars": self._parse_int("initial_parked_cars"),
                "initial_active_cars": self._parse_int("initial_active_cars"),
                "initial_active_exit_rate": self._parse_float("initial_active_exit_rate"),
                "max_steps": self._parse_int("max_steps"),
            }

            if current_tab == 0: # Generate
                payload["source"] = "generate"
                payload["width"] = self._parse_int("width")
                payload["height"] = self._parse_int("height")
                payload["rules"] = {
                    "num_entries": self._parse_int("num_entries"),
                    "num_exits": self._parse_int("num_exits"),
                    "num_parking_spots": self._parse_int("num_parking_spots"),
                }
            else: # Load
                selection_idx = self.lot_combo.current()
                if selection_idx == -1:
                    messagebox.showwarning("Validation", "Please select a parking lot.")
                    return
                lot_id = self.saved_lots[selection_idx]["id"]
                payload["source"] = "load"
                payload["parkingLotId"] = lot_id

            json_data = json.dumps(payload).encode("utf-8")
            req = urllib.request.Request(
                f"{API_URL}/simulation/run", 
                data=json_data, 
                headers={"Content-Type": "application/json"},
                method="POST"
            )

            self.status_var.set("Requesting simulation...")
            self.root.update()

            def worker():
                try:
                    with urllib.request.urlopen(req) as response:
                        if response.status != 200:
                            raise Exception(f"HTTP Error: {response.status}")
                        
                        resp_body = response.read().decode("utf-8")
                        data = json.loads(resp_body)
                        self.root.after(0, lambda: self._on_sim_success(data))
                except urllib.error.URLError as e:
                    self.root.after(0, lambda: messagebox.showerror("Connection Error", f"Could not connect to API.\n{e}"))
                except Exception as e:
                    self.root.after(0, lambda: messagebox.showerror("Error", str(e)))

            threading.Thread(target=worker, daemon=True).start()

        except Exception as e:
            messagebox.showerror("Validation Error", str(e))

    def _on_sim_success(self, data):
        self.grid_data = data["grid"]
        self.timesteps = data["timesteps"]
        self.meta = data["meta"]
        
        self.current_step_index = 0
        
        sim_status = self.meta.get("status", "UNKNOWN")
        sim_msg = self.meta.get("message", "")
        
        base_status = f"Loaded {len(self.timesteps)} steps. Status: {sim_status}."
        if sim_status != "COMPLETED":
            base_status += " (Warning: Not finished)"
            if sim_msg:
                messagebox.showwarning("Simulation Limit Reached", sim_msg)
        
        self.status_var.set(base_status)
        self._draw_static_grid()
        self._draw_step(0)
        self._update_buttons()

    def _update_buttons(self):
        if not self.timesteps:
            self.prev_btn.configure(state="disabled")
            self.next_btn.configure(state="disabled")
            return

        if self.current_step_index > 0:
            self.prev_btn.configure(state="normal")
        else:
            self.prev_btn.configure(state="disabled")

        if self.current_step_index < len(self.timesteps) - 1:
            self.next_btn.configure(state="normal")
        else:
            self.next_btn.configure(state="disabled")

    def _cell_to_pixel(self, x, y):
        px = self.margin + x * self.cell_size
        py = self.margin + y * self.cell_size
        return px, py

    def _draw_static_grid(self):
        self.canvas.delete("all")
        self.canvas_items = {}

        if not self.grid_data:
            return

        width = self.grid_data["width"]
        height = self.grid_data["height"]
        cells = self.grid_data["cells"]

        # Resize scroll region
        w_px = self.margin * 2 + width * self.cell_size
        h_px = self.margin * 2 + height * self.cell_size
        self.canvas.configure(scrollregion=(0, 0, w_px, h_px))

        # Color map
        colors = {
            "WALL": "#2b2b2b",
            "ROAD": "#ffffff",
            "PARKING": "#fff4cc",
            "ENTRY": "#d9f7d9",
            "EXIT": "#ffd6d6",
        }

        # Draw grid cells
        for c in cells:
            x, y = c["x"], c["y"]
            ctype = c["type"]
            px, py = self._cell_to_pixel(x, y)
            
            self.canvas.create_rectangle(
                px, py, px + self.cell_size, py + self.cell_size,
                fill=colors.get(ctype, "pink"), outline="#e0e0e0"
            )

    def _draw_step(self, step_idx):
        if step_idx < 0 or step_idx >= len(self.timesteps):
            return

        step_data = self.timesteps[step_idx]
        t = step_data["t"]
        cars = step_data["cars"] # dict of car_id -> [x, y]
        
        self.status_var.set(f"Time: {t} | Cars: {len(cars)} | Step {step_idx + 1}/{len(self.timesteps)}")

        # Sync cars on canvas
        # 1. Remove cars not in current step
        current_ids = set(cars.keys())
        existing_ids = set(self.canvas_items.keys())
        
        for cid in existing_ids - current_ids:
            oval, txt = self.canvas_items.pop(cid)
            self.canvas.delete(oval)
            self.canvas.delete(txt)
        
        # 2. Update/Create cars
        for cid_str, pos in cars.items():
            cid = str(cid_str)
            x, y = pos
            px, py = self._cell_to_pixel(x, y)
            cx = px + self.cell_size / 2
            cy = py + self.cell_size / 2
            r = max(10, int(self.cell_size * 0.35))
            
            fill = "#1e90ff" # Default blue
            
            if cid not in self.canvas_items:
                oval = self.canvas.create_oval(cx - r, cy - r, cx + r, cy + r, fill=fill, outline="#000000")
                txt = self.canvas.create_text(cx, cy, text=cid, fill="white", font=("Arial", 8, "bold"))
                self.canvas_items[cid] = (oval, txt)
            else:
                oval, txt = self.canvas_items[cid]
                self.canvas.coords(oval, cx - r, cy - r, cx + r, cy + r)
                self.canvas.coords(txt, cx, cy)
                self.canvas.itemconfigure(oval, fill=fill)

    def on_next_step(self):
        if self.current_step_index < len(self.timesteps) - 1:
            self.current_step_index += 1
            self._draw_step(self.current_step_index)
            self._update_buttons()

    def on_prev_step(self):
        if self.current_step_index > 0:
            self.current_step_index -= 1
            self._draw_step(self.current_step_index)
            self._update_buttons()

def main():
    root = tk.Tk()
    app = StepperAppV2(root)
    root.mainloop()

if __name__ == "__main__":
    main()
