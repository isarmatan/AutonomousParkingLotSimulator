import { useNavigate } from "react-router-dom";
import AppLayout from "../layouts/AppLayout";
import "./SimulationModeSelect.css";
import bgHero from "../assets/HomePage.webp";
import { Play, Layers } from "lucide-react";

export default function SimulationModeSelect() {
  const nav = useNavigate();

  return (
    <AppLayout variant="cinematic" bgImage={bgHero}>
      <div className="modeHeader">
        <h1 className="modeTitle">Select Simulation Mode</h1>
        <p className="modeSub">Choose how you want to run your simulation.</p>
      </div>

      <div className="modeGrid">
        <button className="modeCard" onClick={() => nav("/layout")}>
          <div className="modeCardIcon modeCardIcon--blue">
            <Play size={28} />
          </div>
          <div className="modeCardBody">
            <h2 className="modeCardTitle">Normal Simulation</h2>
            <p className="modeCardDesc">
              Run a single simulation with full live visualization, headless mode,
              or side-by-side algorithm comparison.
            </p>
            <ul className="modeCardFeatures">
              <li>Live 2D / 3D rendering</li>
              <li>Headless fast-run mode</li>
              <li>Algorithm comparison</li>
            </ul>
          </div>
          <span className="modeCardArrow">→</span>
        </button>

        <button className="modeCard" onClick={() => nav("/batch-config")}>
          <div className="modeCardIcon modeCardIcon--green">
            <Layers size={28} />
          </div>
          <div className="modeCardBody">
            <h2 className="modeCardTitle">Batch Simulation</h2>
            <p className="modeCardDesc">
              Configure up to 20 independent simulations with different parameters
              and run them all headlessly. Compare results across configurations.
            </p>
            <ul className="modeCardFeatures">
              <li>Up to 20 simulations per batch</li>
              <li>Always headless (fast)</li>
              <li>Per-simulation result cards</li>
            </ul>
          </div>
          <span className="modeCardArrow">→</span>
        </button>
      </div>

      <div className="modeBack">
        <button className="btnBackPrimary" onClick={() => nav("/")}>
          ← Back
        </button>
      </div>
    </AppLayout>
  );
}
