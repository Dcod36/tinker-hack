import asyncio
import httpx
import os
from dotenv import load_dotenv

load_dotenv()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

async def list_models():
    if not GEMINI_API_KEY:
        print("API Key is missing.")
        return

    url = f"https://generativelanguage.googleapis.com/v1beta/models?key={GEMINI_API_KEY}"
    
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(url)
            if response.status_code == 200:
                models = response.json().get('models', [])
                print("Available Models:")
                for model in models:
                    print(f"- {model['name']} (Supports: {', '.join(model.get('supportedGenerationMethods', []))})")
            else:
                print(f"FAILURE: Status {response.status_code}")
                print(response.text)
    except Exception as e:
        print(f"ERROR: {e}")

if __name__ == "__main__":
    asyncio.run(list_models())
