import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import AppLayout from "../layouts/AppLayout";
import { Play, Pause, Square, RotateCcw, AlertTriangle, Loader2, LayoutGrid, Box } from "lucide-react";
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
  max_timesteps: number;
  step_delay_ms: number;
  algorithm: string;
};

type LiveSimulationRequest = SimConfig & {
  source: "generate" | "load";
  width?: number;
  height?: number;
  rules?: { num_entries: number; num_exits: number; num_parking_spots: number };
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
  stats?: TimestepStats;
};

type WsStatus = "IDLE" | "CONNECTING" | "RUNNING" | "PAUSED" | "STOPPED" | "COMPLETED" | "ERROR";

const API_URL = "http://127.0.0.1:8000";
const WS_URL  = "ws://127.0.0.1:8000";
const CONFIG_KEY = "sim_config_v2";
const LAYOUT_KEY = "parking_layout_v1";

const STATUS_CLASS: Record<WsStatus, string> = {
  IDLE: "default", CONNECTING: "default", RUNNING: "success",
  PAUSED: "warning", STOPPED: "warning", COMPLETED: "success", ERROR: "error",
};

const COLORS = {
  CAR_INITIAL: "#ef4444",
  CAR_ARRIVING: "#eab308",
  CAR_TEXT: "#000000",
};

export default function Simulation() {
  const nav = useNavigate();
  const [params] = useSearchParams();
  const layoutId = params.get("layout");

  // ---- State ----
  const [loading, setLoading]       = useState(true);
  const [error, setError]           = useState<string | null>(null);
  const [gridData, setGridData]     = useState<GridData | null>(null);
  const [wsStatus, setWsStatus]     = useState<WsStatus>("IDLE");
  const [liveT, setLiveT]           = useState(0);
  const [liveStats, setLiveStats]   = useState<TimestepStats | null>(null);
  const [viewMode, setViewMode]     = useState<"2D" | "3D">("3D");
  const [liveTimesteps, setLiveTimesteps] = useState<Timestep[]>([]);
  const [renderTick, setRenderTick] = useState(0);

  // ---- Refs ----
  const wsRef       = useRef<WebSocket | null>(null);
  const liveCarsRef = useRef<Record<string, [number, number, number]>>({});
  const prevCarsRef = useRef<Record<string, [number, number, number]>>({});
  const canvasRef   = useRef<HTMLCanvasElement>(null);
  const sim2DRef    = useRef<HTMLDivElement>(null);

  // 2D view scaling
  const [gridScale, setGridScale] = useState(1);
  const CELL_PX   = 32;
  const GAP_PX    = 1;
  const PADDING_PX = 1;

  // ---- WebSocket + /start ----
  useEffect(() => {
    const start = async () => {
      setLoading(true);
      setError(null);
      setWsStatus("CONNECTING");

      try {
        const rawConfig = sessionStorage.getItem(CONFIG_KEY);
        if (!rawConfig) throw new Error("Missing simulation configuration.");
        const config: SimConfig = JSON.parse(rawConfig);

        const basePayload: Partial<LiveSimulationRequest> = { ...config };

        if (layoutId === "new") {
          const rawLayout = sessionStorage.getItem(LAYOUT_KEY);
          if (!rawLayout) throw new Error("Missing new layout parameters.");
          const layout: NewLayout = JSON.parse(rawLayout);
          basePayload.source = "generate";
          basePayload.width  = layout.width;
          basePayload.height = layout.length;
          basePayload.rules  = {
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

        const res = await fetch(`${API_URL}/simulation/start`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(basePayload as LiveSimulationRequest),
        });

        if (!res.ok) {
          const txt = await res.text();
          throw new Error(`Failed to start simulation: ${res.statusText}\n${txt}`);
        }

        const { session_id, grid } = await res.json();
        setGridData(grid);

        const ws = new WebSocket(`${WS_URL}/simulation/ws/${session_id}`);
        wsRef.current = ws;

        ws.onmessage = (event) => {
          const msg = JSON.parse(event.data);

          if (msg.type === "INIT") {
            setGridData(msg.grid);
            liveCarsRef.current = {};
            prevCarsRef.current = {};
            setLiveTimesteps([]);
            setLiveT(0);
            setLiveStats(null);
            setLoading(false);
            setWsStatus("RUNNING");

          } else if (msg.type === "STEP") {
            const cars = msg.cars as Record<string, [number, number, number]>;
            const prev = { ...liveCarsRef.current };
            prevCarsRef.current = prev;
            liveCarsRef.current = cars;
            setLiveT(msg.t);
            setLiveStats(msg.stats);
            setRenderTick((n) => n + 1);
            setLiveTimesteps([
              { t: msg.t - 1, cars: prev },
              { t: msg.t,     cars },
            ]);

          } else if (msg.type === "STATUS") {
            setWsStatus(msg.status as WsStatus);

          } else if (msg.type === "ERROR") {
            setError(msg.message);
            setWsStatus("ERROR");
            setLoading(false);
          }
        };

        ws.onerror = () => {
          setError("WebSocket connection error.");
          setWsStatus("ERROR");
          setLoading(false);
        };

        ws.onclose = () => {
          setWsStatus((prev) =>
            prev === "RUNNING" || prev === "PAUSED" ? "STOPPED" : prev
          );
        };

      } catch (err: unknown) {
        setError(err instanceof Error ? err.message : "An unknown error occurred");
        setWsStatus("ERROR");
        setLoading(false);
      }
    };

    start();
    return () => { wsRef.current?.close(); };
  }, [layoutId]);

  // ---- Control helpers ----
  const send = useCallback((msg: object) => {
    wsRef.current?.send(JSON.stringify(msg));
  }, []);

  const handlePause  = () => send({ type: "PAUSE" });
  const handleResume = () => send({ type: "RESUME" });
  const handleStop   = () => send({ type: "STOP" });
  const handleReset  = () => {
    liveCarsRef.current = {};
    prevCarsRef.current = {};
    setLiveT(0);
    setLiveStats(null);
    setLiveTimesteps([]);
    send({ type: "RESET" });
  };

  const isConnected = wsStatus === "RUNNING" || wsStatus === "PAUSED";

  // ---- Canvas size ----
  const canvasSize = useMemo(() => {
    if (!gridData) return { width: 800, height: 600 };
    const w = gridData.width;
    const h = gridData.height;
    return {
      width:  PADDING_PX * 2 + w * CELL_PX + (w - 1) * GAP_PX,
      height: PADDING_PX * 2 + h * CELL_PX + (h - 1) * GAP_PX,
    };
  }, [gridData]);

  // ---- 2D scale ----
  useEffect(() => {
    if (!gridData || viewMode !== "2D") return;
    const el = sim2DRef.current;
    if (!el) return;
    const compute = () => {
      const rect = el.getBoundingClientRect();
      const sx = (rect.width  - 40) / canvasSize.width;
      const sy = (rect.height - 40) / canvasSize.height;
      setGridScale(Math.max(0.1, Math.min(1, sx, sy)));
    };
    compute();
    const ro = new ResizeObserver(compute);
    ro.observe(el);
    window.addEventListener("resize", compute);
    return () => { window.removeEventListener("resize", compute); ro.disconnect(); };
  }, [gridData, viewMode, canvasSize]);

  // ---- 2D canvas draw ----
  useEffect(() => {
    if (viewMode !== "2D") return;
    const canvas = canvasRef.current;
    if (!canvas || !gridData) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    ctx.clearRect(0, 0, canvas.width, canvas.height);

    Object.entries(liveCarsRef.current).forEach(([id, [cx, cy, isInitial]]) => {
      const px = PADDING_PX + cx * (CELL_PX + GAP_PX) + CELL_PX / 2;
      const py = PADDING_PX + cy * (CELL_PX + GAP_PX) + CELL_PX / 2;
      const carLen = CELL_PX * 0.75;
      const carW   = CELL_PX * 0.45;

      ctx.save();
      ctx.translate(px, py);
      ctx.fillStyle = isInitial === 1 ? COLORS.CAR_INITIAL : COLORS.CAR_ARRIVING;
      ctx.beginPath();
      if (typeof ctx.roundRect === "function") {
        ctx.roundRect(-carLen / 2, -carW / 2, carLen, carW, 4);
      } else {
        ctx.rect(-carLen / 2, -carW / 2, carLen, carW);
      }
      ctx.fill();
      ctx.strokeStyle = "rgba(0,0,0,0.5)";
      ctx.lineWidth = 1;
      ctx.stroke();

      ctx.fillStyle = "rgba(0,0,0,0.6)";
      ctx.fillRect( carLen / 6,     -carW / 2 + 2, 3, carW - 4);
      ctx.fillRect(-carLen / 2 + 2, -carW / 2 + 2, 3, carW - 4);

      ctx.fillStyle = "rgba(255,255,200,0.9)";
      ctx.beginPath();
      ctx.arc(carLen / 2 - 2, -carW / 2 + 3, 1.5, 0, Math.PI * 2);
      ctx.arc(carLen / 2 - 2,  carW / 2 - 3, 1.5, 0, Math.PI * 2);
      ctx.fill();
      ctx.restore();

      ctx.fillStyle = COLORS.CAR_TEXT;
      ctx.font = "bold 9px sans-serif";
      ctx.textAlign = "center";
      ctx.textBaseline = "middle";
      ctx.fillText(id.slice(0, 3), px, py);
    });
  }, [renderTick, viewMode, canvasSize, gridData]);

  // ---- DOM grid rows ----
  const gridRows = useMemo(() => {
    if (!gridData) return null;
    const { width, height, cells } = gridData;
    const r = Array.from({ length: height }, () =>
      Array(width).fill(null as GridCell | null)
    );
    cells.forEach((cell) => {
      if (cell.x < width && cell.y < height) r[cell.y][cell.x] = cell;
    });
    return r;
  }, [gridData]);

  const statusLabel = wsStatus === "CONNECTING" ? "Connecting…" : wsStatus;

  return (
    <AppLayout variant="editor">
      <div className="simPage">
        {/* Header */}
        <div className="simHeader">
          <div className="simTitleGroup">
            <h1 className="simTitle">Simulation</h1>
            {wsStatus !== "IDLE" && (
              <span className={`statusBadge ${STATUS_CLASS[wsStatus] ?? "default"}`}>
                {statusLabel}
              </span>
            )}
          </div>

          <div className="simControls">
            <div
              className="viewToggle"
              style={{ marginRight: 16, borderRight: "1px solid #eee", paddingRight: 16, display: "flex", gap: "0.5rem" }}
            >
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

            {!loading && !error && (
              <>
                <span className="stepCounter">Step {liveT}</span>
                <div className="controlGroup">
                  <button className="iconBtn" onClick={handleReset} title="Reset" disabled={!isConnected}>
                    <RotateCcw size={18} />
                  </button>
                  {wsStatus === "PAUSED" ? (
                    <button className="iconBtn primary" onClick={handleResume} title="Resume">
                      <Play size={18} />
                    </button>
                  ) : (
                    <button
                      className="iconBtn primary"
                      onClick={handlePause}
                      title="Pause"
                      disabled={wsStatus !== "RUNNING"}
                    >
                      <Pause size={18} />
                    </button>
                  )}
                  <button className="iconBtn" onClick={handleStop} title="Stop" disabled={!isConnected}>
                    <Square size={18} />
                  </button>
                </div>
              </>
            )}

            <button
              className="btnGhost"
              onClick={() => { wsRef.current?.close(); nav("/layout"); }}
            >
              Close
            </button>
          </div>
        </div>

        {/* Content */}
        <div className="simContent">
          {loading && (
            <div className="loadingContainer">
              <Loader2 className="spinner" size={48} />
              <p>Connecting to simulation…</p>
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

          {!loading && !error && gridData && (
            <div className={`canvasContainer ${viewMode === "3D" ? "mode-3d" : ""}`}>
              {/* Stats Panel */}
              <div className="simStats">
                <div className="statGroup">
                  <div className="statGroupTitle">Initial Batch</div>
                  <div className="statRow">
                    <span className="statLabel">Exited</span>
                    <span className="statValue">{liveStats?.initial_active_cars_exited ?? 0}</span>
                  </div>
                  {liveStats?.average_steps_to_exit != null && (
                    <div className="statRow">
                      <span className="statLabel">Avg Steps</span>
                      <span className="statValue">{liveStats.average_steps_to_exit.toFixed(1)}</span>
                    </div>
                  )}
                </div>

                <div className="statDivider" />

                <div className="statGroup">
                  <div className="statGroupTitle">Arrivals</div>
                  <div className="statRow">
                    <span className="statLabel">Spawned</span>
                    <span className="statValue">{liveStats?.arriving_cars_spawned ?? 0}</span>
                  </div>
                  <div className="statRow">
                    <span className="statLabel">Parked</span>
                    <span className="statValue">{liveStats?.arriving_cars_parked ?? 0}</span>
                  </div>
                  {liveStats?.average_steps_to_park != null && (
                    <div className="statRow">
                      <span className="statLabel">Avg Steps</span>
                      <span className="statValue">{liveStats.average_steps_to_park.toFixed(1)}</span>
                    </div>
                  )}
                </div>

                <div className="statDivider" />

                <div className="statGroup">
                  <div className="statGroupTitle">Global</div>
                  <div className="statRow">
                    <span className="statLabel">Time</span>
                    <span className="statValue">{liveT}</span>
                  </div>
                  <div className="statRow">
                    <span className="statLabel">Failures</span>
                    <span className="statValue">{liveStats?.total_failed_plans ?? 0}</span>
                  </div>
                </div>
              </div>

              {/* Viewport */}
              {viewMode === "3D" ? (
                <div className="canvasWrapper3D">
                  <Simulation3D
                    grid={gridData}
                    timesteps={liveTimesteps.length > 0 ? liveTimesteps : [{ t: 0, cars: {} }]}
                    currentStepIndex={0}
                    stepProgress={0}
                  />
                </div>
              ) : (
                <div className="simCanvasScroll" ref={sim2DRef}>
                  {gridRows && (
                    <div className="simGridWrap" style={{ transform: `scale(${gridScale})` }}>
                      <div style={{ position: "relative" }}>
                        <div
                          className="simGrid"
                          style={{
                            gridTemplateColumns: `repeat(${gridData.width}, ${CELL_PX}px)`,
                            gridTemplateRows:    `repeat(${gridData.height}, ${CELL_PX}px)`,
                          }}
                        >
                          {gridRows.map((row, y) =>
                            row.map((cell: GridCell | null, x: number) => {
                              if (!cell) return <div key={`${x}-${y}`} className="simCell" />;
                              return (
                                <div
                                  key={`${x}-${y}`}
                                  className={`simCell cell-${cell.type}`}
                                  data-mark={
                                    cell.type === "ENTRY" ? "IN" :
                                    cell.type === "EXIT"  ? "OUT" : undefined
                                  }
                                  title={`(${x},${y}) ${cell.type}`}
                                />
                              );
                            })
                          )}
                        </div>
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