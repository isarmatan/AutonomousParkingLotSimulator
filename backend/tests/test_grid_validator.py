import pytest
from editor.grid_validator import GridValidator, ValidationIssue
from generator.grid import Grid
from generator.cell import CellType

def create_grid(width, height, setup_fn=None):
    grid = Grid(width, height)
    # Initialize with walls/road mix or all road? 
    # Default grid is empty (ROAD? or null?). 
    # Looking at Grid implementation, it usually initializes empty or we set cells.
    # Let's assume we need to set cells manually.
    
    # Fill with walls first for safety in tests
    for x in range(width):
        for y in range(height):
            grid.get_cell(x, y).type = CellType.WALL
            
    if setup_fn:
        setup_fn(grid)
    return grid

def test_basic_constraints_success():
    def setup(grid):
        # Add required components on boundary
        grid.get_cell(1, 0).type = CellType.ENTRY
        grid.get_cell(2, 0).type = CellType.EXIT
        # Add parking inside
        grid.get_cell(1, 1).type = CellType.PARKING
        
    grid = create_grid(5, 5, setup)
    issues = GridValidator.validate_basic_constraints(grid)
    assert len(issues) == 0

def test_missing_components():
    grid = create_grid(5, 5) # All walls
    issues = GridValidator.validate_basic_constraints(grid)
    
    msgs = [i.message for i in issues]
    assert any("at least one ENTRY" in m for m in msgs)
    assert any("at least one EXIT" in m for m in msgs)
    assert any("at least one PARKING" in m for m in msgs)

def test_invalid_boundary_placement():
    def setup(grid):
        # Entry in middle (invalid)
        grid.get_cell(2, 2).type = CellType.ENTRY
        # Exit in middle (invalid)
        grid.get_cell(2, 3).type = CellType.EXIT
        # Parking on boundary (invalid per optional rule, but let's check)
        grid.get_cell(0, 2).type = CellType.PARKING
        
    grid = create_grid(5, 5, setup)
    issues = GridValidator.validate_basic_constraints(grid)
    
    msgs = [i.message for i in issues]
    assert any("ENTRY at (2,2) is not on a valid boundary" in m for m in msgs)
    assert any("EXIT at (2,3) is not on a valid boundary" in m for m in msgs)
    assert any("PARKING at (0,2) cannot be on grid boundary" in m for m in msgs)

def test_connectivity_success():
    def setup(grid):
        # Simple path: Entry(1,0) -> Road(1,1) -> Parking(1,2) -> Road(1,3) -> Exit(1,4)
        grid.get_cell(1, 0).type = CellType.ENTRY
        grid.get_cell(1, 1).type = CellType.ROAD
        grid.get_cell(1, 2).type = CellType.PARKING
        grid.get_cell(1, 3).type = CellType.ROAD
        grid.get_cell(1, 4).type = CellType.EXIT # Exit on boundary
        
    grid = create_grid(5, 5, setup)
    issues = GridValidator.validate_connectivity(grid)
    assert len(issues) == 0

def test_unreachable_island():
    def setup(grid):
        # Connected Component 1
        grid.get_cell(1, 0).type = CellType.ENTRY
        grid.get_cell(1, 1).type = CellType.ROAD
        
        # Disconnected Component 2 (Island)
        grid.get_cell(3, 3).type = CellType.PARKING
        grid.get_cell(3, 2).type = CellType.ROAD # Just some road next to it
        
    grid = create_grid(5, 5, setup)
    issues = GridValidator.validate_connectivity(grid)
    
    msgs = [i.message for i in issues]
    # The Parking at (3,3) should be unreachable
    assert any("PARKING at (3,3) is not reachable" in m for m in msgs)

def test_entry_not_reachable():
    def setup(grid):
        # Entry 1 (connected)
        grid.get_cell(1, 0).type = CellType.ENTRY
        
        # Entry 2 (blocked by walls)
        grid.get_cell(4, 0).type = CellType.ENTRY
        # Surrounding walls are default
        
    grid = create_grid(5, 5, setup)
    issues = GridValidator.validate_connectivity(grid)
    
    # Depending on which entry is picked as start_node, the other might be unreachable
    # Or both if start_node logic picks one.
    # Validator logic:
    # 1. Finds start_node (likely (1,0))
    # 2. BFS
    # 3. Check all functional.
    # So (4,0) should be reported.
    
    msgs = [i.message for i in issues]
    assert any("ENTRY at (4,0) is not reachable" in m for m in msgs)

def test_no_drivable_cells():
    grid = create_grid(5, 5) # All walls
    issues = GridValidator.validate_connectivity(grid)
    assert len(issues) == 1
    assert issues[0].message == "No drivable cells found in grid"
