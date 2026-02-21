import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(__file__), '..', '..', 'database.db')

def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def get_all_cases_summary():
    """
    Returns a compact text summary of all cases for the AI chatbot context.
    """
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT id, missing_full_name, age, gender, missing_city, missing_state, status, created_at FROM cases ORDER BY created_at DESC")
        cases = cursor.fetchall()
        conn.close()

        if not cases:
            return "No missing person cases are currently registered in the system."

        summary_lines = ["Current Missing Person Cases in Database:"]
        for case in cases:
            # Safely handle missing fields if any
            name = case['missing_full_name']
            age = case['age']
            gender = case['gender']
            city = case['missing_city']
            state = case['missing_state']
            status = case['status']
            date = case['created_at']
            
            line = f"- {name} ({age}y/o, {gender}) from {city}, {state}. Status: {status}. Reported on: {date}"
            summary_lines.append(line)
        
        return "\n".join(summary_lines)
    except Exception as e:
        print(f"Error in get_all_cases_summary: {e}")
        return "Internal error: Could not retrieve missing persons data."
