import sqlite3
import os

DB_PATH = "parking_lots.db"

def migrate():
    if not os.path.exists(DB_PATH):
        print("Database not found, skipping migration (tables will be created on startup).")
        return

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    try:
        # Check if column exists
        cursor.execute("PRAGMA table_info(simulation_results)")
        columns = [info[1] for info in cursor.fetchall()]
        
        if "name" not in columns:
            print("Adding 'name' column to simulation_results...")
            cursor.execute("ALTER TABLE simulation_results ADD COLUMN name VARCHAR(120)")
            conn.commit()
            print("Migration successful.")
        else:
            print("'name' column already exists.")
            
    except Exception as e:
        print(f"Migration error: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    migrate()
