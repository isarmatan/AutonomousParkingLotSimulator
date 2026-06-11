import { useState, useEffect, useMemo } from "react";
import { useNavigate } from "react-router-dom";
import AppLayout from "../layouts/AppLayout";
import "./SimulationConfig.css";
import "./BatchSimulationConfig.css";
import bgHero from "../assets/HomePage.webp";
import {
  Layers, Plus, Trash2, Play, RotateCcw, CheckCircle2,
  XCircle, Loader2, Cpu, Hash, LogIn, LogOut, Clock,
  Database, Zap, Save, X, Copy, FolderOpen,
} from "lucide-react";

// ─── Types ────────────────────────────────────────────────────────────────────

type HeadlessResult = {
  mode: string;
  algorithm: string;
  max_steps: number;
  completed_steps: number;
  stopped_reason: string;
  status: string;
  grid_width: number;
  grid_height: number;
  parking_lot_id?: string;
  initial_cars_configured: number;
  max_arriving_cars_configured: number;
  total_cars: number;
  total_parked: number;
  total_failed_plans: number;
  total_exited: number;
  arriving_cars_spawned: number;
  arriving_cars_parked: number;
  average_steps_to_park?: number;
  average_steps_to_exit?: number;
  avg_trip_duration_steps?: number;
  max_trip_duration_steps?: number;
  min_trip_duration_steps?: number;
  total_completed_trips: number;
  avg_planner_ms?: number;
  max_planner_ms?: number;
  planner_call_count: number;
  cpu_usage_avg_percent?: number;
  cpu_usage_peak_percent?: number;
  memory_usage_avg_mb?: number;
  memory_usage_peak_mb?: number;
};

type BatchSimEntry = {
  id: string;
  algorithm: string;
  planning_horizon: number;
  goal_reserve_horizon: number;
  arrival_lambda: number;
  exit_rate: number;
  initial_cars: number;
  max_arriving_cars: number;
  max_timesteps: number;
  layout_source: "generate" | "load";
  layout_width: number;
  layout_height: number;
  layout_entries: number;
  layout_exits: number;
  layout_parking_spots: number;
  layout_parking_lot_id: string;
  layout_parking_lot_name: string;
};

type BatchSimStatus = "pending" | "running" | "success" | "failed";

type BatchSimState = {
  entry: BatchSimEntry;
  status: BatchSimStatus;
  result?: HeadlessResult;
  error?: string;
};

// ─── Constants ────────────────────────────────────────────────────────────────

const API_URL = "http://127.0.0.1:8000";
const MAX_BATCH = 20;

const ALGO_OPTIONS = [
  { value: "priority", label: "Priority Planner" },
  { value: "lacam0",   label: "LaCAM0" },
  { value: "lns2",     label: "MAPF-LNS2" },
];

const DEFAULTS: Omit<BatchSimEntry, "id"> = {
  algorithm: "priority",
  planning_horizon: 50,
  goal_reserve_horizon: 200,
  arrival_lambda: 0.3,
  exit_rate: 0.02,
  initial_cars: 5,
  max_arriving_cars: 0,
  max_timesteps: 1000,
  layout_source: "generate",
  layout_width: 20,
  layout_height: 20,
  layout_entries: 1,
  layout_exits: 1,
  layout_parking_spots: 20,
  layout_parking_lot_id: "",
  layout_parking_lot_name: "",
};

function makeEntry(): BatchSimEntry {
  return { ...DEFAULTS, id: crypto.randomUUID() };
}

// ─── Main Component ───────────────────────────────────────────────────────────

export default function BatchSimulationConfig() {
  const nav = useNavigate();

  const [phase, setPhase] = useState<"config" | "running" | "results">("config");
  const [batchSims, setBatchSims] = useState<BatchSimState[]>([
  ]);
  // separate init below
  const [_init] = useState(() => { setBatchSims([{ entry: makeEntry(), status: "pending" }]); return null; });
  void _init;
  const [savedIds, setSavedIds] = useState<Set<string>>(new Set());
  const [savingAll, setSavingAll] = useState(false);
  const [batchTimeoutMs, setBatchTimeoutMs] = useState(5000);
  // ── Validation ────────────────────────────────────────────────────────────
  const simErrors = batchSims.map(s => {
    if (s.entry.max_timesteps < 1) return "Max Timesteps must be ≥ 1";
    if (s.entry.layout_source === "load" && s.entry.layout_parking_lot_id.trim() === "") return "Enter a Parking Lot ID";
    if (s.entry.layout_source === "generate" && (s.entry.layout_width < 5 || s.entry.layout_height < 5)) return "Width & Height must be ≥ 5";
    return null;
  });
  const canRun = simErrors.every(e => e === null);

  // ── Helpers ───────────────────────────────────────────────────────────────
  const addSim = () => {
    if (batchSims.length >= MAX_BATCH) return;
    setBatchSims(prev => [...prev, { entry: makeEntry(), status: "pending" }]);
  };

  const deleteSim = (id: string) => {
    if (batchSims.length <= 1) return;
    setBatchSims(prev => prev.filter(s => s.entry.id !== id));
  };

  const duplicateSim = (id: string) => {
    if (batchSims.length >= MAX_BATCH) return;
    setBatchSims(prev => {
      const idx = prev.findIndex(s => s.entry.id === id);
      if (idx === -1) return prev;
      const copy: BatchSimState = { entry: { ...prev[idx].entry, id: crypto.randomUUID() }, status: "pending" };
      const next = [...prev];
      next.splice(idx + 1, 0, copy);
      return next;
    });
  };

  const markSaved = (id: string) => setSavedIds(prev => new Set([...prev, id]));

  const saveAll = async () => {
    if (savingAll) return;
    setSavingAll(true);
    const toSave = batchSims
      .map((s, i) => ({ sim: s, idx: i }))
      .filter(({ sim }) => sim.status === "success" && !savedIds.has(sim.entry.id));
    for (const { sim, idx } of toSave) {
      try {
        const res = await fetch(`${API_URL}/simulation/headless/save`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            name: (() => {
              const ln = sim.entry.layout_source === "load"
                ? (sim.entry.layout_parking_lot_name || "Saved Lot")
                : `${sim.entry.layout_width}\u00d7${sim.entry.layout_height} Grid`;
              const d = new Date();
              const ts = d.toLocaleString("en-GB", { day: "2-digit", month: "short", hour: "2-digit", minute: "2-digit" });
              return `${ln} \u2013 ${sim.entry.algorithm} \u2013 Batch ${idx + 1} (${ts})`;
            })(),
            result: sim.result,
            config_json: JSON.stringify(sim.entry),
          }),
        });
        if (res.ok) markSaved(sim.entry.id);
      } catch { /* skip individual failures */ }
    }
    setSavingAll(false);
  };

  const updateEntry = (id: string, field: keyof Omit<BatchSimEntry, "id">, value: string | number) => {
    setBatchSims(prev =>
      prev.map(s => s.entry.id === id ? { ...s, entry: { ...s.entry, [field]: value } } : s)
    );
  };

  // ── Run ───────────────────────────────────────────────────────────────────
  const runBatch = async () => {
    const initial = batchSims.map(s => ({ ...s, status: "pending" as BatchSimStatus, result: undefined, error: undefined }));
    setBatchSims(initial);
    setPhase("running");

    for (let i = 0; i < initial.length; i++) {
      setBatchSims(prev => prev.map((s, idx) => idx === i ? { ...s, status: "running" } : s));

      const entry = initial[i].entry;
      const payload: Record<string, unknown> = {
        planning_horizon: entry.planning_horizon,
        goal_reserve_horizon: entry.goal_reserve_horizon,
        arrival_lambda: entry.arrival_lambda,
        exit_rate: entry.exit_rate,
        initial_cars: entry.initial_cars,
        max_arriving_cars: entry.max_arriving_cars,
        algorithm: entry.algorithm,
        max_steps: entry.max_timesteps,
      };

      payload.step_timeout_ms = batchTimeoutMs;

      if (entry.layout_source === "generate") {
        payload.source = "generate";
        payload.width = entry.layout_width;
        payload.height = entry.layout_height;
        payload.rules = {
          num_entries: entry.layout_entries,
          num_exits: entry.layout_exits,
          num_parking_spots: entry.layout_parking_spots,
        };
      } else {
        payload.source = "load";
        payload.parkingLotId = entry.layout_parking_lot_id.trim();
      }

      try {
        const res = await fetch(`${API_URL}/simulation/headless`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload),
        });
        if (!res.ok) {
          const txt = await res.text();
          throw new Error(`HTTP ${res.status}: ${txt}`);
        }
        const result: HeadlessResult = await res.json();
        setBatchSims(prev => prev.map((s, idx) => idx === i ? { ...s, status: "success", result } : s));
      } catch (err) {
        const msg = err instanceof Error ? err.message : String(err);
        setBatchSims(prev => prev.map((s, idx) => idx === i ? { ...s, status: "failed", error: msg } : s));
      }
    }

    setPhase("results");
  };

  const resetToConfig = () => {
    setBatchSims(prev => prev.map(s => ({ ...s, status: "pending", result: undefined, error: undefined })));
    setPhase("config");
  };

  // ── Render ────────────────────────────────────────────────────────────────
  const successCount = batchSims.filter(s => s.status === "success").length;
  const totalCount   = batchSims.length;

  return (
    <AppLayout variant="cinematic" bgImage={bgHero}>
      {/* Header */}
      <div className="setupHeader">
        <h1 className="setupTitle">
          <span style={{ marginRight: 10, color: "#34d399" }}>⠿</span>
          Batch Simulation
        </h1>
        <p className="setupSubtitle">
          {phase === "config"   && `Configure up to ${MAX_BATCH} independent simulations and run them all headlessly.`}
          {phase === "running"  && `Running ${totalCount} simulation${totalCount !== 1 ? "s" : ""} sequentially…`}
          {phase === "results"  && `Batch complete — ${successCount} / ${totalCount} succeeded.`}
        </p>
      </div>

      {/* ── CONFIG PHASE ── */}
      {phase === "config" && (
        <div className="setupPage">
          {/* Global timeout */}
          <section className="setupCard" style={{ padding: "1.2rem 1.5rem" }}>
            <div style={{ display: "flex", alignItems: "center", gap: 16, flexWrap: "wrap" }}>
              <span style={{ fontSize: "0.85rem", fontWeight: 700, color: "#94a3b8", textTransform: "uppercase", letterSpacing: "0.05em", flexShrink: 0 }}>
                <Zap size={14} style={{ marginRight: 6, verticalAlign: "middle", color: "#f59e0b" }} />
                Headless Timeout
              </span>
              <input
                className="numInput"
                type="number"
                min={500}
                max={20000}
                step={500}
                value={batchTimeoutMs}
                onChange={e => setBatchTimeoutMs(Math.min(20000, Math.max(500, Number(e.target.value))))}
                style={{ width: 100 }}
              />
              <input
                className="rangeInput"
                type="range"
                min={500}
                max={20000}
                step={500}
                value={batchTimeoutMs}
                onChange={e => setBatchTimeoutMs(Number(e.target.value))}
                style={{ flex: 1, minWidth: 120, maxWidth: 300 }}
              />
              <span style={{ fontSize: "0.8rem", color: "#64748b", flexShrink: 0 }}>{(batchTimeoutMs / 1000).toFixed(1)} s per simulation</span>
            </div>
          </section>

          {/* Simulation Blocks */}
          {batchSims.map((sim, idx) => (
            <SimBlock
              key={sim.entry.id}
              index={idx}
              entry={sim.entry}
              error={simErrors[idx]}
              canDelete={batchSims.length > 1}
              canDuplicate={batchSims.length < MAX_BATCH}
              onChange={(field, value) => updateEntry(sim.entry.id, field, value)}
              onDelete={() => deleteSim(sim.entry.id)}
              onDuplicate={() => duplicateSim(sim.entry.id)}
            />
          ))}

          {/* Add button */}
          {batchSims.length < MAX_BATCH && (
            <button className="batchAddBtn" onClick={addSim}>
              <Plus size={16} />
              Add Simulation
              <span className="batchAddCount">{batchSims.length} / {MAX_BATCH}</span>
            </button>
          )}
          {batchSims.length >= MAX_BATCH && (
            <div className="batchMaxNote">Maximum of {MAX_BATCH} simulations reached.</div>
          )}

          {/* Actions */}
          <div className="setupActions">
            <button className="btnBackPrimary" onClick={() => nav("/mode-select")}>
              ← Back
            </button>
            <button
              className="btnStart"
              onClick={runBatch}
              disabled={!canRun}
              title={!canRun ? "Fix validation errors above before running" : undefined}
            >
              <Play size={18} style={{ marginRight: 8 }} />
              Run {totalCount} Simulation{totalCount !== 1 ? "s" : ""}
            </button>
          </div>
        </div>
      )}

      {/* ── RUNNING PHASE ── */}
      {phase === "running" && (
        <div className="setupPage">
          <section className="setupCard">
            <div className="cardHead">
              <h2 className="cardTitle">
                <span className="cardIcon"><Zap size={18} /></span>
                Running Batch…
              </h2>
              <p className="cardSub">Simulations run sequentially. Please wait.</p>
            </div>
            <div className="batchRunList">
              {batchSims.map((sim, idx) => (
                <div key={sim.entry.id} className={`batchRunRow batchRunRow--${sim.status}`}>
                  <div className="batchRunIcon">
                    {sim.status === "pending"  && <span className="batchDot batchDot--pending" />}
                    {sim.status === "running"  && <Loader2 size={16} className="batchSpinner" />}
                    {sim.status === "success"  && <CheckCircle2 size={16} color="#34d399" />}
                    {sim.status === "failed"   && <XCircle size={16} color="#f87171" />}
                  </div>
                  <span className="batchRunLabel">Simulation {idx + 1}</span>
                  <span className="batchRunAlgo">{ALGO_OPTIONS.find(a => a.value === sim.entry.algorithm)?.label}</span>
                  <span className="batchRunSteps">{sim.entry.max_timesteps.toLocaleString()} steps</span>
                  <span className={`batchRunStatus batchRunStatus--${sim.status}`}>
                    {sim.status === "pending" && "Waiting"}
                    {sim.status === "running" && "Running…"}
                    {sim.status === "success" && "Done"}
                    {sim.status === "failed"  && "Failed"}
                  </span>
                </div>
              ))}
            </div>
          </section>
        </div>
      )}

      {/* ── RESULTS PHASE ── */}
      {phase === "results" && (
        <div className="setupPage">
          {/* Summary */}
          <section className={`setupCard ${successCount === totalCount ? "highlight" : successCount === 0 ? "setupCard--error" : ""}`}>
            <div className="cardHead">
              <h2 className="cardTitle">
                <span className="cardIcon"><CheckCircle2 size={18} /></span>
                Batch Complete
              </h2>
              <p className="cardSub">
                {successCount} of {totalCount} simulation{totalCount !== 1 ? "s" : ""} succeeded.
                {successCount < totalCount && ` ${totalCount - successCount} failed.`}
              </p>
            </div>
            <div className="setupActions">
              <button className="btnBackPrimary" onClick={() => nav("/mode-select")}>
                ← Back to Modes
              </button>
              <button className="btnPrimary" onClick={resetToConfig}>
                <RotateCcw size={15} style={{ marginRight: 6 }} />
                Edit & Re-run
              </button>
            </div>
          </section>

          {/* Per-simulation result cards */}
          {/* Save All */}
          {batchSims.some(s => s.status === "success" && !savedIds.has(s.entry.id)) && (
            <div className="batchSaveAllRow">
              <button className="batchSaveAllBtn" onClick={saveAll} disabled={savingAll}>
                {savingAll
                  ? <><Loader2 size={15} className="batchSpinner" style={{ marginRight: 7 }} />Saving…</>
                  : <><Save size={15} style={{ marginRight: 7 }} />Save All Results</>
                }
              </button>
            </div>
          )}

          {batchSims.map((sim, idx) => (
            <SimResultCard
              key={sim.entry.id}
              index={idx}
              sim={sim}
              isSaved={savedIds.has(sim.entry.id)}
              onSaved={() => markSaved(sim.entry.id)}
            />
          ))}
        </div>
      )}
    </AppLayout>
  );
}

// ─── Sub-components ───────────────────────────────────────────────────────────

function SimBlock({
  index, entry, error, canDelete, canDuplicate, onChange, onDelete, onDuplicate,
}: {
  index: number;
  entry: BatchSimEntry;
  error: string | null;
  canDelete: boolean;
  canDuplicate: boolean;
  onChange: (field: keyof Omit<BatchSimEntry, "id">, value: string | number) => void;
  onDelete: () => void;
  onDuplicate: () => void;
}) {
  const [showPicker, setShowPicker] = useState(false);

  return (
    <section className="setupCard batchSimBlock">
      {showPicker && (
        <LayoutPickerModal
          onSelect={(id, name, entries, exits, spots) => {
            onChange("layout_parking_lot_id", id);
            onChange("layout_parking_lot_name", name);
            onChange("layout_entries", entries);
            onChange("layout_exits", exits);
            onChange("layout_parking_spots", spots);
          }}
          onClose={() => setShowPicker(false)}
        />
      )}
      {/* Block header */}
      <div className="batchBlockHeader">
        <div className="cardHead" style={{ marginBottom: 0 }}>
          <h2 className="cardTitle">
            <span className="cardIcon"><Layers size={18} /></span>
            Simulation {index + 1}
          </h2>
        </div>
        <div className="batchBlockActions">
          <button
            className="batchDuplicateBtn"
            onClick={onDuplicate}
            disabled={!canDuplicate}
            title={canDuplicate ? "Duplicate this simulation" : "Batch limit reached"}
          >
            <Copy size={14} />
          </button>
          <button
            className="batchDeleteBtn"
            onClick={onDelete}
            disabled={!canDelete}
            title={canDelete ? "Delete this simulation" : "Cannot delete the last simulation"}
          >
            <Trash2 size={15} />
          </button>
        </div>
      </div>

      {/* ── Parking Lot ── */}
      <div className="batchSimLayoutSection">
        <div className="fieldRow" style={{ borderTop: "none", paddingTop: 0 }}>
          <div className="fieldTop">
            <span className="fieldLabel"><span className="iconBadge"><Database size={14} /></span>Parking Lot</span>
          </div>
          <div className="batchLayoutToggle" style={{ marginBottom: 0 }}>
            <button
              className={`batchSourceBtn${entry.layout_source === "generate" ? " active" : ""}`}
              onClick={() => onChange("layout_source", "generate")}
            >Generate new</button>
            <button
              className={`batchSourceBtn${entry.layout_source === "load" ? " active" : ""}`}
              onClick={() => onChange("layout_source", "load")}
            >Load saved</button>
          </div>
        </div>
        {entry.layout_source === "generate" && (
          <div className="batchLayoutGrid">
            <BatchNum label="Width"         value={entry.layout_width}         min={5}  max={200} onChange={v => onChange("layout_width", v)} />
            <BatchNum label="Height"        value={entry.layout_height}        min={5}  max={200} onChange={v => onChange("layout_height", v)} />
            <BatchNum label="Entries"       value={entry.layout_entries}       min={1}  max={10}  onChange={v => onChange("layout_entries", v)} />
            <BatchNum label="Exits"         value={entry.layout_exits}         min={1}  max={10}  onChange={v => onChange("layout_exits", v)} />
            <BatchNum label="Parking Spots" value={entry.layout_parking_spots} min={1}  max={500} onChange={v => onChange("layout_parking_spots", v)} />
          </div>
        )}
        {entry.layout_source === "load" && (
          <div className="batchLayoutPickerRow">
            {entry.layout_parking_lot_id ? (
              <div className="batchLayoutSelected">
                <span className="batchLayoutSelectedName">{entry.layout_parking_lot_name || entry.layout_parking_lot_id}</span>
                <button className="batchLayoutChangeBtn" onClick={() => setShowPicker(true)}>
                  <FolderOpen size={13} style={{ marginRight: 5 }} />Change
                </button>
              </div>
            ) : (
              <button className="batchLayoutChooseBtn" onClick={() => setShowPicker(true)}>
                <FolderOpen size={15} style={{ marginRight: 8 }} />
                Choose a Saved Layout…
              </button>
            )}
          </div>
        )}
      </div>

      <div className="batchFieldGrid">
        {/* Algorithm */}
        <div className="fieldRow">
          <div className="fieldTop">
            <span className="fieldLabel"><span className="iconBadge"><Cpu size={14} /></span>Algorithm</span>
          </div>
          <div className="fieldBottom" style={{ gridTemplateColumns: "1fr" }}>
            <select
              className="selectInput"
              value={entry.algorithm}
              onChange={e => onChange("algorithm", e.target.value)}
            >
              {ALGO_OPTIONS.map(a => <option key={a.value} value={a.value}>{a.label}</option>)}
            </select>
          </div>
        </div>

        {/* Max Timesteps */}
        <div className="fieldRow">
          <div className="fieldTop">
            <span className="fieldLabel"><span className="iconBadge"><Clock size={14} /></span>Max Timesteps</span>
          </div>
          <div className="fieldBottom" style={{ gridTemplateColumns: "90px 1fr" }}>
            <input className="numInput" type="number" min={1} max={100000} step={100}
              value={entry.max_timesteps}
              onChange={e => onChange("max_timesteps", Math.max(1, Number(e.target.value)))} />
            <input className="rangeInput" type="range" min={100} max={10000} step={100}
              value={entry.max_timesteps}
              onChange={e => onChange("max_timesteps", Number(e.target.value))} />
          </div>
          {error && <div className="fieldHint">{error}</div>}
        </div>

        {/* Initial Cars */}
        <div className="fieldRow">
          <div className="fieldTop">
            <span className="fieldLabel"><span className="iconBadge"><Hash size={14} /></span>Initial Cars</span>
          </div>
          <div className="fieldBottom" style={{ gridTemplateColumns: "90px 1fr" }}>
            <input className="numInput" type="number" min={0} max={500} step={1}
              value={entry.initial_cars}
              onChange={e => onChange("initial_cars", Math.max(0, Number(e.target.value)))} />
            <input className="rangeInput" type="range" min={0} max={100} step={1}
              value={entry.initial_cars}
              onChange={e => onChange("initial_cars", Number(e.target.value))} />
          </div>
        </div>

        {/* Arrival Rate */}
        <div className="fieldRow">
          <div className="fieldTop">
            <span className="fieldLabel"><span className="iconBadge"><LogIn size={14} /></span>Arrival Rate (λ)</span>
          </div>
          <div className="fieldBottom" style={{ gridTemplateColumns: "90px 1fr" }}>
            <input className="numInput" type="number" min={0} max={1} step={0.01}
              value={entry.arrival_lambda}
              onChange={e => onChange("arrival_lambda", Math.min(1, Math.max(0, Number(e.target.value))))} />
            <input className="rangeInput" type="range" min={0} max={1} step={0.01}
              value={entry.arrival_lambda}
              onChange={e => onChange("arrival_lambda", Number(e.target.value))} />
          </div>
        </div>

        {/* Exit Rate */}
        <div className="fieldRow">
          <div className="fieldTop">
            <span className="fieldLabel"><span className="iconBadge"><LogOut size={14} /></span>Exit Rate</span>
          </div>
          <div className="fieldBottom" style={{ gridTemplateColumns: "90px 1fr" }}>
            <input className="numInput" type="number" min={0} max={1} step={0.01}
              value={entry.exit_rate}
              onChange={e => onChange("exit_rate", Math.min(1, Math.max(0, Number(e.target.value))))} />
            <input className="rangeInput" type="range" min={0} max={1} step={0.01}
              value={entry.exit_rate}
              onChange={e => onChange("exit_rate", Number(e.target.value))} />
          </div>
        </div>

        {/* Max Arriving Cars */}
        <div className="fieldRow">
          <div className="fieldTop">
            <span className="fieldLabel"><span className="iconBadge"><Hash size={14} /></span>Max Arriving Cars <small style={{color:"#64748b"}}>(0 = ∞)</small></span>
          </div>
          <div className="fieldBottom" style={{ gridTemplateColumns: "90px 1fr" }}>
            <input className="numInput" type="number" min={0} max={10000} step={10}
              value={entry.max_arriving_cars}
              onChange={e => onChange("max_arriving_cars", Math.max(0, Number(e.target.value)))} />
            <input className="rangeInput" type="range" min={0} max={500} step={10}
              value={entry.max_arriving_cars}
              onChange={e => onChange("max_arriving_cars", Number(e.target.value))} />
          </div>
        </div>

        {/* Planning Horizon */}
        <div className="fieldRow">
          <div className="fieldTop">
            <span className="fieldLabel"><span className="iconBadge"><Clock size={14} /></span>Planning Horizon</span>
          </div>
          <div className="fieldBottom" style={{ gridTemplateColumns: "90px 1fr" }}>
            <input className="numInput" type="number" min={10} max={200} step={5}
              value={entry.planning_horizon}
              onChange={e => onChange("planning_horizon", Number(e.target.value))} />
            <input className="rangeInput" type="range" min={10} max={200} step={5}
              value={entry.planning_horizon}
              onChange={e => onChange("planning_horizon", Number(e.target.value))} />
          </div>
        </div>

        {/* Goal Reserve Horizon */}
        <div className="fieldRow">
          <div className="fieldTop">
            <span className="fieldLabel"><span className="iconBadge"><Clock size={14} /></span>Goal Reserve Horizon</span>
          </div>
          <div className="fieldBottom" style={{ gridTemplateColumns: "90px 1fr" }}>
            <input className="numInput" type="number" min={10} max={500} step={10}
              value={entry.goal_reserve_horizon}
              onChange={e => onChange("goal_reserve_horizon", Number(e.target.value))} />
            <input className="rangeInput" type="range" min={10} max={500} step={10}
              value={entry.goal_reserve_horizon}
              onChange={e => onChange("goal_reserve_horizon", Number(e.target.value))} />
          </div>
        </div>
      </div>
    </section>
  );
}

function BatchNum({ label, value, min, max, onChange }: {
  label: string; value: number; min: number; max: number;
  onChange: (v: number) => void;
}) {
  return (
    <div className="batchNumCell">
      <label className="batchNumLabel">{label}</label>
      <input
        className="numInput"
        type="number"
        min={min}
        max={max}
        value={value}
        onChange={e => onChange(Number(e.target.value))}
        style={{ width: "100%" }}
      />
    </div>
  );
}

function formatHeadlessStatus(status: string): string {
  if (status === "COMPLETED")         return "All Cars Done";
  if (status === "MAX_STEPS_REACHED") return "Max Steps Reached";
  if (status === "TIMEOUT")           return "Timed Out";
  return status.replace(/_/g, " ");
}

function SimResultCard({ index, sim, isSaved, onSaved }: {
  index: number;
  sim: BatchSimState;
  isSaved: boolean;
  onSaved: () => void;
}) {
  const r = sim.result;
  const algoLabel = ALGO_OPTIONS.find(a => a.value === sim.entry.algorithm)?.label ?? sim.entry.algorithm;
  const layoutName = sim.entry.layout_source === "load"
    ? (sim.entry.layout_parking_lot_name || "Saved Lot")
    : `${sim.entry.layout_width}\u00d7${sim.entry.layout_height} Grid`;
  const [showSaveInput, setShowSaveInput] = useState(false);
  const [saveName, setSaveName] = useState(() => {
    const d = new Date();
    const ts = d.toLocaleString("en-GB", { day: "2-digit", month: "short", hour: "2-digit", minute: "2-digit" });
    return `${layoutName} \u2013 ${algoLabel} \u2013 ${ts}`;
  });
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);

  const handleSave = async () => {
    setSaving(true);
    setSaveError(null);
    try {
      const res = await fetch(`${API_URL}/simulation/headless/save`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          name: saveName.trim() || `Simulation ${index + 1}`,
          result: r,
          config_json: JSON.stringify(sim.entry),
        }),
      });
      if (!res.ok) {
        const txt = await res.text();
        throw new Error(`HTTP ${res.status}: ${txt}`);
      }
      onSaved();
      setShowSaveInput(false);
    } catch (err) {
      setSaveError(err instanceof Error ? err.message : String(err));
    } finally {
      setSaving(false);
    }
  };

  return (
    <section className={`setupCard batchResultCard batchResultCard--${sim.status}`}>
      {/* Card header */}
      <div className="batchResultHeader">
        <div className="batchResultTitle">
          <span className="batchResultIndex">Simulation {index + 1}</span>
          <span className="batchAlgoBadge">{algoLabel}</span>
          <span className={`batchStatusBadge batchStatusBadge--${sim.status}${r?.status === "TIMEOUT" ? " batchStatusBadge--timeout" : ""}`}>
            {sim.status === "success" && formatHeadlessStatus(r?.status ?? "")}
            {sim.status === "failed"  && "Failed"}
            {sim.status === "pending" && "Pending"}
            {sim.status === "running" && "Running"}
          </span>
        </div>
        {r && (
          <div className="batchResultMeta">
            <span>{r.completed_steps.toLocaleString()} steps</span>
            <span>·</span>
            <span>{r.grid_width}×{r.grid_height} grid</span>
            <span>·</span>
            <span>{formatHeadlessStatus(r.status)}</span>
          </div>
        )}
      </div>

      {/* Error */}
      {sim.status === "failed" && sim.error && (
        <div className="batchErrorMsg">{sim.error}</div>
      )}

      {/* Stats grid */}
      {r && (
        <div className="batchStatGrid">
          <StatCard title="Exited"        val={r.total_exited}
            sub={`avg ${r.average_steps_to_exit?.toFixed(1) ?? "—"} steps`} />
          <StatCard title="Arrivals Parked" val={`${r.arriving_cars_parked} / ${r.arriving_cars_spawned}`}
            sub={`avg ${r.average_steps_to_park?.toFixed(1) ?? "—"} steps`} />
          <StatCard title="Failures"      val={r.total_failed_plans}
            sub="planning errors" />
          <StatCard title="Avg Trip"      val={r.avg_trip_duration_steps?.toFixed(1) ?? "—"}
            sub={`steps · ${r.total_completed_trips} trips`} />
          <StatCard title="Trip Range"    val={`${r.min_trip_duration_steps ?? "—"} – ${r.max_trip_duration_steps ?? "—"}`}
            sub="min – max steps" />
          <StatCard title="Avg Plan Time" val={r.avg_planner_ms != null ? `${r.avg_planner_ms.toFixed(2)} ms` : "—"}
            sub={`peak ${r.max_planner_ms?.toFixed(2) ?? "—"} ms`} />
          {r.cpu_usage_avg_percent != null && (
            <StatCard title="CPU Avg"     val={`${r.cpu_usage_avg_percent}%`}
              sub={`peak ${r.cpu_usage_peak_percent}%`} />
          )}
          {r.memory_usage_avg_mb != null && (
            <StatCard title="Memory Avg"  val={`${r.memory_usage_avg_mb} MB`}
              sub={`peak ${r.memory_usage_peak_mb} MB`} />
          )}
        </div>
      )}

      {/* Save */}
      {sim.status === "success" && r && (
        <div className="batchSaveRow">
          {isSaved ? (
            <span className="batchSavedBadge">
              <CheckCircle2 size={14} style={{ marginRight: 5 }} />
              Saved to history
            </span>
          ) : showSaveInput ? (
            <div className="batchSaveInputRow">
              <input
                className="numInput batchSaveNameInput"
                type="text"
                value={saveName}
                onChange={e => setSaveName(e.target.value)}
                placeholder="Enter a name…"
                onKeyDown={e => { if (e.key === "Enter") handleSave(); if (e.key === "Escape") { setShowSaveInput(false); setSaveError(null); } }}
                autoFocus
              />
              <button className="batchSaveConfirmBtn" onClick={handleSave} disabled={saving}>
                {saving ? <Loader2 size={14} className="batchSpinner" /> : <><Save size={13} style={{ marginRight: 5 }} />Save</>}
              </button>
              <button className="batchSaveCancelBtn" onClick={() => { setShowSaveInput(false); setSaveError(null); }} disabled={saving}>
                <X size={14} />
              </button>
            </div>
          ) : (
            <button className="batchSaveBtn" onClick={() => setShowSaveInput(true)}>
              <Save size={14} style={{ marginRight: 7 }} />
              Save Result
            </button>
          )}
          {saveError && <div className="batchSaveError">{saveError}</div>}
        </div>
      )}
    </section>
  );
}

function StatCard({ title, val, sub }: { title: string; val: string | number; sub: string }) {
  return (
    <div className="batchStatCard">
      <div className="batchStatTitle">{title}</div>
      <div className="batchStatVal">{val}</div>
      <div className="batchStatSub">{sub}</div>
    </div>
  );
}

// ─── Layout Picker Modal ──────────────────────────────────────────────────────

type PickerLayout = { id: string; name: string; entries: number; exits: number; spots: number; size: string; note: string; };

function LayoutPickerModal({ onSelect, onClose }: {
  onSelect: (id: string, name: string, entries: number, exits: number, spots: number) => void;
  onClose: () => void;
}) {
  const [layouts, setLayouts] = useState<PickerLayout[]>([]);
  const [loading, setLoading] = useState(true);
  const [fetchError, setFetchError] = useState<string | null>(null);
  const [q, setQ] = useState("");

  useEffect(() => {
    fetch(`${API_URL}/editor/saved`)
      .then(r => {
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        return r.json();
      })
      .then(data => {
        setLayouts((data.items || []).map((item: Record<string, unknown>) => ({
          id: item.id as string,
          name: (item.name as string) || "Untitled Layout",
          entries: (item.num_entries as number) || 0,
          exits: (item.num_exits as number) || 0,
          spots: (item.capacity as number) || 0,
          size: `${item.width}\u00d7${item.height}`,
          note: `Entries: ${item.num_entries}, Exits: ${item.num_exits}`,
        })));
      })
      .catch(e => setFetchError(e instanceof Error ? e.message : String(e)))
      .finally(() => setLoading(false));
  }, []);

  const filtered = useMemo(() => {
    const s = q.trim().toLowerCase();
    return s ? layouts.filter(l => l.name.toLowerCase().includes(s)) : layouts;
  }, [q, layouts]);

  return (
    <div className="batchPickerOverlay" onClick={onClose}>
      <div className="batchPickerBox" onClick={e => e.stopPropagation()}>
        <div className="batchPickerHeader">
          <span className="batchPickerTitle">Choose a Saved Layout</span>
          <button className="batchPickerClose" onClick={onClose}><X size={18} /></button>
        </div>
        <div className="batchPickerSearch">
          <FolderOpen size={15} className="batchPickerSearchIcon" />
          <input
            className="batchPickerSearchInput"
            placeholder="Search layouts…"
            value={q}
            onChange={e => setQ(e.target.value)}
            autoFocus
          />
        </div>
        <div className="batchPickerList">
          {loading && <div className="batchPickerState">Loading layouts…</div>}
          {fetchError && <div className="batchPickerState batchPickerState--error">Error: {fetchError}</div>}
          {!loading && !fetchError && filtered.length === 0 && (
            <div className="batchPickerState">No layouts found.</div>
          )}
          {!loading && filtered.map(l => (
            <button
              key={l.id}
              className="batchPickerCard"
              onClick={() => { onSelect(l.id, l.name, l.entries, l.exits, l.spots); onClose(); }}
            >
              <div className="batchPickerCardName">{l.name}</div>
              <div className="batchPickerCardMeta">{l.size} · {l.spots} spots · {l.note}</div>
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}
