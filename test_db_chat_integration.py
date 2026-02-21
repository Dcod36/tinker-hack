import os
import sys
import sqlite3

# Add app to path
sys.path.insert(0, os.getcwd())

from app.models.database import DB_PATH

def check_db_content():
    try:
        if not os.path.exists(DB_PATH):
            print("❌ Database file not found.")
            return False
            
        from app.services.db_chat_service import get_all_cases_summary
        summary = get_all_cases_summary()
        print("\n--- Current Database Summary for AI ---")
        print(summary)
        print("---------------------------------------\n")
        return True
    except Exception as e:
        print(f"❌ Error fetching DB summary: {e}")
        return False

def verify_service_injection():
    try:
        from app.services.openai_service import chat_service
        print("✅ OpenAIChatService with DB context initialized.")
        return True
    except Exception as e:
        print(f"❌ Error initializing OpenAIChatService: {e}")
        return False

if __name__ == "__main__":
    v1 = check_db_content()
    v2 = verify_service_injection()
    
    if v1 and v2:
        print("Integration verification successful!")
    else:
        print("Integration verification failed.")
