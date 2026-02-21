import sys
import os

print("--- Testing app.models.database ---")
try:
    from app.models.database import get_connection
    print("✅ app.models.database OK")
except Exception as e:
    print(f"❌ app.models.database FAIL: {e}")

print("\n--- Testing app.services.case_service ---")
try:
    from app.services.case_service import get_all_cases_summary
    print("✅ app.services.case_service OK")
except Exception as e:
    print(f"❌ app.services.case_service FAIL: {e}")

print("\n--- Testing app.services.openai_service ---")
try:
    from app.services.openai_service import chat_service
    print("✅ app.services.openai_service OK")
except Exception as e:
    print(f"❌ app.services.openai_service FAIL: {e}")
