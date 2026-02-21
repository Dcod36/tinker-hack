import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-key-change-in-production")
    PORT = int(os.getenv("PORT", "8001"))  # 8001 to avoid conflict with default uvicorn 8000
    UPLOAD_FOLDER = os.path.join(os.path.dirname(__file__), '..', 'uploads')
    MAX_UPLOAD_SIZE = 16 * 1024 * 1024  # 16 MB
    ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'webp'}
    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")

config = Config()
