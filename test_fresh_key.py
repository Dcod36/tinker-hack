import asyncio
import httpx
import os
from dotenv import load_dotenv

load_dotenv()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
# Testing 2.0-flash on v1beta as it is typically preferred now
GEMINI_API_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent"

async def test_key():
    if not GEMINI_API_KEY:
        print("API Key is missing.")
        return

    payload = {
        "contents": [
            {
                "role": "user",
                "parts": [{"text": "Say 'Fresh key test successful!'"}]
            }
        ],
        "generationConfig": {
            "temperature": 0.7,
            "maxOutputTokens": 20,
        }
    }

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(
                f"{GEMINI_API_URL}?key={GEMINI_API_KEY}",
                json=payload,
            )
            print(f"Status: {response.status_code}")
            if response.status_code == 200:
                print("SUCCESS!")
                print(response.json()["candidates"][0]["content"]["parts"][0]["text"])
            else:
                print(f"Response Body: {response.text}")
    except Exception as e:
        print(f"ERROR: {e}")

if __name__ == "__main__":
    asyncio.run(test_key())
