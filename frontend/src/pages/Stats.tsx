import { useEffect, useMemo, useState } from "react";
import AppLayout from "../layouts/AppLayout";
import "./Stats.css";
import bgHero from "../assets/HomePage.png";
import { Trash2, AlertTriangle } from "lucide-react";

const API_URL = "http://127.0.0.1:8000";

type SimHistoryItem = {
  id: string;
  name?: string;
  created_at: string;
  parking_lot_id?: string;
  grid_width?: number;
  grid_height?: number;

  initial_active_cars_configured: number;
  max_arriving_cars_configured: number;

  total_steps: number;
  total_cars: number;
  total_parked: number;
  total_failed_plans: number;
  status: string;

  initial_active_cars_exited: number;
  arriving_cars_parked: number;
  arriving_cars_spawned?: number;

  average_steps_to_park?: number;
  average_steps_to_exit?: number;
};

export default function Stats() {
  const [items, setItems] = useState<SimHistoryItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [query, setQuery] = useState("");
  const [deleteId, setDeleteId] = useState<string | null>(null);

  useEffect(() => {
    const fetchHistory = async () => {
      try {
        const res = await fetch(`${API_URL}/simulation/history`);
        if (!res.ok) throw new Error("Failed to fetch history");
        const data = await res.json();
        setItems(data);
      } catch (err: unknown) {
        const message = err instanceof Error ? err.message : "Unknown error";
        setError(message);
      } finally {
        setLoading(false);
      }
    };
    fetchHistory();
  }, []);

  const handleDelete = async () => {
    if (!deleteId) return;
    try {
      const res = await fetch(`${API_URL}/simulation/${deleteId}`, { method: "DELETE" });
      if (!res.ok) throw new Error("Failed to delete simulation");
      setItems((prev) => prev.filter((item) => item.id !== deleteId));
      setDeleteId(null);
    } catch (err: any) {
      alert(err.message);
    }
  };

  const formatDate = (isoString: string) => new Date(isoString).toLocaleString();

  const getStatusClass = (status: string) => {
    if (status === "COMPLETED") return "completed";
    if (status === "MAX_STEPS_REACHED") return "partial";
    return "failed";
  };

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return items;
    return items.filter((x) => (x.name || "Untitled").toLowerCase().includes(q));
  }, [items, query]);

  const kpis = useMemo(() => {
    const totalRuns = items.length;
    const completed = items.filter((x) => x.status === "COMPLETED").length;
    const successRate = totalRuns ? Math.round((completed / totalRuns) * 100) : 0;

    const avgExit = avg(
      items.map((x) => x.average_steps_to_exit).filter((v): v is number => typeof v === "number")
    );
    const avgPark = avg(
      items.map((x) => x.average_steps_to_park).filter((v): v is number => typeof v === "number")
    );

    const totalFailures = items.reduce((sum, x) => sum + (x.total_failed_plans || 0), 0);

    return { totalRuns, successRate, avgExit, avgPark, totalFailures };
  }, [items]);

  return (
    <AppLayout variant="cinematic" bgImage={bgHero}>
      <div className="statsPage statsBright">
        <header className="statsHeader">
          <div>
            <h1 className="statsTitle">Simulation History</h1>
            <p className="statsSubtitle">Review performance metrics from previous simulation runs.</p>
          </div>

          <div className="statsControls">
            <div className="searchWrap">
              <input
                className="searchInput"
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                placeholder="Search by simulation name..."
              />
              <span className="searchGlow" />
            </div>
          </div>
        </header>

        {loading && <div className="loadingState">Loading history...</div>}
        {error && <div className="errorState">Error: {error}</div>}

        {!loading && !error && items.length === 0 && (
          <div className="emptyState">No simulation history found. Run a simulation to see results here.</div>
        )}

        {!loading && !error && items.length > 0 && (
          <section className="kpiGrid">
            <div className="kpiCard">
              <div className="kpiLabel">Total Runs</div>
              <div className="kpiValue">{kpis.totalRuns}</div>
              <div className="kpiSub">All recorded simulations</div>
            </div>

            <div className="kpiCard accentTurq">
              <div className="kpiLabel">Success Rate</div>
              <div className="kpiValue">{kpis.successRate}%</div>
              <div className="kpiSub">Completed / Total</div>
            </div>

            <div className="kpiCard accentPurple">
              <div className="kpiLabel">Avg Exit Steps</div>
              <div className="kpiValue">{Number.isFinite(kpis.avgExit) ? kpis.avgExit.toFixed(1) : "—"}</div>
              <div className="kpiSub">Mean per run</div>
            </div>

            <div className="kpiCard accentPink">
              <div className="kpiLabel">Avg Park Steps</div>
              <div className="kpiValue">{Number.isFinite(kpis.avgPark) ? kpis.avgPark.toFixed(1) : "—"}</div>
              <div className="kpiSub">Mean per run</div>
            </div>

            <div className="kpiCard accentAmber">
              <div className="kpiLabel">Failures</div>
              <div className="kpiValue">{kpis.totalFailures}</div>
              <div className="kpiSub">Total failed plans</div>
            </div>
          </section>
        )}

        {!loading && !error && items.length > 0 && filtered.length === 0 && (
          <div className="emptyState">No results match your search. Try clearing the search input.</div>
        )}

        {!loading && !error && filtered.length > 0 && (
          <div className="statsTableContainer glass">
            <table className="statsTable">
              <thead>
                <tr>
                  <th>Date</th>
                  <th>Name</th>
                  <th>Status</th>
                  <th>Layout</th>
                  <th>Initial Batch</th>
                  <th>Arrivals</th>
                  <th>Efficiency (Avg Steps)</th>
                  <th>Total Steps</th>
                  <th>Actions</th>
                </tr>
              </thead>
              <tbody>
                {filtered.map((item) => (
                  <tr key={item.id}>
                    <td className="mono">{formatDate(item.created_at)}</td>

                    <td>
                      <div className="nameCell">
                        <b className="nameMain">{item.name || "Untitled"}</b>
                        <span className="nameSub">
                          {item.grid_width && item.grid_height ? `${item.grid_width}×${item.grid_height}` : "Unknown layout"}
                        </span>
                      </div>
                    </td>

                    <td>
                      <span className={`statusBadge ${getStatusClass(item.status)}`}>
                        <span className="dot" />
                        {item.status.replace(/_/g, " ")}
                      </span>
                    </td>

                    <td>
                      {item.grid_width && item.grid_height ? `${item.grid_width}x${item.grid_height}` : "Unknown"}
                    </td>

                    <td>
                      <div className="statMetric">
                        <span className="statMetricVal">
                          {item.initial_active_cars_exited} / {item.initial_active_cars_configured}
                        </span>
                        <span className="statMetricSub">Exited / Requested</span>
                      </div>
                    </td>

                    <td>
                      <div className="statMetric">
                        <span className="statMetricVal">
                          {item.arriving_cars_parked} / {item.max_arriving_cars_configured}
                        </span>
                        <span className="statMetricSub">Parked / Max Allowed</span>
                      </div>
                    </td>

                    <td>
                      <div className="statMetric">
                        <span className="statMetricVal">
                          {typeof item.average_steps_to_exit === "number"
                            ? `Exit: ${item.average_steps_to_exit.toFixed(1)}`
                            : "Exit: —"}
                        </span>
                        <span className="statMetricVal">
                          {typeof item.average_steps_to_park === "number"
                            ? `Park: ${item.average_steps_to_park.toFixed(1)}`
                            : "Park: —"}
                        </span>
                      </div>
                    </td>

                    <td>
                      <div className="statMetric">
                        <span className="statMetricVal">{item.total_steps}</span>
                        <span className="statMetricSub">{item.total_failed_plans} failures</span>
                      </div>
                    </td>

                    <td>
                      <button 
                        className="deleteBtn" 
                        onClick={() => setDeleteId(item.id)}
                        title="Delete Simulation"
                      >
                        <Trash2 size={16} />
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {deleteId && (
          <div className="modalOverlay">
            <div className="modalContent">
              <div className="modalHeader">
                <AlertTriangle className="errorIcon" size={24} />
                <h3>Delete Simulation?</h3>
              </div>
              <p>Are you sure you want to delete this simulation record? This action cannot be undone.</p>
              <div className="modalActions">
                <button className="btnGhost" onClick={() => setDeleteId(null)}>Cancel</button>
                <button className="btnDeleteConfirm" onClick={handleDelete}>Delete</button>
              </div>
            </div>
          </div>
        )}
      </div>
    </AppLayout>
  );
}

function avg(nums: number[]) {
  if (!nums.length) return NaN;
  return nums.reduce((a, b) => a + b, 0) / nums.length;
}