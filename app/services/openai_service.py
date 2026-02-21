import httpx
import os
from app.config import config

SYSTEM_PROMPT = """You are a helpful assistant for the National Missing Person Support System, specialized in child safety and recovery.
Your primary goal is to guide users through the immediate steps when a child is missing:
1. Contact local law enforcement/emergency services (100 or 112) IMMEDIATELY. There is NO waiting period for children.
2. Provide a detailed description: Full name, age, height, hair color, and the EXACT clothing they were last seen wearing.
3. Use this platform: Upload the most recent, clear photograph of the child to our AI facial recognition system.
4. Gather information: Note the time and location where the child was last seen and a list of their friends or frequented places.

Be extremely empathetic, calm, and professional. Prioritize urgent safety advice above all else.
Keep responses brief (2-3 sentences) to avoid overwhelming the user, unless they ask for specific procedural details."""

from app.services.db_chat_service import get_all_cases_summary

OPENAI_API_URL = "https://api.openai.com/v1/chat/completions"

class OpenAIChatService:
    def __init__(self):
        self.api_key = os.getenv("OPENAI_API_KEY")

    async def get_response(self, user_message: str) -> str:
        if not self.api_key or self.api_key == "your_openai_key_here":
            return "Please configure the OpenAI API key in the .env file to enable the chatbot."

        # Fetch the latest data from the database
        db_context = get_all_cases_summary()

        full_system_prompt = f"{SYSTEM_PROMPT}\n\nDATABASE CONTEXT:\n{db_context}\n\nUse the above database context to answer any questions about missing persons registered in the system. If a user asks who is missing, list the people from the context above. If they ask about a specific person, provide their details from the context."

        payload = {
            "model": "gpt-4o-mini",
            "messages": [
                {"role": "system", "content": full_system_prompt},
                {"role": "user", "content": user_message}
            ],
            "temperature": 0.7,
            "max_tokens": 400
        }

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    OPENAI_API_URL,
                    json=payload,
                    headers=headers
                )
                
                if response.status_code != 200:
                    error_data = response.json()
                    print(f"OpenAI API error: {error_data}")
                    return "I'm having trouble connecting to OpenAI. Please check your API key and quota."
                
                data = response.json()
                return data["choices"][0]["message"]["content"]
        except Exception as e:
            print(f"OpenAI service error: {e}")
            return "An unexpected error occurred. Please try again later."

chat_service = OpenAIChatService()
