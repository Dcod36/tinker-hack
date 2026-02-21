import os
import sys

# Ensure we are in the right directory
os.chdir(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.getcwd())

print(f"Current Working Directory: {os.getcwd()}")

try:
    from app.services.case_service import get_case_stats_by_date
    from app.models.database import DB_PATH
    
    print(f"Database Path in use: {DB_PATH}")
    print(f"Database Exists: {os.path.exists(DB_PATH)}")
    
    stats = get_case_stats_by_date()
    print(f"Stats from function: {stats}")
    
    import sqlite3
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM cases")
    count = cursor.fetchone()[0]
    print(f"Total cases in DB: {count}")
    
    cursor.execute("SELECT missing_date FROM cases")
    dates = cursor.fetchall()
    print(f"All missing_date values: {dates}")
    conn.close()

except Exception as e:
    print(f"Error occurred: {e}")
    import traceback
    traceback.print_exc()
