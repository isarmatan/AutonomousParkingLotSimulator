import { useMemo } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import AppLayout from "../layouts/AppLayout";
import "../pages/SimulationConfig.css";
import bgHero from "../assets/HomePage.png";
import { Database, PlusCircle, CheckCircle2, LayoutGrid } from "lucide-react";

export default function Layout() {
  const nav = useNavigate();
  const [params] = useSearchParams();
  const chosenLayoutId = params.get("layout");


  const layoutLabel = useMemo(() => {
    if (!chosenLayoutId) return null;
    if (chosenLayoutId === "new") return "Generated new parking lot";
    return `Saved layout: ${chosenLayoutId}`;
  }, [chosenLayoutId]);

  const onStart = () => {
    if (!chosenLayoutId) return;
    nav(`/config?layout=${encodeURIComponent(chosenLayoutId)}`);
  };

  return (
    <AppLayout variant="cinematic" bgImage={bgHero}>
      <div className="setupHeader">
        <h1 className="setupTitle">Layout</h1>
        <p className="setupSubtitle">
          Choose an existing parking lot or create a new one.
        </p>
      </div>

      <div className="setupPage">
        <>
          <div className="setupGrid">
              <section className="setupCard">
                <div className="cardHead">
                  <h2 className="cardTitle">
                    <span className="cardIcon" aria-hidden="true"><Database size={18} /></span>
                    Load a saved parking lot
                  </h2>
                  <p className="cardSub">Browse saved parking lots and select one.</p>
                </div>

                <div className="setupActions" style={{ gridTemplateColumns: "1fr" }}>
                  <button className="btnPrimary" onClick={() => nav("/layouts")}>
                    Open Saved Layouts →
                  </button>
                </div>
              </section>

              <section className="setupCard">
                <div className="cardHead">
                  <h2 className="cardTitle">
                    <span className="cardIcon" aria-hidden="true"><PlusCircle size={18} /></span>
                    Generate new parking lot
                  </h2>
                  <p className="cardSub">Define dimensions and entries/exits.</p>
                </div>

                <div className="setupActions" style={{ gridTemplateColumns: "1fr" }}>
                  <button className="btnPrimary" onClick={() => nav("/layout/new")}>
                    Generate New →
                  </button>
                </div>
              </section>

              <section className="setupCard">
                <div className="cardHead">
                  <h2 className="cardTitle">
                    <span className="cardIcon" aria-hidden="true"><LayoutGrid size={18} /></span>
                    Design in Editor
                  </h2>
                  <p className="cardSub">Draw a custom parking lot layout from scratch.</p>
                </div>

                <div className="setupActions" style={{ gridTemplateColumns: "1fr" }}>
                  <button className="btnPrimary" onClick={() => nav("/editor")}>
                    Open Editor →
                  </button>
                </div>
              </section>
            </div>

            {layoutLabel ? (
              <div className="setupCard highlight">
                <div className="cardHead">
                  <h2 className="cardTitle">
                    <span className="cardIcon" aria-hidden="true"><CheckCircle2 size={18} /></span>
                    Selected Parking Lot
                  </h2>
                  <p className="cardSub">{layoutLabel}</p>
                </div>

                <div className="setupActions">
                  <button className="btnStart" onClick={onStart}>
                    Continue to Config →
                  </button>
                </div>
              </div>
            ) : null}
          </>

        <div className="setupActions setupActions--single">
          <button className="btnBackPrimary" onClick={() => nav("/mode-select")}>
            ← Back
          </button>
        </div>

      </div>
    </AppLayout>
  );
}