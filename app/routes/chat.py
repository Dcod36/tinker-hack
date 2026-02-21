from fastapi import APIRouter
from pydantic import BaseModel

from app.services.gemini_service import chat_service

router = APIRouter()


class ChatRequest(BaseModel):
    message: str


class ChatResponse(BaseModel):
    reply: str


@router.post("/api/chat", response_model=ChatResponse)
async def chat(req: ChatRequest):
    reply = await chat_service.get_response(req.message)
    return ChatResponse(reply=reply)
