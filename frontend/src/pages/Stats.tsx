import { useEffect, useMemo, useState } from "react";
import AppLayout from "../layouts/AppLayout";
import "./Stats.css";
import bgHero from "../assets/HomePage.png";
import { Trash2, AlertTriangle, Download, CheckSquare, Square } from "lucide-react";

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
  const [selectedItems, setSelectedItems] = useState<Set<string>>(new Set());
  const [showBulkActions, setShowBulkActions] = useState(false);

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

  const handleExport = async (item: SimHistoryItem) => {
    try {
      // Create CSV content from simulation data
      const csvHeaders = [
        'Simulation ID',
        'Name',
        'Created At',
        'Status',
        'Grid Width',
        'Grid Height',
        'Initial Active Cars Configured',
        'Max Arriving Cars Configured',
        'Total Steps',
        'Total Cars',
        'Total Parked',
        'Total Failed Plans',
        'Initial Active Cars Exited',
        'Arriving Cars Spawned',
        'Arriving Cars Parked',
        'Average Steps to Park',
        'Average Steps to Exit'
      ];

      const csvData = [
        item.id,
        item.name || 'Untitled',
        item.created_at,
        item.status,
        item.grid_width || '',
        item.grid_height || '',
        item.initial_active_cars_configured,
        item.max_arriving_cars_configured,
        item.total_steps,
        item.total_cars,
        item.total_parked,
        item.total_failed_plans,
        item.initial_active_cars_exited,
        item.arriving_cars_spawned || '',
        item.arriving_cars_parked,
        item.average_steps_to_park || '',
        item.average_steps_to_exit || ''
      ];

      // Convert to CSV format
      const csvContent = [
        csvHeaders.join(','),
        csvData.map(field => `"${field}"`).join(',')
      ].join('\n');

      // Create and download the file
      const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
      const link = document.createElement('a');
      const url = URL.createObjectURL(blob);
      
      const fileName = `simulation_${item.name || 'unnamed'}_${item.id.slice(0, 8)}.csv`;
      
      link.setAttribute('href', url);
      link.setAttribute('download', fileName);
      link.style.visibility = 'hidden';
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
    } catch (err: any) {
      alert(`Failed to export simulation: ${err.message}`);
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

  const toggleSelection = (id: string) => {
    setSelectedItems(prev => {
      const newSet = new Set(prev);
      if (newSet.has(id)) {
        newSet.delete(id);
      } else {
        newSet.add(id);
      }
      setShowBulkActions(newSet.size > 0);
      return newSet;
    });
  };

  const toggleSelectAll = () => {
    if (selectedItems.size === filtered.length) {
      setSelectedItems(new Set());
      setShowBulkActions(false);
    } else {
      setSelectedItems(new Set(filtered.map(item => item.id)));
      setShowBulkActions(true);
    }
  };

  const handleBulkDelete = async () => {
    if (selectedItems.size === 0) return;
    
    const confirmDelete = window.confirm(
      `Are you sure you want to delete ${selectedItems.size} simulation${selectedItems.size > 1 ? 's' : ''}? This action cannot be undone.`
    );
    
    if (!confirmDelete) return;
    
    try {
      const deletePromises = Array.from(selectedItems).map(id => 
        fetch(`${API_URL}/simulation/${id}`, { method: "DELETE" })
      );
      
      await Promise.all(deletePromises);
      
      setItems(prev => prev.filter(item => !selectedItems.has(item.id)));
      setSelectedItems(new Set());
      setShowBulkActions(false);
    } catch (err: any) {
      alert(`Failed to delete simulations: ${err.message}`);
    }
  };

  const handleBulkExport = () => {
    if (selectedItems.size === 0) return;
    
    const selectedData = items.filter(item => selectedItems.has(item.id));
    
    // Create CSV content for multiple simulations
    const csvHeaders = [
      'Simulation ID',
      'Name',
      'Created At',
      'Status',
      'Grid Width',
      'Grid Height',
      'Initial Active Cars Configured',
      'Max Arriving Cars Configured',
      'Total Steps',
      'Total Cars',
      'Total Parked',
      'Total Failed Plans',
      'Initial Active Cars Exited',
      'Arriving Cars Spawned',
      'Arriving Cars Parked',
      'Average Steps to Park',
      'Average Steps to Exit'
    ];

    const csvRows = selectedData.map(item => {
      const csvData = [
        item.id,
        item.name || 'Untitled',
        item.created_at,
        item.status,
        item.grid_width || '',
        item.grid_height || '',
        item.initial_active_cars_configured,
        item.max_arriving_cars_configured,
        item.total_steps,
        item.total_cars,
        item.total_parked,
        item.total_failed_plans,
        item.initial_active_cars_exited,
        item.arriving_cars_spawned || '',
        item.arriving_cars_parked,
        item.average_steps_to_park || '',
        item.average_steps_to_exit || ''
      ];
      return csvData.map(field => `"${field}"`).join(',');
    });

    const csvContent = [csvHeaders.join(','), ...csvRows].join('\n');

    // Create and download the file
    const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
    const link = document.createElement('a');
    const url = URL.createObjectURL(blob);
    
    const fileName = `simulations_bulk_export_${new Date().toISOString().slice(0, 10)}.csv`;
    
    link.setAttribute('href', url);
    link.setAttribute('download', fileName);
    link.style.visibility = 'hidden';
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  };

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
                  <th>
                    <button 
                      className="selectAllBtn" 
                      onClick={toggleSelectAll}
                      title={selectedItems.size === filtered.length ? "Deselect All" : "Select All"}
                    >
                      {selectedItems.size === filtered.length && filtered.length > 0 ? 
                        <CheckSquare size={16} /> : 
                        <Square size={16} />
                      }
                    </button>
                  </th>
                  <th>Date</th>
                  <th>Name</th>
                  <th>Status</th>
                  <th>Layout</th>
                  <th>Initial Batch</th>
                  <th>Arrivals</th>
                  <th>Efficiency (Avg Steps)</th>
                  <th>Total Steps</th>
                  <th>Export</th>
                  <th>Actions</th>
                </tr>
              </thead>
              <tbody>
                {filtered.map((item) => (
                  <tr key={item.id} className={selectedItems.has(item.id) ? "selected" : ""}>
                    <td>
                      <button 
                        className="checkboxBtn" 
                        onClick={() => toggleSelection(item.id)}
                        title="Select Simulation"
                      >
                        {selectedItems.has(item.id) ? 
                          <CheckSquare size={16} /> : 
                          <Square size={16} />
                        }
                      </button>
                    </td>
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
                        className="exportBtn" 
                        onClick={() => handleExport(item)}
                        title="Export to CSV"
                      >
                        <Download size={16} />
                      </button>
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

        {showBulkActions && (
          <div className="bulkActionsBar glass">
            <div className="bulkActionsInfo">
              <span className="selectedCount">{selectedItems.size} simulation{selectedItems.size > 1 ? 's' : ''} selected</span>
            </div>
            <div className="bulkActionsButtons">
              <button className="bulkExportBtn" onClick={handleBulkExport}>
                <Download size={16} />
                Export Selected
              </button>
              <button className="bulkDeleteBtn" onClick={handleBulkDelete}>
                <Trash2 size={16} />
                Delete Selected
              </button>
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