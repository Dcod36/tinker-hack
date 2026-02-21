import os
import sys
import sqlite3

# Ensure we are in the right directory
os.chdir(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.getcwd())

from app.models.database import DB_PATH
from app.config import config

print(f"DEBUG: Using DB_PATH = {DB_PATH}")

def check_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    # Check cases
    cursor.execute("SELECT * FROM cases")
    rows = cursor.fetchall()
    print(f"DEBUG: Found {len(rows)} cases in DB")
    
    for row in rows:
        print(f"CASE ID: {row['id']}")
        print(f"  Name: {row['missing_full_name']}")
        print(f"  Date: '{row['missing_date']}' (len: {len(str(row['missing_date']))})")
        print(f"  Image: '{row['image_path']}'")
        
        # Check if file exists
        full_path = os.path.join(config.UPLOAD_FOLDER, row['image_path'])
        exists = os.path.exists(full_path)
        print(f"  File Exists at {full_path}: {exists}")
        
    # Check stats query manually
    cursor.execute("""
        SELECT missing_date, COUNT(*) as count 
        FROM cases 
        WHERE missing_date IS NOT NULL AND missing_date != ''
        GROUP BY missing_date
    """)
    stats_rows = cursor.fetchall()
    print(f"DEBUG: Stats query returned {len(stats_rows)} rows")
    for r in stats_rows:
        print(f"  - {r['missing_date']}: {r['count']}")
        
    conn.close()

if __name__ == "__main__":
    check_db()
