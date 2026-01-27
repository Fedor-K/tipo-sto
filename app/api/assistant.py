# -*- coding: utf-8 -*-
"""
AI Assistant API Router
Chat endpoint for mechanics with image support
"""
from typing import Optional
from fastapi import APIRouter, UploadFile, File, Form
from pydantic import BaseModel
import base64

from app.services.ai_assistant import get_ai_service

router = APIRouter(prefix="/assistant", tags=["assistant"])


class ChatRequest(BaseModel):
    """Chat request model"""
    message: str
    session_id: Optional[str] = "default"
    car_context: Optional[str] = None
    image_base64: Optional[str] = None  # Base64 encoded image


class ChatResponse(BaseModel):
    """Chat response model"""
    response: str
    session_id: str


@router.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """
    Send message to AI assistant and get response.

    - **message**: Your question about car repair
    - **session_id**: Optional session ID to maintain conversation history
    - **car_context**: Optional context about the car being worked on
    - **image_base64**: Optional base64 encoded image for vision analysis
    """
    service = get_ai_service()
    response = await service.chat(
        message=request.message,
        session_id=request.session_id,
        car_context=request.car_context,
        image_base64=request.image_base64,
    )
    return ChatResponse(response=response, session_id=request.session_id)


@router.post("/chat-with-image", response_model=ChatResponse)
async def chat_with_image(
    message: str = Form(...),
    session_id: str = Form("default"),
    car_context: Optional[str] = Form(None),
    image: UploadFile = File(None),
):
    """
    Send message with image to AI assistant.

    Upload an image file along with your question for visual diagnosis.
    """
    service = get_ai_service()

    image_base64 = None
    if image and image.content_type and image.content_type.startswith("image/"):
        content = await image.read()
        image_base64 = base64.b64encode(content).decode("utf-8")

    response = await service.chat(
        message=message,
        session_id=session_id,
        car_context=car_context,
        image_base64=image_base64,
    )
    return ChatResponse(response=response, session_id=session_id)


@router.post("/clear")
async def clear_history(session_id: str = "default"):
    """Clear conversation history for a session"""
    service = get_ai_service()
    service.clear_history(session_id)
    return {"success": True, "message": "История очищена"}


@router.get("/status")
async def assistant_status():
    """Check if AI assistant is configured"""
    from app.config import get_settings
    settings = get_settings()
    configured = bool(settings.OPENAI_API_KEY)
    return {
        "configured": configured,
        "model": "GPT-4 Vision",
        "features": ["text", "images"],
        "message": "AI помощник готов (с поддержкой фото)" if configured else "Требуется API ключ (OPENAI_API_KEY)",
    }


@router.get("/logs")
async def get_chat_logs(date: Optional[str] = None):
    """
    Get chat logs for analysis.

    - **date**: Optional date in YYYY-MM-DD format (defaults to today)
    """
    service = get_ai_service()
    logs = service.get_chat_logs(date)
    return {
        "date": date or "today",
        "count": len(logs),
        "logs": logs,
    }
