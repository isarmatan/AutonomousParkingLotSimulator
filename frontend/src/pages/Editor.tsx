import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import AppLayout from "../layouts/AppLayout";
import {
  Save,
  AlertTriangle,
  CheckCircle,
  Layers,
  Square,
  ParkingSquare,
  LogIn,
  LogOut,
  LayoutGrid,
  Loader2,
  Box,
} from "lucide-react";
import "./Editor.css";
import Scene3D from "../components/Scene3D";

const API_URL = "http://127.0.0.1:8000";

// --- Types ---
type CellType = "WALL" | "ROAD" | "PARKING" | "ENTRY" | "EXIT";

type CellDTO = {
  x: number;
  y: number;
  type: CellType;
  metadata: Record<string, unknown>;
};

type GridDTO = {
  width: number;
  height: number;
  cells: CellDTO[];
};

type ErrorDTO = {
  code: string;
  message: string;
  x?: number;
  y?: number;
};

type Tool = {
  id: string;
  label: string;
  icon: React.ReactNode;
  actionType: "PAINT" | "PLACE_ENTRY" | "PLACE_EXIT" | "PLACE_PARKING" | "CLEAR";
  cellType?: CellType;
};

const TOOLS: Tool[] = [
  { id: "wall", label: "Wall", icon: <Layers />, actionType: "PAINT", cellType: "WALL" },
  { id: "road", label: "Road", icon: <Square />, actionType: "PAINT", cellType: "ROAD" },
  { id: "parking", label: "Parking", icon: <ParkingSquare />, actionType: "PLACE_PARKING" },
  { id: "entry", label: "Entry", icon: <LogIn />, actionType: "PLACE_ENTRY" },
  { id: "exit", label: "Exit", icon: <LogOut />, actionType: "PLACE_EXIT" },
];

export default function Editor() {
  const nav = useNavigate();

  // State
  const [draftId, setDraftId] = useState<string | null>(null);
  const [grid, setGrid] = useState<GridDTO | null>(null);
  const [selectedTool, setSelectedTool] = useState<Tool>(TOOLS[1]); // Default to Road
  const [loading, setLoading] = useState(false);
  const [viewMode, setViewMode] = useState<"2D" | "3D">("3D");
  const [saving, setSaving] = useState(false);
  const [validationErrors, setValidationErrors] = useState<ErrorDTO[]>([]);
  const [validationRan, setValidationRan] = useState(false);
  const [saveDialogOpen, setSaveDialogOpen] = useState(false);
  const [saveName, setSaveName] = useState("");
  const [saveError, setSaveError] = useState<string | null>(null);
  const [isDragging, setIsDragging] = useState(false);

  // Initialization State
  const [initWidth, setInitWidth] = useState(20);
  const [initHeight, setInitHeight] = useState(15);

  const CELL_PX = 32;
  const isLargeGrid = !!(grid && (grid.width > 40 || grid.height > 40));

  // Stop dragging when mouse leaves window or goes up anywhere
  useEffect(() => {
    const handleGlobalUp = () => setIsDragging(false);
    window.addEventListener("mouseup", handleGlobalUp);
    return () => window.removeEventListener("mouseup", handleGlobalUp);
  }, []);

  const onMouseDown = (x: number, y: number) => {
    setIsDragging(true);
    handleCellClick(x, y);
  };

  const onMouseEnter = (x: number, y: number) => {
    if (isDragging) {
      handleCellClick(x, y);
    }
  };

  // Create Draft
  const handleCreateDraft = async () => {
    try {
      setLoading(true);
      const res = await fetch(`${API_URL}/editor/drafts`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ source: "blank", width: initWidth, height: initHeight }),
      });

      if (!res.ok) throw new Error("Failed to create draft");

      const data = await res.json();
      setDraftId(data.draftId);
      setGrid(data.grid);
      if (initWidth > 40 || initHeight > 40) setViewMode("2D");
    } catch (e) {
      console.error(e);
      alert("Failed to initialize editor session.");
    } finally {
      setLoading(false);
    }
  };

  // Handle Cell Click
  const handleCellClick = async (x: number, y: number) => {
    if (!draftId || !selectedTool) return;

    const payload = {
      action: {
        type: selectedTool.actionType,
        x,
        y,
        cellType: selectedTool.cellType,
      },
    };

    try {
      const res = await fetch(`${API_URL}/editor/drafts/${draftId}/actions:apply`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });

      const data = await res.json();

      if (data.ok) {
        setGrid(data.grid);
        setValidationErrors((prev) => prev.filter((e) => e.x !== x || e.y !== y));
        setValidationRan(false);
      } else {
        console.warn("Action failed:", data.error);
        setValidationErrors((prev) => [...prev, data.error]);
        setTimeout(() => {
          setValidationErrors((prev) => prev.filter((e) => e !== data.error));
        }, 3000);
      }
    } catch (e) {
      console.error("Network error applying action", e);
    }
  };

  // Validate Draft
  const handleValidate = async () => {
    if (!draftId) return;
    try {
      const res = await fetch(`${API_URL}/editor/drafts/${draftId}:validate`, {
        method: "POST",
      });
      const data = await res.json();
      setValidationErrors(data.errors || []);
      setValidationRan(true);
    } catch (e) {
      console.error(e);
    }
  };

  // Save Draft
  const handleSave = async () => {
    if (!draftId || !saveName.trim()) return;

    try {
      setSaving(true);
      setSaveError(null);

      const res = await fetch(`${API_URL}/editor/drafts/${draftId}:save`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name: saveName }),
      });

      const data = await res.json();

      if (data.ok) {
        setSaveDialogOpen(false);
        nav("/layouts");
      } else {
        setValidationErrors(data.errors || []);
        if (data.errors.some((e: ErrorDTO) => e.code === "NAME_TAKEN")) {
          setSaveError("Name already taken.");
        } else {
          setSaveDialogOpen(false);
        }
      }
    } catch {
      setSaveError("Network error.");
    } finally {
      setSaving(false);
    }
  };

  // Build rows
  const rows = useMemo(() => {
    if (!grid) return null;
    const r = Array.from({ length: grid.height }, () => Array(grid.width).fill(null as CellDTO | null));
    grid.cells.forEach((cell) => {
      if (cell.x < grid.width && cell.y < grid.height) r[cell.y][cell.x] = cell;
    });
    return r;
  }, [grid]);

  // Render Grid
  const renderGrid = () => {
    if (!grid || !rows) return null;

    return (
      <div className={`editorCanvasScroll${isLargeGrid ? " editorCanvasScroll--large" : ""}`}>
        <div
          className={`editorGrid${isLargeGrid ? " editorGrid--large" : ""}`}
          style={{
            gridTemplateColumns: `repeat(${grid.width}, ${CELL_PX}px)`,
            gridTemplateRows: `repeat(${grid.height}, ${CELL_PX}px)`,
          }}
        >
          {rows.map((row, y) =>
            row.map((cell: CellDTO | null, x: number) => {
              if (!cell) return null;
              const hasError = validationErrors.some((e) => e.x === x && e.y === y);

              return (
                <div
                  key={`${x}-${y}`}
                  className={`editorCell cell-${cell.type} ${hasError ? "cell-error" : ""}`}
                  data-mark={cell.type === "ENTRY" ? "IN" : cell.type === "EXIT" ? "OUT" : undefined}
                  onMouseDown={() => onMouseDown(x, y)}
                  onMouseEnter={() => onMouseEnter(x, y)}
                  title={`(${x},${y}) ${cell.type}`}
                  style={hasError ? { outline: "2px solid red", zIndex: 10 } : {}}
                />
              );
            })
          )}
        </div>
      </div>
    );
  };

  return (
    <AppLayout variant="editor">
      {!draftId ? (
        // --- Initialization Screen ---
        <div className="editorPage" style={{ justifyContent: "center", alignItems: "center" }}>
          <div className="editorCard" style={{ width: 400, padding: 32 }}>
            <h2 className="editorCardTitle" style={{ marginBottom: 8 }}>
              Create New Parking Lot
            </h2>
            <p className="editorCardSub" style={{ marginBottom: 24 }}>
              Set the dimensions for your new grid.
            </p>

            <div style={{ marginBottom: 16 }}>
              <label className="editorFieldLabel" style={{ display: "block", marginBottom: 8 }}>
                Width (Cells)
              </label>
              <input
                type="number"
                className="editorNumInput"
                style={{ width: "100%" }}
                value={initWidth}
                onChange={(e) => setInitWidth(Number(e.target.value))}
                min={5}
                max={50}
              />
            </div>

            <div style={{ marginBottom: 24 }}>
              <label className="editorFieldLabel" style={{ display: "block", marginBottom: 8 }}>
                Height (Cells)
              </label>
              <input
                type="number"
                className="editorNumInput"
                style={{ width: "100%" }}
                value={initHeight}
                onChange={(e) => setInitHeight(Number(e.target.value))}
                min={5}
                max={50}
              />
            </div>

            <button
              className="editorBtnPrimary"
              style={{ width: "100%", justifyContent: "center" }}
              onClick={handleCreateDraft}
              disabled={loading}
            >
              {loading ? <Loader2 className="spinner" size={16} /> : "Create Draft"}
            </button>
          </div>
        </div>
      ) : (
        // --- Main Editor UI ---
        <div className="editorPage">
          {/* Header */}

          <div className="editorWorkspace">
            {/* Sidebar */}
            <div className="editorSidebar">
              {/* View Mode Toggle */}
              <div className="editorSidebarSection">
                <span className="editorSidebarTitle">View</span>
                <div className="viewToggle" style={{ display: "flex", gap: 8 }}>
                  <button
                    className={`editorToolBtn ${viewMode === "2D" ? "active" : ""}`}
                    onClick={() => setViewMode("2D")}
                    title="2D View"
                    style={{ flex: 1, height: 40, flexDirection: "row" }}
                  >
                    <div className="editorToolIcon" style={{ marginBottom: 0, marginRight: 6 }}>
                      <LayoutGrid size={18} />
                    </div>
                    <span className="editorToolLabel">2D</span>
                  </button>
                  <button
                    className={`editorToolBtn ${viewMode === "3D" ? "active" : ""}`}
                    onClick={() => !isLargeGrid && setViewMode("3D")}
                    title={isLargeGrid ? "3D disabled for grids larger than 40×40" : "3D View"}
                    disabled={isLargeGrid}
                    style={{ flex: 1, height: 40, flexDirection: "row", opacity: isLargeGrid ? 0.4 : 1 }}
                  >
                    <div className="editorToolIcon" style={{ marginBottom: 0, marginRight: 6 }}>
                      <Box size={18} />
                    </div>
                    <span className="editorToolLabel">3D</span>
                  </button>
                </div>
              </div>

              {/* Tools */}
              <div className="editorSidebarSection">
                <span className="editorSidebarTitle">Tools</span>
                <div className="editorToolsGrid">
                  {TOOLS.map((tool) => (
                    <button
                      key={tool.id}
                      className={`editorToolBtn ${selectedTool.id === tool.id ? "active" : ""}`}
                      onClick={() => setSelectedTool(tool)}
                      title={tool.label}
                    >
                      <div className="editorToolIcon">{tool.icon}</div>
                      <span className="editorToolLabel">{tool.label}</span>
                    </button>
                  ))}
                </div>
              </div>

              {/* Actions */}
              <div className="editorSidebarSection">
                <span className="editorSidebarTitle">Actions</span>
                <button
                  className="editorBtnPrimary"
                  onClick={() => {
                    handleValidate();
                    setSaveDialogOpen(true);
                  }}
                  style={{ marginBottom: 8, justifyContent: "center" }}
                >
                  <Save size={16} style={{ marginRight: 8 }} />
                  Save Layout
                </button>
                <button className="editorBtnGhost" onClick={handleValidate} style={{ justifyContent: "center" }}>
                  <CheckCircle size={16} style={{ marginRight: 8 }} />
                  Validate
                </button>
              </div>

              {/* Validation Result */}
              {validationRan && validationErrors.length === 0 && (
                <div className="editorValidationSuccess">
                  <CheckCircle size={15} style={{ flexShrink: 0, color: "#4ade80" }} />
                  <span>Looking good — the grid is valid.</span>
                </div>
              )}

              {/* Validation Errors */}
              {validationErrors.length > 0 && (
                <div className="editorSidebarSection">
                  <span className="editorSidebarTitle">Errors</span>
                  <div className="editorValidationList">
                    {validationErrors.map((err, idx) => (
                      <div key={idx} className="editorValidationItem error">
                        <AlertTriangle size={16} style={{ flexShrink: 0 }} />
                        <span>
                          {err.message}
                          {err.x !== undefined && ` at (${err.x}, ${err.y})`}
                        </span>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              <div className="editorSidebarSection">
                <span className="editorSidebarTitle">Instructions</span>
                <p style={{ fontSize: "0.85rem", color: "#94a3b8", lineHeight: 1.5 }}>
                  Select a tool and click on the grid to paint.
                  <br />
                  <br />
                  <strong>Entries</strong>/<strong>Exits</strong> must be on boundary.
                </p>
              </div>
            </div>

            {/* Canvas */}
            <div className={`editorCanvasContainer ${viewMode === "3D" ? "mode-3d" : ""}`}>
              {loading ? (
                <Loader2 className="spinner" size={48} />
              ) : viewMode === "3D" ? (
                <Scene3D grid={grid} onCellClick={handleCellClick} />
              ) : (
                renderGrid()
              )}
            </div>
          </div>
        </div>
      )}

      {/* Save Dialog */}
      {saveDialogOpen && (
        <div className="editorSaveDialog">
          <div className="editorSaveDialogContent">
            <h2 className="editorCardTitle">Save Parking Lot</h2>
            <p className="editorCardSub">Give your parking lot a unique name.</p>

            <div>
              <label className="editorFieldLabel" style={{ marginBottom: 8, display: "block" }}>
                Name
              </label>
              <input
                className="editorNumInput"
                style={{ width: "100%", textAlign: "left" }}
                value={saveName}
                onChange={(e) => setSaveName(e.target.value)}
                placeholder="e.g. Downtown Garage A"
              />
              {saveError && <p style={{ color: "red", fontSize: "0.8rem", marginTop: 4 }}>{saveError}</p>}
            </div>

            <div className="editorDialogButtons">
              <button className="editorBtnGhost" onClick={() => setSaveDialogOpen(false)}>
                Cancel
              </button>
              <button className="editorBtnPrimary" onClick={handleSave} disabled={saving}>
                {saving ? "Saving..." : "Save"}
              </button>
            </div>
          </div>
        </div>
      )}
    </AppLayout>
  );
}


