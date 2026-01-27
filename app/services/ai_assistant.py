# -*- coding: utf-8 -*-
"""
AI Assistant Service for Mechanics
Uses OpenAI GPT-4 Vision for car repair advice and image analysis
"""
import base64
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional
import httpx

from app.config import get_settings
from app.services.vin_decoder import get_vin_service

# Chat logs directory
CHAT_LOGS_DIR = Path(__file__).parent.parent.parent / "data" / "chat_logs"
CHAT_LOGS_DIR.mkdir(parents=True, exist_ok=True)

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """Ты - опытный автомеханик-консультант в автосервисе (СТО).
Ты отвечаешь ТОЛЬКО на вопросы про автомобили, автозапчасти и работы СТО.

ВАЖНО: Ты НЕ отвечаешь на вопросы, не связанные с автомобилями!
Если тебя спрашивают про что-то другое (электроника, бытовая техника, наушники, телефоны и т.д.) -
вежливо откажись и скажи, что ты специализируешься только на автомобилях.

Если на фото НЕ автомобильная деталь или узел - скажи: "Это не похоже на автозапчасть. Я могу помочь только с автомобильными деталями и ремонтом."

## КОНТЕКСТ АВТОМОБИЛЯ

ВАЖНО: Если механик отправляет VIN-код (17 символов) - система АВТОМАТИЧЕСКИ расшифрует его и покажет марку/модель.
Используй эту информацию для точных ответов.

Если VIN не указан - спроси механика про автомобиль: "Подскажите марку и модель автомобиля (или VIN-код), чтобы я мог дать более точный ответ."

Когда механик называет автомобиль (например "Kia Rio 2018" или "BMW X5 E70") - ЗАПОМНИ это и используй в ответах.
Если в сообщении упоминается марка/модель - учитывай это для всех последующих ответов в сессии.

Если знаешь автомобиль - давай специфичные рекомендации:
- Точные моменты затяжки для этой модели
- Типичные болячки этой марки/модели
- Специфические коды ошибок производителя (P1xxx)
- Рекомендуемые масла и жидкости

## OBD-II КОДЫ ОШИБОК

Ты эксперт по диагностическим кодам OBD-II (DTC). Когда механик спрашивает про код ошибки:

1. **Расшифруй код** - что он означает
2. **Назови возможные причины** - от самых частых к редким (обычно 3-5 причин)
3. **Дай план диагностики** - что проверить в первую очередь
4. **Укажи** какие датчики/узлы задействованы
5. **Если есть** - упомяни типичные проблемы для конкретной марки/модели

Структура кодов OBD-II:
- P0xxx - Трансмиссия (двигатель, КПП) - общие коды
- P1xxx - Трансмиссия - коды производителя
- P2xxx - Трансмиссия - общие коды (расширенные)
- P3xxx - Трансмиссия - резерв
- B0xxx - Кузов - общие
- B1xxx - Кузов - коды производителя
- C0xxx - Шасси - общие
- C1xxx - Шасси - коды производителя
- U0xxx - Сеть/коммуникация - общие
- U1xxx - Сеть - коды производителя

Примеры частых кодов:
- P0300 - случайные пропуски зажигания
- P0171/P0174 - бедная смесь (банк 1/2)
- P0172/P0175 - богатая смесь (банк 1/2)
- P0420/P0430 - эффективность катализатора ниже порога
- P0440-P0449 - система EVAP (улавливание паров топлива)
- P0500 - датчик скорости автомобиля
- P0335/P0340 - датчик положения коленвала/распредвала

## МОМЕНТЫ ЗАТЯЖКИ

Если спрашивают про момент затяжки - давай точные значения в Н·м.
Типичные значения (если не знаешь точно для модели):
- Колёсные болты: 100-120 Н·м (легковые), 140-160 Н·м (внедорожники)
- Свечи зажигания: 20-30 Н·м
- Сливная пробка поддона: 25-35 Н·м
- Масляный фильтр: затягивать руками + 3/4 оборота

## ПРАВИЛА

1. Отвечай кратко и по делу - механики ценят конкретику
2. Давай пошаговые инструкции когда это нужно
3. Предупреждай о технике безопасности
4. Указывай нужные инструменты
5. Если не уверен в точных значениях - скажи об этом

Ты можешь помочь с:
- Расшифровкой OBD-II кодов ошибок (DTC)
- Диагностикой неисправностей по симптомам
- Анализом фотографий автодеталей
- Моментами затяжки, допусками
- Порядком выполнения работ
- Выбором запчастей и расходников
- Типичными болячками марок/моделей

Если отправляют фото автодетали - дай диагностику:
- Что это за деталь
- В каком состоянии
- Нужна ли замена
- На что обратить внимание

Отвечай на русском языке."""


class AIAssistantService:
    """AI Assistant for mechanics using OpenAI GPT-4 Vision"""

    def __init__(self):
        self.settings = get_settings()
        self.api_key = self.settings.OPENAI_API_KEY
        self.api_url = "https://api.openai.com/v1/chat/completions"
        self._conversation_history: Dict[str, List[dict]] = {}
        # Log API key status (first 10 chars only for security)
        if self.api_key:
            logger.info(f"OpenAI API key loaded: {self.api_key[:10]}... (length: {len(self.api_key)})")
        else:
            logger.warning("OpenAI API key NOT loaded!")

    def _get_headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    async def chat(
        self,
        message: str,
        session_id: str = "default",
        car_context: Optional[str] = None,
        image_base64: Optional[str] = None,
        image_url: Optional[str] = None,
    ) -> str:
        """
        Send a message and get AI response.

        Args:
            message: User's question
            session_id: Session ID for conversation history
            car_context: Optional context about current car (make, model, year, issue)
            image_base64: Optional base64 encoded image for vision analysis
            image_url: Optional URL to image for vision analysis

        Returns:
            AI response text
        """
        if not self.api_key:
            return "❌ API ключ не настроен. Добавьте OPENAI_API_KEY в .env файл."

        # Try to detect and decode VIN in message
        vin_info = ""
        vin_service = get_vin_service()
        detected_vin = vin_service.extract_vin_from_text(message)
        if detected_vin:
            decoded = await vin_service.decode_vin(detected_vin)
            if decoded.get("success"):
                vin_info = vin_service.format_for_chat(decoded)
                # Store car context for session (без года - API часто ошибается)
                car_context = f"{decoded.get('make', '')} {decoded.get('model', '')}".strip()
                logger.info(f"VIN detected and decoded: {detected_vin} -> {car_context}")

        # Build system prompt with car context if provided
        system = SYSTEM_PROMPT
        if car_context:
            system += f"\n\nКонтекст текущего автомобиля:\n{car_context}"

        # Get or create conversation history
        if session_id not in self._conversation_history:
            self._conversation_history[session_id] = []

        history = self._conversation_history[session_id]

        # Build message content
        content = []

        # Add image if provided
        if image_base64:
            content.append({
                "type": "image_url",
                "image_url": {
                    "url": f"data:image/jpeg;base64,{image_base64}",
                    "detail": "high"
                }
            })
        elif image_url:
            content.append({
                "type": "image_url",
                "image_url": {
                    "url": image_url,
                    "detail": "high"
                }
            })

        # Add text message
        content.append({
            "type": "text",
            "text": message
        })

        # Add user message to history
        user_message = {"role": "user", "content": content if (image_base64 or image_url) else message}
        history.append(user_message)

        # Keep only last 10 messages to avoid token limits
        if len(history) > 10:
            history = history[-10:]
            self._conversation_history[session_id] = history

        # Build messages array with system prompt
        messages = [{"role": "system", "content": system}] + history

        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(
                    self.api_url,
                    headers=self._get_headers(),
                    json={
                        "model": "gpt-4o",
                        "messages": messages,
                        "max_tokens": 1024,
                        "temperature": 0.7,
                    },
                )

                if response.status_code == 401:
                    return "❌ Неверный API ключ. Проверьте OPENAI_API_KEY."

                if response.status_code == 429:
                    return "❌ Превышен лимит запросов. Подождите немного."

                if response.status_code != 200:
                    error_detail = response.text[:500] if response.text else "No details"
                    logger.error(f"AI API error: {response.status_code} - {error_detail}")
                    logger.error(f"API key used: {self.api_key[:15]}...")
                    return f"❌ Ошибка API: {response.status_code}"

                data = response.json()
                assistant_message = data["choices"][0]["message"]["content"]

                # Prepend VIN info if decoded
                if vin_info:
                    assistant_message = f"{vin_info}\n\n{assistant_message}"

                # Add assistant response to history (text only for history)
                history.append({"role": "assistant", "content": assistant_message})

                # Log chat for analysis
                self._log_chat(
                    session_id=session_id,
                    message=message,
                    response=assistant_message,
                    has_image=bool(image_base64 or image_url),
                )

                return assistant_message

        except httpx.TimeoutException:
            return "❌ Превышено время ожидания. Попробуйте ещё раз."
        except Exception as e:
            logger.error(f"AI chat error: {e}")
            return f"❌ Ошибка: {str(e)}"

    def clear_history(self, session_id: str = "default"):
        """Clear conversation history for a session"""
        if session_id in self._conversation_history:
            del self._conversation_history[session_id]

    def _log_chat(
        self,
        session_id: str,
        message: str,
        response: str,
        has_image: bool = False,
    ):
        """Log chat message and response to file for analysis"""
        try:
            log_file = CHAT_LOGS_DIR / f"{datetime.now().strftime('%Y-%m-%d')}.jsonl"
            log_entry = {
                "timestamp": datetime.now().isoformat(),
                "session_id": session_id,
                "message": message,
                "response": response,
                "has_image": has_image,
            }
            with open(log_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(log_entry, ensure_ascii=False) + "\n")
        except Exception as e:
            logger.error(f"Failed to log chat: {e}")

    def get_chat_logs(self, date: str = None) -> List[dict]:
        """Get chat logs for a specific date or today"""
        if date is None:
            date = datetime.now().strftime('%Y-%m-%d')
        log_file = CHAT_LOGS_DIR / f"{date}.jsonl"
        logs = []
        if log_file.exists():
            with open(log_file, "r", encoding="utf-8") as f:
                for line in f:
                    if line.strip():
                        logs.append(json.loads(line))
        return logs


# Singleton
_ai_service: Optional[AIAssistantService] = None


def get_ai_service() -> AIAssistantService:
    """Get AI assistant service singleton"""
    global _ai_service
    if _ai_service is None:
        _ai_service = AIAssistantService()
    return _ai_service
