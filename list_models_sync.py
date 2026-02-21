import httpx
import os
from dotenv import load_dotenv

load_dotenv()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

def list_models():
    if not GEMINI_API_KEY:
        print("API Key is missing.")
        return

    url = f"https://generativelanguage.googleapis.com/v1beta/models?key={GEMINI_API_KEY}"
    
    try:
        with httpx.Client(timeout=30.0) as client:
            response = client.get(url)
            if response.status_code == 200:
                models = response.json().get('models', [])
                print("Available Models:")
                for model in models:
                    print(f"- {model['name']}")
            else:
                print(f"FAILURE: Status {response.status_code}")
                print(response.text)
    except Exception as e:
        print(f"ERROR: {e}")

if __name__ == "__main__":
    list_models()
