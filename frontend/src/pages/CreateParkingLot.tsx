import { useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import AppLayout from "../layouts/AppLayout";
import "./SimulationConfig.css";
import { Ruler } from "lucide-react";
import bgHero from "../assets/HomePage.png";

const LAYOUT_KEY = "parking_layout_v1";

type NewLayout = {
  length: number;
  width: number;
  entries: number;
  exits: number;
  totalSpots: number;
};

export default function CreateParkingLot() {
  const nav = useNavigate();

  const [length, setLength] = useState(15);
  const [width, setWidth] = useState(20);
  const [entries, setEntries] = useState(1);
  const [exits, setExits] = useState(1);
  const [totalSpots, setTotalSpots] = useState(96);

  const defaults = useMemo(() => ({ length: 15, width: 20, entries: 1, exits: 1, totalSpots: 96 }), []);

  const onSave = () => {
    const layout: NewLayout = {
      length: Math.max(1, Math.floor(length)),
      width: Math.max(1, Math.floor(width)),
      entries: Math.max(0, Math.floor(entries)),
      exits: Math.max(0, Math.floor(exits)),
      totalSpots: Math.max(0, Math.floor(totalSpots)),
    };

    sessionStorage.setItem(LAYOUT_KEY, JSON.stringify(layout));
    nav("/layout?layout=new");
  };

  return (
    <AppLayout variant="cinematic" bgImage={bgHero}>
      <div className="setupHeader">
        <h1 className="setupTitle">Create New Parking Lot</h1>
        <p className="setupSubtitle">Enter the new layout parameters.</p>
      </div>

      <div className="setupPage">
        <section className="setupCard">
          <div className="cardHead">
            <h2 className="cardTitle">
              <span className="cardIcon" aria-hidden="true"><Ruler size={18} /></span>
              Parking Lot Parameters
            </h2>
            <p className="cardSub">These are placeholders until the real editor/backend is connected.</p>
          </div>

          <FieldRow label="Length" value={length} min={1} max={500} step={1} onChange={setLength} onDefault={() => setLength(defaults.length)} />
          <FieldRow label="Width" value={width} min={1} max={500} step={1} onChange={setWidth} onDefault={() => setWidth(defaults.width)} />

          <FieldRow label="Number of Entries" value={entries} min={0} max={20} step={1} onChange={setEntries} onDefault={() => setEntries(defaults.entries)} />
          <FieldRow label="Number of Exits" value={exits} min={0} max={20} step={1} onChange={setExits} onDefault={() => setExits(defaults.exits)} />

          <FieldRow label="Total Parking Spots" value={totalSpots} min={0} max={100000} step={1} onChange={setTotalSpots} onDefault={() => setTotalSpots(defaults.totalSpots)} />
        </section>

        <div className="setupActions">
          <button className="btnBackPrimary" onClick={() => nav(-1)}>
            ← Back
          </button>
          <button className="btnPrimary" onClick={onSave}>
            Save Layout →
          </button>
        </div>
      </div>
    </AppLayout>
  );
}

/* reuse the same FieldRow component logic */
function FieldRow(props: {
  label: string;
  value: number;
  min: number;
  max: number;
  step: number;
  onChange: (v: number) => void;
  onDefault: () => void;
}) {
  const { label, value, min, max, step, onChange, onDefault } = props;

  return (
    <div className="fieldRow">
      <div className="fieldTop">
        <span className="fieldLabel">{label}</span>
        <button type="button" className="miniPill" onClick={onDefault}>
          default
        </button>
      </div>

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

        <span className="fieldUnit"></span>
      </div>
    </div>
  );
}
