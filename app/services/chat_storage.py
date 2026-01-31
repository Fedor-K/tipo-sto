# -*- coding: utf-8 -*-
"""
Chat Storage Service
Persistent storage for chat conversations (like ChatGPT/Claude)
"""
import json
import logging
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, List, Any

logger = logging.getLogger(__name__)

# Conversations directory
CONVERSATIONS_DIR = Path(__file__).parent.parent.parent / "data" / "conversations"
CONVERSATIONS_DIR.mkdir(parents=True, exist_ok=True)


class ChatStorageService:
    """Persistent chat storage service"""

    def __init__(self):
        self._ensure_dir()

    def _ensure_dir(self):
        """Ensure conversations directory exists"""
        CONVERSATIONS_DIR.mkdir(parents=True, exist_ok=True)

    def _get_path(self, chat_id: str) -> Path:
        """Get file path for a chat"""
        return CONVERSATIONS_DIR / f"{chat_id}.json"

    def _generate_title(self, message: str) -> str:
        """Generate chat title from first message"""
        # Take first 50 chars, clean up
        title = message.strip()[:50]
        if len(message) > 50:
            title += "..."
        return title

    def create_chat(self, first_message: str = None) -> Dict[str, Any]:
        """
        Create a new chat conversation

        Args:
            first_message: Optional first message to generate title

        Returns:
            New chat object
        """
        chat_id = str(uuid.uuid4())[:8]  # Short ID
        now = datetime.now().isoformat()

        chat = {
            "id": chat_id,
            "title": self._generate_title(first_message) if first_message else "Новый чат",
            "created_at": now,
            "updated_at": now,
            "messages": []
        }

        self._save_chat(chat)
        logger.info(f"Created new chat: {chat_id}")
        return chat

    def get_chat(self, chat_id: str) -> Optional[Dict[str, Any]]:
        """
        Get a chat by ID

        Args:
            chat_id: Chat ID

        Returns:
            Chat object or None
        """
        path = self._get_path(chat_id)
        if not path.exists():
            return None

        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Error loading chat {chat_id}: {e}")
            return None

    def list_chats(self, limit: int = 50) -> List[Dict[str, Any]]:
        """
        List all chats, sorted by updated_at desc

        Args:
            limit: Max number of chats to return

        Returns:
            List of chat summaries (without full messages)
        """
        chats = []

        for path in CONVERSATIONS_DIR.glob("*.json"):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    chat = json.load(f)
                    # Return summary without full messages
                    chats.append({
                        "id": chat["id"],
                        "title": chat["title"],
                        "created_at": chat["created_at"],
                        "updated_at": chat["updated_at"],
                        "message_count": len(chat.get("messages", []))
                    })
            except Exception as e:
                logger.error(f"Error loading chat {path}: {e}")

        # Sort by updated_at descending
        chats.sort(key=lambda x: x["updated_at"], reverse=True)
        return chats[:limit]

    def add_message(
        self,
        chat_id: str,
        role: str,
        content: str,
        has_image: bool = False
    ) -> Optional[Dict[str, Any]]:
        """
        Add a message to a chat

        Args:
            chat_id: Chat ID
            role: 'user' or 'assistant'
            content: Message content
            has_image: Whether message had an image

        Returns:
            Updated chat or None
        """
        chat = self.get_chat(chat_id)
        if not chat:
            return None

        message = {
            "role": role,
            "content": content,
            "timestamp": datetime.now().isoformat(),
            "has_image": has_image
        }

        chat["messages"].append(message)
        chat["updated_at"] = datetime.now().isoformat()

        # Update title if this is first user message and title is default
        if (chat["title"] == "Новый чат" and
            role == "user" and
            len([m for m in chat["messages"] if m["role"] == "user"]) == 1):
            chat["title"] = self._generate_title(content)

        self._save_chat(chat)
        return chat

    def update_title(self, chat_id: str, title: str) -> Optional[Dict[str, Any]]:
        """
        Update chat title

        Args:
            chat_id: Chat ID
            title: New title

        Returns:
            Updated chat or None
        """
        chat = self.get_chat(chat_id)
        if not chat:
            return None

        chat["title"] = title[:100]  # Limit title length
        chat["updated_at"] = datetime.now().isoformat()
        self._save_chat(chat)
        return chat

    def delete_chat(self, chat_id: str) -> bool:
        """
        Delete a chat

        Args:
            chat_id: Chat ID

        Returns:
            True if deleted, False if not found
        """
        path = self._get_path(chat_id)
        if path.exists():
            path.unlink()
            logger.info(f"Deleted chat: {chat_id}")
            return True
        return False

    def _save_chat(self, chat: Dict[str, Any]):
        """Save chat to file"""
        path = self._get_path(chat["id"])
        with open(path, "w", encoding="utf-8") as f:
            json.dump(chat, ensure_ascii=False, indent=2, fp=f)

    def get_messages_for_ai(self, chat_id: str) -> List[Dict[str, str]]:
        """
        Get messages in format suitable for AI API

        Args:
            chat_id: Chat ID

        Returns:
            List of messages in OpenAI format
        """
        chat = self.get_chat(chat_id)
        if not chat:
            return []

        # Convert to OpenAI format, keep last 10 messages
        messages = []
        for msg in chat.get("messages", [])[-10:]:
            messages.append({
                "role": msg["role"],
                "content": msg["content"]
            })
        return messages


# Singleton
_storage_service: Optional[ChatStorageService] = None


def get_chat_storage() -> ChatStorageService:
    """Get chat storage service singleton"""
    global _storage_service
    if _storage_service is None:
        _storage_service = ChatStorageService()
    return _storage_service
