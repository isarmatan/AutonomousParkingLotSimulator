import sys
import os

# Add project root to sys.path so we can import from db
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from sqlalchemy import select
from sqlalchemy.orm import Session
from db.database import engine, init_db
from db.models import ParkingLotModel
import json

def render_grid(grid_data):
    width = grid_data['width']
    height = grid_data['height']
    cells = grid_data['cells']
    
    # Create empty grid
    grid_map = [[' ' for _ in range(width)] for _ in range(height)]
    
    # Fill grid
    for cell in cells:
        x = cell['x']
        y = cell['y']
        c_type = cell['type']
        
        char = '?'
        if c_type == 'WALL': char = '#'
        elif c_type == 'ROAD': char = '.'
        elif c_type == 'PARKING': char = 'P'
        elif c_type == 'ENTRY': char = 'E'
        elif c_type == 'EXIT': char = 'X'
        
        if 0 <= x < width and 0 <= y < height:
            grid_map[y][x] = char
            
    # Convert to string
    lines = []
    lines.append('+' + '-' * width + '+')
    for row in grid_map:
        lines.append('|' + ''.join(row) + '|')
    lines.append('+' + '-' * width + '+')
    return "\n".join(lines)

def show_db_contents():
    # Ensure tables exist
    init_db()

    output_file = "visible_grids.txt"
    
    with Session(engine) as session:
        stmt = select(ParkingLotModel).order_by(ParkingLotModel.created_at.desc())
        results = session.scalars(stmt).all()

        with open(output_file, "w", encoding="utf-8") as f:
            f.write(f"Found {len(results)} saved parking lots in the database:\n")
            f.write("=" * 60 + "\n\n")

            for lot in results:
                f.write(f"ID: {lot.id}\n")
                f.write(f"Name: {lot.name}\n")
                f.write(f"Created At: {lot.created_at}\n")
                
                try:
                    grid_data = json.loads(lot.grid_json)
                    f.write(f"Dimensions: {grid_data.get('width')}x{grid_data.get('height')}\n")
                    f.write("Preview:\n")
                    f.write(render_grid(grid_data))
                except Exception as e:
                    f.write(f"Error rendering grid: {e}\n")
                
                f.write("\n" + "-" * 60 + "\n\n")

    print(f"Exported {len(results)} grids to {output_file}")

if __name__ == "__main__":
    show_db_contents()
