import { useMemo, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import AppLayout from "../layouts/AppLayout";
import "./SimulationConfig.css";
import bgHero from "../assets/HomePage.webp"; 

import { Car, Activity, Clock, LogOut, LogIn, Hash, Cpu, Zap, GitCompare } from "lucide-react";

type SimConfig = {
  planning_horizon: number;
  goal_reserve_horizon: number;
  arrival_lambda: number;
  exit_rate: number;
  initial_cars: number;
  max_timesteps: number;
  step_delay_ms: number;
  algorithm: string;
  headless_mode: boolean;
  comparison_mode: boolean;
  comparison_algorithms: string[];
  headless_timeout_ms?: number;
};

const ALL_ALGORITHMS: { value: string; label: string }[] = [
  { value: "priority", label: "Priority Planner" },
  { value: "lacam0",   label: "LaCAM0" },
  { value: "lns2",     label: "MAPF-LNS2" },
];

const STORAGE_KEY = "sim_config_v3";

export default function SimulationConfig() {
  const nav = useNavigate();
  const [params] = useSearchParams();
  const layoutId = params.get("layout") ?? "new";

  const [planningHorizon, setPlanningHorizon] = useState<number>(50);
  const [goalReserveHorizon, setGoalReserveHorizon] = useState<number>(200);
  const [arrivalLambda, setArrivalLambda] = useState<number>(0.3);
  const [exitRate, setExitRate] = useState<number>(0.02);
  const [initialCars, setInitialCars] = useState<number>(5);
  const [maxTimesteps, setMaxTimesteps] = useState<number>(0);
  const [stepDelayMs, setStepDelayMs] = useState<number>(100);
  const [algorithm, setAlgorithm] = useState<string>("priority");
  const [headlessMode, setHeadlessMode] = useState<boolean>(false);
  const [comparisonMode, setComparisonMode] = useState<boolean>(false);
  const [comparisonAlgorithms, setComparisonAlgorithms] = useState<string[]>(["priority", "lacam0"]);
  const [headlessTimeoutMs, setHeadlessTimeoutMs] = useState<number>(5000);

  const handleHeadlessChange = (v: boolean) => {
    setHeadlessMode(v);
    if (v) setComparisonMode(false);
  };
  const handleComparisonChange = (v: boolean) => {
    setComparisonMode(v);
    if (v) setHeadlessMode(false);
  };

  const defaults = useMemo(
    () => ({
      planning_horizon: 50,
      goal_reserve_horizon: 200,
      arrival_lambda: 0.3,
      exit_rate: 0.02,
      initial_cars: 5,
      max_timesteps: 0,
      step_delay_ms: 100,
      algorithm: "priority",
      headless_mode: false,
      comparison_mode: false,
      comparison_algorithms: ["priority", "lacam0"],
    }),
    []
  );

  const saveAndContinue = () => {
    const cfg: SimConfig = {
      planning_horizon: Math.max(1, Math.floor(planningHorizon)),
      goal_reserve_horizon: Math.max(1, Math.floor(goalReserveHorizon)),
      arrival_lambda: Math.max(0, Math.min(1, Number(arrivalLambda))),
      exit_rate: Math.max(0, Math.min(1, Number(exitRate))),
      initial_cars: Math.max(0, Math.floor(initialCars)),
      max_timesteps: Math.max(0, Math.floor(maxTimesteps)),
      step_delay_ms: Math.max(10, Math.floor(stepDelayMs)),
      algorithm,
      headless_mode: headlessMode,
      comparison_mode: comparisonMode,
      comparison_algorithms: comparisonAlgorithms,
    };

    if (headlessMode || comparisonMode) cfg.headless_timeout_ms = headlessTimeoutMs;
    sessionStorage.setItem(STORAGE_KEY, JSON.stringify(cfg));
    nav(`/simulation?layout=${encodeURIComponent(layoutId)}`);
  };

  return (
    <AppLayout variant="cinematic" bgImage={bgHero}>
      <div className="setupHeader">
        <h1 className="setupTitle">Configuration</h1>
        <p className="setupSubtitle">Configure simulation parameters for the selected parking layout.</p>
      </div>

      <div className="setupPage">
        <div className="setupGrid">
          <section className="setupCard">
            <CardHead icon={<Car size={18} />} title="Vehicle Counts" sub="Cars in the lot and flow rates." />

            <FieldRow
              icon={<Hash size={16} />}
              label="Initial Cars (t=0)"
              description="Number of cars already parked when the simulation starts. They have no goal — they will begin to leave over time based on the exit rate."
              value={initialCars}
              min={0}
              max={500}
              step={1}
              onChange={setInitialCars}
              onDefault={() => setInitialCars(defaults.initial_cars)}
            />

            <FieldRow
              icon={<LogIn size={16} />}
              label="Arrival Rate (λ)"
              description="Probability per timestep that a new car arrives at an entry cell and looks for a parking spot."
              value={arrivalLambda}
              min={0}
              max={1}
              step={0.01}
              onChange={setArrivalLambda}
              onDefault={() => setArrivalLambda(defaults.arrival_lambda)}
            />

            <FieldRow
              icon={<LogOut size={16} />}
              label="Exit Rate (per car)"
              description="Probability per timestep that each individual parked car decides to leave. Higher values = faster turnover."
              value={exitRate}
              min={0}
              max={1}
              step={0.01}
              onChange={setExitRate}
              onDefault={() => setExitRate(defaults.exit_rate)}
            />
          </section>

          <section className="setupCard">
            <CardHead icon={<Activity size={18} />} title="Simulation Parameters" sub="Timing & Pathfinding." />

            <SelectRow
              icon={<Cpu size={16} />}
              label="Algorithm"
              value={algorithm}
              options={["priority", "lacam0", "lns2"]}
              onChange={setAlgorithm}
            />

            <FieldRow
              icon={<Clock size={16} />}
              label="Step Delay (ms)"
              description="Milliseconds between timesteps — lower is faster"
              value={stepDelayMs}
              min={10}
              max={2000}
              step={10}
              onChange={setStepDelayMs}
              onDefault={() => setStepDelayMs(defaults.step_delay_ms)}
            />

            <FieldRow
              icon={<Clock size={16} />}
              label="Max Timesteps (0 = unlimited)"
              description="Simulation stops automatically after this many steps. 0 means run until you stop it."
              value={maxTimesteps}
              min={0}
              max={10000}
              step={100}
              onChange={setMaxTimesteps}
              onDefault={() => setMaxTimesteps(defaults.max_timesteps)}
            />

            <ToggleRow
              icon={<Zap size={16} />}
              label="Headless Mode"
              description="Skip live rendering — run at full speed and return final statistics only."
              hint={headlessMode && maxTimesteps === 0 ? "⚠ Max Timesteps must be ≥ 1 to use Headless Mode." : undefined}
              checked={headlessMode}
              onChange={handleHeadlessChange}
            />

            <ToggleRow
              icon={<GitCompare size={16} />}
              label="Comparison Mode"
              description="Run two algorithms on the same layout headlessly and compare results side-by-side."
              hint={
                comparisonMode && maxTimesteps === 0
                  ? "⚠ Max Timesteps must be ≥ 1 to use Comparison Mode."
                  : comparisonMode && comparisonAlgorithms.length !== 2
                  ? "⚠ Select exactly 2 algorithms to compare."
                  : undefined
              }
              checked={comparisonMode}
              onChange={handleComparisonChange}
            />

            {(headlessMode || comparisonMode) && (
              <FieldRow
                icon={<Clock size={16} />}
                label="Headless Timeout (ms)"
                description="Maximum real-time duration the headless run may take before it is stopped."
                value={headlessTimeoutMs}
                min={500}
                max={20000}
                step={500}
                onChange={setHeadlessTimeoutMs}
                onDefault={() => setHeadlessTimeoutMs(5000)}
                defaultHint="5 000 ms"
              />
            )}

            {comparisonMode && (
              <AlgorithmPicker
                all={ALL_ALGORITHMS}
                selected={comparisonAlgorithms}
                onChange={setComparisonAlgorithms}
              />
            )}

             <FieldRow
              icon={<Clock size={16} />}
              label="Planning Horizon"
              description="The number of future steps the planner looks ahead when computing paths"
              value={planningHorizon}
              min={10}
              max={200}
              step={5}
              onChange={setPlanningHorizon}
              onDefault={() => setPlanningHorizon(defaults.planning_horizon)}
            />
            
            <FieldRow
              icon={<Clock size={16} />}
              label="Goal Reserve Horizon"
              description="The duration for which a parking spot is reserved for an assigned vehicle during planning"
              value={goalReserveHorizon}
              min={10}
              max={500}
              step={10}
              onChange={setGoalReserveHorizon}
              onDefault={() => setGoalReserveHorizon(defaults.goal_reserve_horizon)}
            />
          </section>
        </div>

        <div className="setupActions">
          <button className="btnBackPrimary" onClick={() => nav(`/layout?layout=${encodeURIComponent(layoutId)}`)}>
            ← Back
          </button>

          <button
            className="btnPrimary"
            onClick={saveAndContinue}
            disabled={
              (headlessMode && maxTimesteps === 0) ||
              (comparisonMode && maxTimesteps === 0) ||
              (comparisonMode && comparisonAlgorithms.length !== 2)
            }
            title={
              comparisonMode && comparisonAlgorithms.length !== 2
                ? "Select exactly 2 algorithms to compare"
                : (headlessMode || comparisonMode) && maxTimesteps === 0
                ? "Set Max Timesteps ≥ 1 to use this mode"
                : undefined
            }
          >
            Start Simulation →
          </button>
        </div>
      </div>
    </AppLayout>
  );
}

/* ---------- small components ---------- */

function CardHead(props: { icon: React.ReactNode; title: string; sub: string }) {
  return (
    <div className="cardHead">
      <h2 className="cardTitle">
        <span className="cardIcon" aria-hidden="true">{props.icon}</span>
        {props.title}
      </h2>
      <p className="cardSub">{props.sub}</p>
    </div>
  );
}

function ToggleRow(props: {
  icon?: React.ReactNode;
  label: string;
  description?: string;
  hint?: string;
  checked: boolean;
  onChange: (v: boolean) => void;
}) {
  return (
    <div className="fieldRow">
      <div className="fieldTop">
        <span className="fieldLabel">
          {props.icon ? <span className="iconBadge" aria-hidden="true">{props.icon}</span> : null}
          {props.label}
        </span>
        <label className="toggleSwitch">
          <input
            type="checkbox"
            checked={props.checked}
            onChange={e => props.onChange(e.target.checked)}
          />
          <span className="toggleTrack">
            <span className="toggleThumb" />
          </span>
        </label>
      </div>
      {props.description ? <div className="fieldDescription">{props.description}</div> : null}
      {props.hint ? <div className="fieldHint">{props.hint}</div> : null}
    </div>
  );
}

function AlgorithmPicker(props: {
  all: { value: string; label: string }[];
  selected: string[];
  onChange: (v: string[]) => void;
}) {
  const toggle = (algo: string) => {
    if (props.selected.includes(algo)) {
      if (props.selected.length > 1) props.onChange(props.selected.filter(a => a !== algo));
    } else {
      const next = props.selected.length < 2
        ? [...props.selected, algo]
        : [props.selected[1], algo]; // replace oldest when already 2 selected
      props.onChange(next);
    }
  };
  return (
    <div className="algoPickerRow">
      <span className="algoPickerLabel">Select 2 to compare:</span>
      <div className="algoPickerChips">
        {props.all.map((algo) => {
          const sel = props.selected.includes(algo.value);
          const order = props.selected.indexOf(algo.value) + 1;
          return (
            <button
              key={algo.value}
              type="button"
              className={`algoChip${sel ? " selected" : ""}`}
              onClick={() => toggle(algo.value)}
            >
              {sel && <span className="algoChipBadge">{order}</span>}
              {algo.label}
            </button>
          );
        })}
      </div>
    </div>
  );
}

function SelectRow(props: {
  icon?: React.ReactNode;
  label: string;
  value: string;
  options: string[];
  onChange: (v: string) => void;
}) {
  return (
    <div className="fieldRow">
      <div className="fieldTop">
        <span className="fieldLabel">
          {props.icon ? <span className="iconBadge" aria-hidden="true">{props.icon}</span> : null}
          {props.label}
        </span>
      </div>
      <div className="fieldBottom" style={{ gridTemplateColumns: "1fr" }}>
        <select
          className="selectInput"
          value={props.value}
          onChange={(e) => props.onChange(e.target.value)}
        >
          {props.options.map((opt) => (
            <option key={opt} value={opt}>
              {opt}
            </option>
          ))}
        </select>
      </div>
    </div>
  );
}

function FieldRow(props: {
  icon?: React.ReactNode;
  label: string;
  description?: string;
  value: number;
  min: number;
  max: number;
  step: number;
  onChange: (v: number) => void;
  onDefault: () => void;
  defaultHint?: string;
  suffix?: string;
}) {
  const { icon, label, description, value, min, max, step, onChange, onDefault, defaultHint, suffix } = props;

  return (
    <div className="fieldRow">
      <div className="fieldTop">
        <span className="fieldLabel">
          {icon ? <span className="iconBadge" aria-hidden="true">{icon}</span> : null}
          {label}
        </span>

        <button type="button" className="miniPill" onClick={onDefault}>
          {defaultHint ?? "default"}
        </button>
      </div>

      {description ? <div className="fieldDescription">{description}</div> : null}

      <div className="fieldBottom">
        <input
          className="numInput"
          type="number"
          value={Number.isFinite(value) ? value : 0}
          min={min}
          max={max}
          step={step}
          onChange={(e) => onChange(Number(e.target.value))}
        />

        <input
          className="rangeInput"
          type="range"
          value={Number.isFinite(value) ? value : 0}
          min={min}
          max={max}
          step={step}
          onChange={(e) => onChange(Number(e.target.value))}
        />

        <span className="fieldUnit">{suffix ?? ""}</span>
      </div>
    </div>
  );
}