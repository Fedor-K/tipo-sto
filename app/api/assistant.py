# -*- coding: utf-8 -*-
"""
AI Assistant API Router
Chat endpoint for mechanics with image support
Includes persistent chat history (like ChatGPT/Claude)
"""
from typing import Optional, List
from fastapi import APIRouter, UploadFile, File, Form, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
import base64
import json

from app.services.ai_assistant import get_ai_service
from app.services.chat_storage import get_chat_storage

router = APIRouter(prefix="/assistant", tags=["assistant"])


class ChatRequest(BaseModel):
    """Chat request model"""
    message: str
    chat_id: Optional[str] = None  # Persistent chat ID
    session_id: Optional[str] = "default"  # Legacy session ID
    car_context: Optional[str] = None
    image_base64: Optional[str] = None  # Base64 encoded image


class ChatResponse(BaseModel):
    """Chat response model"""
    response: str
    chat_id: Optional[str] = None
    session_id: str


class ChatSummary(BaseModel):
    """Chat summary for list"""
    id: str
    title: str
    created_at: str
    updated_at: str
    message_count: int


class ChatDetail(BaseModel):
    """Full chat with messages"""
    id: str
    title: str
    created_at: str
    updated_at: str
    messages: List[dict]


class CreateChatRequest(BaseModel):
    """Create new chat request"""
    title: Optional[str] = None


class UpdateChatRequest(BaseModel):
    """Update chat request"""
    title: str


@router.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """
    Send message to AI assistant and get response.

    - **message**: Your question about car repair
    - **chat_id**: Optional persistent chat ID (creates new if not provided)
    - **session_id**: Optional session ID to maintain conversation history
    - **car_context**: Optional context about the car being worked on
    - **image_base64**: Optional base64 encoded image for vision analysis
    """
    service = get_ai_service()
    storage = get_chat_storage()

    chat_id = request.chat_id

    # Create new chat if no chat_id provided
    if not chat_id:
        new_chat = storage.create_chat(request.message)
        chat_id = new_chat["id"]

    # Save user message
    storage.add_message(
        chat_id=chat_id,
        role="user",
        content=request.message,
        has_image=bool(request.image_base64)
    )

    # Get AI response (use chat_id as session_id for history)
    response = await service.chat(
        message=request.message,
        session_id=chat_id,
        car_context=request.car_context,
        image_base64=request.image_base64,
    )

    # Save assistant response
    storage.add_message(
        chat_id=chat_id,
        role="assistant",
        content=response
    )

    return ChatResponse(response=response, chat_id=chat_id, session_id=chat_id)


@router.post("/chat/stream")
async def chat_stream(request: ChatRequest):
    """
    Stream chat response (Server-Sent Events).
    Text appears as it's generated - like ChatGPT.
    """
    service = get_ai_service()
    storage = get_chat_storage()

    chat_id = request.chat_id

    # Create new chat if no chat_id provided
    if not chat_id:
        new_chat = storage.create_chat(request.message)
        chat_id = new_chat["id"]

    # Save user message
    storage.add_message(
        chat_id=chat_id,
        role="user",
        content=request.message,
        has_image=bool(request.image_base64)
    )

    async def generate():
        full_response = ""
        # Send chat_id first
        yield f"data: {json.dumps({'chat_id': chat_id})}\n\n"

        async for chunk in service.chat_stream(
            message=request.message,
            session_id=chat_id,
            car_context=request.car_context,
            image_base64=request.image_base64,
        ):
            full_response += chunk
            yield f"data: {json.dumps({'text': chunk})}\n\n"

        # Save complete response
        storage.add_message(chat_id=chat_id, role="assistant", content=full_response)
        yield f"data: {json.dumps({'done': True})}\n\n"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        }
    )


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


# ============================================
# Chat History Management (like ChatGPT/Claude)
# ============================================

@router.get("/chats", response_model=List[ChatSummary])
async def list_chats(limit: int = 50):
    """
    Get list of all saved chats.

    Returns chat summaries sorted by last update (newest first).
    """
    storage = get_chat_storage()
    chats = storage.list_chats(limit=limit)
    return chats


@router.post("/chats", response_model=ChatDetail)
async def create_chat(request: CreateChatRequest = None):
    """
    Create a new empty chat.

    - **title**: Optional title (defaults to "Новый чат")
    """
    storage = get_chat_storage()
    chat = storage.create_chat()
    if request and request.title:
        chat = storage.update_title(chat["id"], request.title)
    return chat


@router.get("/chats/{chat_id}", response_model=ChatDetail)
async def get_chat(chat_id: str):
    """
    Get a specific chat with all messages.

    - **chat_id**: Chat ID
    """
    storage = get_chat_storage()
    chat = storage.get_chat(chat_id)
    if not chat:
        raise HTTPException(status_code=404, detail="Чат не найден")
    return chat


@router.put("/chats/{chat_id}")
async def update_chat(chat_id: str, request: UpdateChatRequest):
    """
    Update chat title.

    - **chat_id**: Chat ID
    - **title**: New title
    """
    storage = get_chat_storage()
    chat = storage.update_title(chat_id, request.title)
    if not chat:
        raise HTTPException(status_code=404, detail="Чат не найден")
    return chat


@router.delete("/chats/{chat_id}")
async def delete_chat(chat_id: str):
    """
    Delete a chat.

    - **chat_id**: Chat ID
    """
    storage = get_chat_storage()
    deleted = storage.delete_chat(chat_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Чат не найден")
    return {"success": True, "message": "Чат удалён"}
