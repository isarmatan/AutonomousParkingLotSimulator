import { useEffect, useMemo, useRef, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import AppLayout from "../layouts/AppLayout";
import { Play, Pause, SkipBack, SkipForward, RotateCcw, AlertTriangle, Loader2, Save, Check, LayoutGrid, Box } from "lucide-react";
import "./Simulation.css";
import Simulation3D from "../components/Simulation3D";

// --- Types ---
type SimConfig = {
  planning_horizon: number;
  goal_reserve_horizon: number;
  arrival_lambda: number;
  max_arriving_cars: number;
  initial_parked_cars: number;
  initial_active_cars: number;
  initial_active_exit_rate: number;
  max_steps: number;
};

type SimulationRequest = SimConfig & {
  source: "generate" | "load";
  width?: number;
  height?: number;
  rules?: {
    num_entries: number;
    num_exits: number;
    num_parking_spots: number;
  };
  parkingLotId?: string;
};

type NewLayout = {
  length: number;
  width: number;
  entries: number;
  exits: number;
  totalSpots: number;
};

type GridCell = {
  x: number;
  y: number;
  type: "WALL" | "ROAD" | "PARKING" | "ENTRY" | "EXIT";
  metadata: Record<string, unknown>;
};

type GridData = {
  width: number;
  height: number;
  cells: GridCell[];
};

type TimestepStats = {
  total_cars: number;
  total_parked: number;
  total_failed_plans: number;
  initial_active_cars_exited: number;
  arriving_cars_spawned: number;
  arriving_cars_parked: number;
  average_steps_to_park?: number;
  average_steps_to_exit?: number;
};

type Timestep = {
  t: number;
  cars: Record<string, [number, number, number]>;
  stats: TimestepStats;
};

type SimResponse = {
  grid: GridData;
  timesteps: Timestep[];
  meta: {
    status: string;
    message?: string;
    total_steps: number;
    total_cars: number;
    total_parked: number;
    total_failed_plans: number;

    initial_active_cars_configured: number;
    initial_active_cars_exited: number;
    
    max_arriving_cars_configured: number;
    arriving_cars_spawned: number;
    arriving_cars_parked: number;
    
    average_steps_to_park?: number;
    average_steps_to_exit?: number;
  };
};

const API_URL = "http://127.0.0.1:8000";
const CONFIG_KEY = "sim_config_v1";
const LAYOUT_KEY = "parking_layout_v1";

// const CELL_SIZE = 32;
const COLORS = {
  WALL: "#1e293b",
  ROAD: "rgba(255, 255, 255, 0.05)",
  PARKING: "rgba(234, 179, 8, 0.2)",
  ENTRY: "rgba(34, 197, 94, 0.2)",
  EXIT: "rgba(239, 68, 68, 0.2)",
  CAR_INITIAL: "#ef4444", // Red for exiting cars (t=0)
  CAR_ARRIVING: "#eab308", // Yellow for entering cars
  CAR: "#38bdf8",
  CAR_TEXT: "#000000",
  GRID_LINE: "rgba(56, 189, 248, 0.1)",
};

export default function Simulation() {
  const nav = useNavigate();
  const [params] = useSearchParams();
  const layoutId = params.get("layout");

  // State
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [data, setData] = useState<SimResponse | null>(null);
  const [stepIndex, setStepIndex] = useState(0);
  const [stepProgress, setStepProgress] = useState(0);
  const [isPlaying, setIsPlaying] = useState(false);
  const [viewMode, setViewMode] = useState<"2D" | "3D">("3D");
  
  // Persistence
  const [reqPayload, setReqPayload] = useState<SimulationRequest | null>(null);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);

  // Canvas Refs
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const carRotationsRef = useRef<Record<string, number>>({});
  
  // 2D View Scaling
  const sim2DRef = useRef<HTMLDivElement>(null);
  const [gridScale, setGridScale] = useState(1);
  const CELL_PX = 32;
  const GAP_PX = 1;
  const PADDING_PX = 1;

  // Load Configs & Fetch
  useEffect(() => {
    const fetchData = async () => {
      try {
        setLoading(true);
        setError(null);
        setSaved(false);

        // 1. Read Config
        const rawConfig = sessionStorage.getItem(CONFIG_KEY);
        if (!rawConfig) throw new Error("Missing simulation configuration.");
        const config: SimConfig = JSON.parse(rawConfig);

        // 2. Prepare Payload
        // We use Partial or construct it carefully to avoid TS errors before completion
        const basePayload: Partial<SimulationRequest> = { ...config };

        if (layoutId === "new") {
          const rawLayout = sessionStorage.getItem(LAYOUT_KEY);
          if (!rawLayout) throw new Error("Missing new layout parameters.");
          const layout: NewLayout = JSON.parse(rawLayout);
          
          basePayload.source = "generate";
          basePayload.width = layout.width;
          basePayload.height = layout.length; // Mapping length to height
          basePayload.rules = {
            num_entries: layout.entries,
            num_exits: layout.exits,
            num_parking_spots: layout.totalSpots,
          };
        } else if (layoutId) {
          basePayload.source = "load";
          basePayload.parkingLotId = layoutId;
        } else {
          throw new Error("No layout specified.");
        }
        
        const payload = basePayload as SimulationRequest;
        setReqPayload(payload);

        // 3. Fetch
        const res = await fetch(`${API_URL}/simulation/run`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload),
        });

        if (!res.ok) {
          const txt = await res.text();
          throw new Error(`Simulation failed: ${res.statusText}\n${txt}`);
        }

        const result: SimResponse = await res.json();
        setData(result);
        setStepIndex(0);
        carRotationsRef.current = {};
      } catch (err: unknown) {
        console.error(err);
        if (err instanceof Error) {
          setError(err.message);
        } else {
          setError("An unknown error occurred");
        }
      } finally {
        setLoading(false);
      }
    };

    fetchData();
  }, [layoutId]);

  // Playback Loop
  const requestRef = useRef<number | null>(null);
  const lastTimeRef = useRef<number>(0);
  const accumulatorRef = useRef<number>(0);

  useEffect(() => {
    if (!isPlaying || !data) {
      if (requestRef.current !== null) {
        cancelAnimationFrame(requestRef.current);
        requestRef.current = null;
      }
      return;
    }

    lastTimeRef.current = performance.now();
    accumulatorRef.current = 0;

    const animate = (time: number) => {
      const delta = time - lastTimeRef.current;
      lastTimeRef.current = time;
      
      // Cap delta to prevent huge jumps (e.g. if tab was backgrounded)
      // Max 1 second catch-up
      const safeDelta = Math.min(delta, 1000);
      
      accumulatorRef.current += safeDelta;

      const stepDuration = 100; // 100ms per step

      if (accumulatorRef.current >= stepDuration) {
        setStepIndex((prev) => {
          const maxIndex = data.timesteps.length - 1;
          if (prev >= maxIndex) {
            setIsPlaying(false);
            return prev;
          }
          return prev + 1;
        });
        accumulatorRef.current -= stepDuration;
        
        // Anti-Spiral: If we are still behind after advancing a step, 
        // it means rendering is slower than 10fps.
        // We reset accumulator to 0 to "slow down time" and ensure we see this step 
        // instead of rushing/skipping to catch up.
        if (accumulatorRef.current >= stepDuration) {
             accumulatorRef.current = 0;
        }
      }

      // Calculate progress (0.0 to 1.0)
      const progress = Math.max(0, Math.min(accumulatorRef.current / stepDuration, 1.0));
      setStepProgress(progress);

      requestRef.current = requestAnimationFrame(animate);
    };

    requestRef.current = requestAnimationFrame(animate);

    return () => {
      if (requestRef.current !== null) {
        cancelAnimationFrame(requestRef.current);
      }
    };
  }, [isPlaying, data]);

  // Compute Canvas Size (matching DOM grid with gaps)
  const canvasSize = useMemo(() => {
    if (!data) return { width: 800, height: 600 };
    const w = data.grid.width;
    const h = data.grid.height;
    // Width = padding*2 + cells + gaps
    const width = (PADDING_PX * 2) + (w * CELL_PX) + ((w - 1) * GAP_PX);
    const height = (PADDING_PX * 2) + (h * CELL_PX) + ((h - 1) * GAP_PX);
    return { width, height };
  }, [data]);

  // Compute scale in 2D
  useEffect(() => {
    if (!data) return;
    if (viewMode !== "2D") return;
    const el = sim2DRef.current;
    if (!el) return;

    const compute = () => {
      const rect = el.getBoundingClientRect();
      const availableW = rect.width;
      const availableH = rect.height;

      const { width: gridW, height: gridH } = canvasSize;
      const margin = 40; 

      const sx = (availableW - margin) / gridW;
      const sy = (availableH - margin) / gridH;

      const s = Math.min(1, sx, sy);
      setGridScale(Math.max(0.1, s));
    };

    compute();
    const ro = new ResizeObserver(compute);
    ro.observe(el);
    window.addEventListener("resize", compute);
    return () => {
      window.removeEventListener("resize", compute);
      ro.disconnect();
    };
  }, [data, viewMode, canvasSize]);

  // Draw Cars (Canvas Overlay)
  useEffect(() => {
    if (viewMode !== "2D") return;
    
    const canvas = canvasRef.current;
    if (!canvas || !data) return;

    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    const { timesteps } = data;
    const currentStep = timesteps[stepIndex];

    // Clear
    ctx.clearRect(0, 0, canvas.width, canvas.height);

    // Draw Cars
    if (currentStep && currentStep.cars) {
      Object.entries(currentStep.cars).forEach(([id, data]) => {
        const [cx, cy, isInitial] = data; // data is [x, y, is_initial]
        
        let drawX = cx;
        let drawY = cy;
        let angle = carRotationsRef.current[id] ?? 0;

        // Interpolation
        const nextStep = timesteps[stepIndex + 1];
        if (nextStep && nextStep.cars && nextStep.cars[id]) {
          const [nx, ny] = nextStep.cars[id];
          const dx = nx - cx;
          const dy = ny - cy;
          
          // Only update angle if moving significantly
          if (Math.abs(dx) > 0.01 || Math.abs(dy) > 0.01) {
             angle = Math.atan2(dy, dx);
             carRotationsRef.current[id] = angle;
          }

          drawX = cx + dx * stepProgress;
          drawY = cy + dy * stepProgress;
        }

        // Calculate pixel position with gaps
        const px = PADDING_PX + drawX * (CELL_PX + GAP_PX) + CELL_PX / 2;
        const py = PADDING_PX + drawY * (CELL_PX + GAP_PX) + CELL_PX / 2;

        // --- Draw Car Shape ---
        ctx.save();
        ctx.translate(px, py);
        ctx.rotate(angle);

        const carLen = CELL_PX * 0.75;
        const carWidth = CELL_PX * 0.45;

        // Body color
        ctx.fillStyle = isInitial === 1 ? COLORS.CAR_INITIAL : COLORS.CAR_ARRIVING;
        
        ctx.beginPath();
        // Check for roundRect support, fallback to rect
        if (typeof ctx.roundRect === 'function') {
             ctx.roundRect(-carLen/2, -carWidth/2, carLen, carWidth, 4);
        } else {
             ctx.rect(-carLen/2, -carWidth/2, carLen, carWidth);
        }
        ctx.fill();
        ctx.strokeStyle = "rgba(0,0,0,0.5)";
        ctx.lineWidth = 1;
        ctx.stroke();

        // Windshields (Dark)
        ctx.fillStyle = "rgba(0, 0, 0, 0.6)";
        // Front (Right side at 0 angle)
        ctx.fillRect(carLen/6, -carWidth/2 + 2, 3, carWidth - 4);
        // Rear (Left side)
        ctx.fillRect(-carLen/2 + 3, -carWidth/2 + 2, 2, carWidth - 4);
        ctx.fillRect(-carLen/2 + 2, -carWidth/2 + 2, 3, carWidth - 4);

        // Headlights (Yellow/White)
        ctx.fillStyle = "rgba(255, 255, 200, 0.9)";
        ctx.beginPath();
        ctx.arc(carLen/2 - 2, -carWidth/2 + 3, 1.5, 0, Math.PI * 2);
        ctx.arc(carLen/2 - 2, carWidth/2 - 3, 1.5, 0, Math.PI * 2);
        ctx.fill();

        ctx.restore();

        // Text
        ctx.fillStyle = COLORS.CAR_TEXT;
        ctx.font = "bold 9px sans-serif";
        ctx.textAlign = "center";
        ctx.textBaseline = "middle";
        ctx.fillText(id.slice(0, 3), px, py);
      });
    }
  }, [data, stepIndex, stepProgress, viewMode, canvasSize]);

  // Prepare Rows for DOM Grid
  const gridRows = useMemo(() => {
    if (!data) return null;
    const { width, height, cells } = data.grid;
    const r = Array.from({ length: height }, () => Array(width).fill(null as GridCell | null));
    cells.forEach((cell) => {
      if (cell.x < width && cell.y < height) r[cell.y][cell.x] = cell;
    });
    return r;
  }, [data]);

  // Handlers
  const togglePlay = () => setIsPlaying(!isPlaying);
  const restart = () => {
    setIsPlaying(false);
    setStepIndex(0);
  };
  const nextStep = () => setStepIndex((i) => Math.min(i + 1, (data?.timesteps.length || 1) - 1));
  const prevStep = () => setStepIndex((i) => Math.max(i - 1, 0));

  const handleSave = async () => {
    if (!data || !reqPayload || saved) return;
    
    const name = window.prompt("Enter a name for this simulation result:", "My Simulation");
    if (!name) return; // Cancelled

    try {
      setSaving(true);
      const payload = {
          name,
          request: reqPayload,
          meta: data.meta,
          grid_width: data.grid.width,
          grid_height: data.grid.height
      };
      
      const res = await fetch(`${API_URL}/simulation/save`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      
      if (!res.ok) {
        const errorData = await res.json().catch(() => ({ detail: res.statusText }));
        const errorMessage = typeof errorData.detail === 'string' 
            ? errorData.detail 
            : JSON.stringify(errorData.detail, null, 2);
        throw new Error(`Failed to save results: ${errorMessage}`);
      }
      
      setSaved(true);
    } catch (err: unknown) {
        console.error(err);

        if (err instanceof Error) {
          alert(err.message);
        } else {
          alert("Failed to save results");
        }
      } finally {
        setSaving(false);
      }
  };

  return (
    <AppLayout variant="editor">
      <div className="simPage">
        {/* Header */}
        <div className="simHeader">
          <div className="simTitleGroup">
            <h1 className="simTitle">Simulation</h1>
            {data && (
              <span className={`statusBadge ${data.meta.status === "COMPLETED" ? "success" : "warning"}`}>
                {data.meta.status}
              </span>
            )}
          </div>
          
          <div className="simControls">
             <div className="viewToggle" style={{ marginRight: 16, borderRight: "1px solid #eee", paddingRight: 16, display: "flex", gap: "0.5rem" }}>
              <button 
                className={`iconBtn ${viewMode === "2D" ? "primary" : ""}`}
                onClick={() => setViewMode("2D")}
                title="2D View"
                style={{ width: "auto", padding: "0 8px", gap: "6px" }}
              >
                <LayoutGrid size={18} />
                <span style={{ fontSize: "0.8rem", fontWeight: 600 }}>2D</span>
              </button>
              <button 
                className={`iconBtn ${viewMode === "3D" ? "primary" : ""}`}
                onClick={() => setViewMode("3D")}
                title="3D View"
                style={{ width: "auto", padding: "0 8px", gap: "6px" }}
              >
                <Box size={18} />
                <span style={{ fontSize: "0.8rem", fontWeight: 600 }}>3D</span>
              </button>
            </div>

             {data && (
               <>
                 <span className="stepCounter">
                   Step {stepIndex} / {data.timesteps.length - 1}
                 </span>
                 <div className="controlGroup">
                   <button className="iconBtn" onClick={restart} title="Restart">
                     <RotateCcw size={18} />
                   </button>
                   <button className="iconBtn" onClick={prevStep} disabled={stepIndex <= 0} title="Previous">
                     <SkipBack size={18} />
                   </button>
                   <button className="iconBtn primary" onClick={togglePlay} title={isPlaying ? "Pause" : "Play"}>
                     {isPlaying ? <Pause size={18} /> : <Play size={18} />}
                   </button>
                   <button className="iconBtn" onClick={nextStep} disabled={!data || stepIndex >= data.timesteps.length - 1} title="Next">
                     <SkipForward size={18} />
                   </button>
                 </div>
                 
                 <div className="controlGroup">
                    <button 
                        className={`iconBtn ${saved ? 'success' : ''}`} 
                        onClick={handleSave} 
                        disabled={saving || saved}
                        title={saved ? "Saved" : "Save Results"}
                    >
                        {saving ? <Loader2 className="spinner" size={18} /> : (saved ? <Check size={18} /> : <Save size={18} />)}
                    </button>
                 </div>
               </>
             )}
             <button className="btnGhost" onClick={() => nav("/layout")}>
               Close
             </button>
          </div>
        </div>

        {/* Content */}
        <div className="simContent">
          {loading && (
            <div className="loadingContainer">
              <Loader2 className="spinner" size={48} />
              <p>Running simulation...</p>
              <p className="subText">This may take a few seconds.</p>
            </div>
          )}

          {error && (
            <div className="errorContainer">
              <AlertTriangle className="errorIcon" size={48} />
              <h2>Simulation Error</h2>
              <p>{error}</p>
              <button className="btnPrimary" onClick={() => nav("/config")}>
                Return to Config
              </button>
            </div>
          )}

          {!loading && !error && data && (
            <div className={`canvasContainer ${viewMode === "3D" ? "mode-3d" : ""}`}>
              <div className="simStats">
                <div className="statGroup">
                  <div className="statGroupTitle">Initial Batch</div>
                  <div className="statRow">
                    <span className="statLabel">Served (Exited)</span>
                    <span className="statValue">
                      {data.timesteps[stepIndex]?.stats?.initial_active_cars_exited ?? 0} / {data.meta.initial_active_cars_configured}
                    </span>
                  </div>
                  {data.timesteps[stepIndex]?.stats?.average_steps_to_exit ? (
                    <div className="statRow">
                      <span className="statLabel">Avg Steps</span>
                      <span className="statValue">{data.timesteps[stepIndex].stats.average_steps_to_exit!.toFixed(1)}</span>
                    </div>
                  ) : null}
                </div>

                <div className="statDivider" />

                <div className="statGroup">
                  <div className="statGroupTitle">Arrivals</div>
                  <div className="statRow">
                    <span className="statLabel">Served (Parked)</span>
                    <span className="statValue">
                      {data.timesteps[stepIndex]?.stats?.arriving_cars_parked ?? 0} / {data.meta.max_arriving_cars_configured}
                    </span>
                  </div>
                  {data.timesteps[stepIndex]?.stats?.average_steps_to_park ? (
                    <div className="statRow">
                      <span className="statLabel">Avg Steps</span>
                      <span className="statValue">{data.timesteps[stepIndex].stats.average_steps_to_park!.toFixed(1)}</span>
                    </div>
                  ) : null}
                </div>

                <div className="statDivider" />

                <div className="statGroup">
                  <div className="statGroupTitle">Global</div>
                  <div className="statRow">
                    <span className="statLabel">Time</span>
                    <span className="statValue">{data.timesteps[stepIndex]?.t ?? stepIndex} / {data.meta.total_steps}</span>
                  </div>
                  <div className="statRow">
                     <span className="statLabel">Failures</span>
                     <span className="statValue">{data.timesteps[stepIndex]?.stats?.total_failed_plans ?? 0}</span>
                  </div>
                </div>
              </div>

              {viewMode === "3D" ? (
                <div className="canvasWrapper3D">
                  <Simulation3D 
                    grid={data.grid} 
                    timesteps={data.timesteps} 
                    currentStepIndex={stepIndex} 
                    stepProgress={stepProgress}
                  />
                </div>
              ) : (
                <div className="simCanvasScroll" ref={sim2DRef}>
                  {data && gridRows && (
                    <div className="simGridWrap" style={{ transform: `scale(${gridScale})` }}>
                      <div style={{ position: "relative" }}>
                        {/* DOM Grid */}
                        <div
                          className="simGrid"
                          style={{
                            gridTemplateColumns: `repeat(${data.grid.width}, ${CELL_PX}px)`,
                            gridTemplateRows: `repeat(${data.grid.height}, ${CELL_PX}px)`,
                          }}
                        >
                          {gridRows.map((row, y) =>
                            row.map((cell: GridCell | null, x: number) => {
                              if (!cell) return <div key={`${x}-${y}`} className="simCell" />;
                              return (
                                <div
                                  key={`${x}-${y}`}
                                  className={`simCell cell-${cell.type}`}
                                  data-mark={cell.type === "ENTRY" ? "IN" : cell.type === "EXIT" ? "OUT" : undefined}
                                  title={`(${x},${y}) ${cell.type}`}
                                />
                              );
                            })
                          )}
                        </div>
                        
                        {/* Canvas Overlay for Cars */}
                        <canvas
                          ref={canvasRef}
                          width={canvasSize.width}
                          height={canvasSize.height}
                          className="simCanvas"
                        />
                      </div>
                    </div>
                  )}
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </AppLayout>
  );
}