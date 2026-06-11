import { useMemo, useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import AppLayout from "../layouts/AppLayout";
import "./SavedLayouts.css";
import "../pages/SimulationConfig.css";
import bgHero from "../assets/HomePage.png";


const API_URL = "http://127.0.0.1:8000";

type LayoutItem = {
  id: string;
  name: string;
  updatedAt: string; // We'll mock this for now or use a default
  spots: number;
  size: string;
  note?: string;
};

export default function SavedLayouts() {
  const navigate = useNavigate();
  const [q, setQ] = useState("");
  const [layouts, setLayouts] = useState<LayoutItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const fetchLayouts = async () => {
      try {
        const res = await fetch(`${API_URL}/editor/saved`);
        if (!res.ok) {
          throw new Error(`Failed to fetch layouts: ${res.statusText}`);
        }
        const data = await res.json();
        
        // Transform backend data to frontend format
        const items: LayoutItem[] = (data.items || []).map((item: Record<string, unknown>) => ({
          id: item.id,
          name: item.name || "Untitled Layout",
          updatedAt: "Unknown", // Backend doesn't provide this yet
          spots: item.capacity || 0,
          size: `${item.width}x${item.height}`,
          note: `Entries: ${item.num_entries}, Exits: ${item.num_exits}`
        }));
        
        setLayouts(items);
      } catch (err: unknown) {
        const message = err instanceof Error ? err.message : "Unknown error";
        setError(message);
      } finally {
        setLoading(false);
      }
    };

    fetchLayouts();
  }, []);

  const filtered = useMemo(() => {
    const s = q.trim().toLowerCase();
    if (!s) return layouts;
    return layouts.filter((l) => l.name.toLowerCase().includes(s));
  }, [q, layouts]);

  const onOpen = (id: string, name: string) => {
    sessionStorage.setItem("sim_lot_name", name);
    navigate(`/layout?layout=${encodeURIComponent(id)}`);
  };

  const onDelete = async (e: React.MouseEvent, id: string) => {
    e.stopPropagation(); // Prevent card click
    if (!window.confirm("Are you sure you want to delete this layout? This action cannot be undone.")) {
      return;
    }

    try {
      const res = await fetch(`${API_URL}/editor/saved/${id}`, {
        method: "DELETE",
      });

      if (!res.ok) {
        throw new Error(`Failed to delete layout: ${res.statusText}`);
      }

      // Remove from local state
      setLayouts((prev) => prev.filter((l) => l.id !== id));
    } catch (err: unknown) {
      alert(err instanceof Error ? err.message : "Unknown error deleting layout");
    }
  };

  return (
    <AppLayout variant="cinematic" bgImage={bgHero}>
      {/* Header */}
      <div className="setupHeader">
        <h1 className="setupTitle">Saved Layouts</h1>
        <p className="setupSubtitle">Browse ready-made parking lots and load one to continue.</p>
      </div>

      <div className="setupPage">
        <div className="layoutsPage" dir="ltr">
          <div className="layoutsTop">
            <div className="layoutsBar">
              <input
                className="layoutsSearch"
                value={q}
                onChange={(e) => setQ(e.target.value)}
                placeholder="Search layouts..."
                aria-label="Search layouts"
              />
              <div className="layoutsCount">{filtered.length} layouts</div>
            </div>
          </div>

          {loading && <div className="loadingState">Loading layouts...</div>}
          
          {error && <div className="errorState">Error: {error}</div>}

          {!loading && !error && (
            <div className="layoutsGrid">
              {filtered.map((l) => (
                <button key={l.id} className="layoutCard" onClick={() => onOpen(l.id, l.name)}>
                  <div className="layoutCardHead">
                    <div className="layoutName">{l.name}</div>
                    <div className="layoutActions">
                      <div className="layoutMeta">{l.updatedAt}</div>
                      <button 
                        className="layoutDeleteBtn" 
                        onClick={(e) => onDelete(e, l.id)}
                        title="Delete Layout"
                      >
                        Delete
                      </button>
                    </div>
                  </div>

                  <div className="layoutStats">
                    <div className="layoutPill">Spots: <b>{l.spots}</b></div>
                    <div className="layoutPill">Size: <b>{l.size}</b></div>
                  </div>

                  <div className={`layoutNote ${l.note ? "" : "layoutNoteMuted"}`}>
                    {l.note ?? "No notes"}
                  </div>

                  <div className="layoutHint">Click to load →</div>
                </button>
              ))}
            </div>
          )}
        </div>

        {/* Back button */}
        <div className="setupActions setupActions--single">
          <button className="btnBackPrimary" onClick={() => navigate("/layout")}>
            ← Back
          </button>
        </div>
      </div>
    </AppLayout>
  );
}
