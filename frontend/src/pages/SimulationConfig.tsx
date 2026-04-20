import { useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import AppLayout from "../layouts/AppLayout";
import "./SimulationConfig.css";
import bgHero from "../assets/HomePage.webp"; 

import { Car, Activity, Clock, LogOut, LogIn, Hash, Cpu } from "lucide-react";

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

const STORAGE_KEY = "sim_config_v1";

export default function SimulationConfig() {
  const nav = useNavigate();

  // State matching backend API
  const [planningHorizon, setPlanningHorizon] = useState<number>(50);
  const [goalReserveHorizon, setGoalReserveHorizon] = useState<number>(200);
  const [arrivalLambda, setArrivalLambda] = useState<number>(1);
  const [maxArrivingCars, setMaxArrivingCars] = useState<number>(1);
  const [initialParkedCars, setInitialParkedCars] = useState<number>(0);
  const [initialActiveCars, setInitialActiveCars] = useState<number>(1);
  const [initialActiveExitRate, setInitialActiveExitRate] = useState<number>(1.0);
  const [maxSteps, setMaxSteps] = useState<number>(500);
  const [algorithm, setAlgorithm] = useState<string>("Priority planning");

  const defaults = useMemo(
    () => ({
      planning_horizon: 50,
      goal_reserve_horizon: 200,
      arrival_lambda: 1,
      max_arriving_cars: 1,
      initial_parked_cars: 0,
      initial_active_cars: 1,
      initial_active_exit_rate: 1.0,
      max_steps: 500,
      algorithm: "Priority planning",
    }),
    []
  );

  const saveAndContinue = () => {
    const cfg: SimConfig = {
      planning_horizon: Math.max(1, Math.floor(planningHorizon)),
      goal_reserve_horizon: Math.max(1, Math.floor(goalReserveHorizon)),
      arrival_lambda: Math.max(0, Number(arrivalLambda)),
      max_arriving_cars: Math.max(0, Math.floor(maxArrivingCars)),
      initial_parked_cars: Math.max(0, Math.floor(initialParkedCars)),
      initial_active_cars: Math.max(0, Math.floor(initialActiveCars)),
      initial_active_exit_rate: Math.max(0, Number(initialActiveExitRate)),
      max_steps: Math.max(1, Math.floor(maxSteps)),
    };

    sessionStorage.setItem(STORAGE_KEY, JSON.stringify(cfg));
    nav("/layout");
  };

  return (
    <AppLayout variant="cinematic" bgImage={bgHero}>
      <div className="setupHeader">
        <h1 className="setupTitle">Configuration</h1>
        <p className="setupSubtitle">Define simulation parameters before selecting a parking layout.</p>
      </div>

      <div className="setupPage">
        <div className="setupGrid">
          <section className="setupCard">
            <CardHead icon={<Car size={18} />} title="Vehicle Counts" sub="Initial state and limits." />

            <FieldRow
              icon={<Hash size={16} />}
              label="Static Parked Cars"
              value={initialParkedCars}
              min={0}
              max={500}
              step={1}
              onChange={setInitialParkedCars}
              onDefault={() => setInitialParkedCars(defaults.initial_parked_cars)}
            />

            <FieldRow
              icon={<Hash size={16} />}
              label="Exiting Cars"
              value={initialActiveCars}
              min={0}
              max={500}
              step={1}
              onChange={setInitialActiveCars}
              onDefault={() => setInitialActiveCars(defaults.initial_active_cars)}
            />

             <FieldRow
              icon={<LogOut size={16} />}
              label="Exit Rate (λ)"
              value={initialActiveExitRate}
              min={0}
              max={1}
              step={0.1}
              onChange={setInitialActiveExitRate}
              onDefault={() => setInitialActiveExitRate(defaults.initial_active_exit_rate)}
            />

            <FieldRow
              icon={<LogIn size={16} />}
              label="Entering Cars"
              value={maxArrivingCars}
              min={0}
              max={500}
              step={1}
              onChange={setMaxArrivingCars}
              onDefault={() => setMaxArrivingCars(defaults.max_arriving_cars)}
            />
            <FieldRow
              icon={<Activity size={16} />}
              label="Enter Rate (λ)"
              value={arrivalLambda}
              min={0}
              max={1}
              step={0.1}
              onChange={setArrivalLambda}
              onDefault={() => setArrivalLambda(defaults.arrival_lambda)}
              suffix="veh/min"
            />
          </section>

          <section className="setupCard">
            <CardHead icon={<Activity size={18} />} title="Simulation Parameters" sub="Timing & Pathfinding." />

            <SelectRow
              icon={<Cpu size={16} />}
              label="Algorithm"
              value={algorithm}
              options={["Priority planning"]}
              onChange={setAlgorithm}
            />



            <FieldRow
              icon={<Clock size={16} />}
              label="Max Steps (Duration)"
              value={maxSteps}
              min={1}
              max={3600}
              step={10}
              onChange={setMaxSteps}
              onDefault={() => setMaxSteps(defaults.max_steps)}
            />

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
          <button className="btnBackPrimary" onClick={() => nav("/")}>
            ← Back
          </button>

          <button className="btnPrimary" onClick={saveAndContinue}>
            Continue to Layout →
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