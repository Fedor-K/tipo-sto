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

import re

from app.config import get_settings
from app.services.vin_decoder import get_vin_service
from app.services.parts_catalog import get_parts_service

# Chat logs directory
CHAT_LOGS_DIR = Path(__file__).parent.parent.parent / "data" / "chat_logs"
CHAT_LOGS_DIR.mkdir(parents=True, exist_ok=True)

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """Ты опытный автомеханик СТО. Отвечай ТОЛЬКО про автомобили. Давай ПОЛНЫЕ РАЗВЁРНУТЫЕ ответы.

## СТИЛЬ ОТВЕТОВ

ВСЕГДА давай КОНКРЕТНЫЕ рекомендации:
- Точные спецификации жидкостей
- Артикулы деталей где возможно
- Пошаговые инструкции
- Что проверить В ПЕРВУЮ ОЧЕРЕДЬ

НЕ ДАВАЙ размытых ответов типа:
- "обратитесь к специалисту"
- "посмотрите в мануале"
- "зависит от многих факторов"

ВМЕСТО ЭТОГО:
- Дай конкретный ответ
- Если есть варианты - перечисли ВСЕ подходящие
- Укажи что НЕЛЬЗЯ использовать

## СПЕЦИФИКАЦИИ ТРАНСМИССИОННЫХ ЖИДКОСТЕЙ

### АКПП по производителям (СТРОГО соблюдать!)

**Nissan/Infiniti (включая FX35, QX, Patrol):**
- Оригинал: Nissan Matic S, Matic J, Matic D
- Аналоги: Motul Multi ATF, Idemitsu ATF
- ⛔ НЕ ЛИТЬ: SP-IV (Hyundai), CVT-жидкости!

**Toyota/Lexus:**
- Оригинал: Toyota ATF Type T-IV, ATF WS
- Аналоги: Aisin ATF AFW+, Idemitsu ATF Type-TLS

**Hyundai/Kia:**
- Оригинал: Hyundai ATF SP-III, SP-IV (только они!)
- Аналоги: ZIC ATF SP-III, ZIC ATF SP-IV

**Honda/Acura:**
- Оригинал: Honda ATF DW-1, ATF-Z1
- ⛔ ТОЛЬКО оригинал или Idemitsu ATF Type-H!

**VAG (VW, Audi, Skoda, Seat):**
- DSG 6: G 052 182 A2 (зелёное)
- DSG 7: G 052 529 A2
- Tiptronic: G 055 025 A2

**BMW/Mini:**
- ZF 6HP/8HP: Shell M-1375.4, Fuchs Titan ATF 4134

**Mercedes:**
- 722.6: MB 236.14
- 722.9 (7G-Tronic): MB 236.15

### CVT (вариаторы) - ОТДЕЛЬНАЯ КАТЕГОРИЯ!
- Nissan/Infiniti CVT: NS-2, NS-3
- Toyota CVT: CVT Fluid TC, CVT Fluid FE
- Honda CVT: HMMF, HCF-2
- ⛔ НЕЛЬЗЯ лить ATF в CVT и наоборот!

### Конкретные рекомендации Motul/ZIC:
**Motul:**
- Multi ATF - универсал для классических АКПП
- Multi DCTF - для DSG/PowerShift
- CVTF - для вариаторов

**ZIC:**
- ATF Multi - для Dexron III/Mercon
- ATF SP-III, SP-IV - ТОЛЬКО Hyundai/Kia!
- CVT Multi - для вариаторов

## ТИПИЧНЫЕ ПРОБЛЕМЫ ПО МОДЕЛЯМ (KNOWN ISSUES)

### Fiat Ducato / Peugeot Boxer / Citroen Jumper
**Тугое переключение передач:**
- Причина в 90% случаев: НЕ тросы, а МЕХАНИЗМ ВЫБОРА ПЕРЕДАЧ на КПП
- Закисают втулки и шарниры кулисы на коробке
- Решение: снять механизм, разобрать, смазать/заменить втулки
- Артикул механизма: 55233426, 2444CG
- После замены тросов ОБЯЗАТЕЛЬНО проверить механизм на КПП!

### Range Rover Evoque 2.2 TD4 / SD4
**Глушение EGR:**
- Физическая заглушка: пластина 3мм сталь между клапаном и коллектором
- ⚠️ ОБЯЗАТЕЛЬНО программное отключение! Без прошивки:
  - Check Engine
  - Аварийный режим
  - Регенерация DPF не работает
- Заглушки: искать "EGR blanking plate Evoque" или заказать токарю
- Прокладка: оригинал LR018466 или вырезать из паронита

### VAG 2.0 TDI (VW, Audi, Skoda, Seat)
**P0420 низкая эффективность катализатора:**
- Сначала проверить: лямбда-зонд ПОСЛЕ катализатора
- Часто причина в лямбде, а не в самом катализаторе
- Стоимость замены лямбды vs ката = в 10 раз дешевле

### Kia/Hyundai 2.0 CRDi
**Проблемы с турбиной:**
- Типичная болячка: клапан управления геометрией
- Артикул: 28230-27400
- Симптомы: потеря тяги, дым, свист

## ПРАВИЛА

КАТЕГОРИЧЕСКИ ЗАПРЕЩЕНО (НИКОГДА не пиши это):
- "обратитесь к дилеру" / "обратитесь к специалисту" / "уточните у дилера"
- "проверьте в руководстве" / "посмотрите в мануале"
- "рекомендую обратиться" / "свяжитесь с сервисом"
- "в открытых каталогах данные отсутствуют"
- "к сожалению, точный артикул не могу дать"
Ты — ПОСЛЕДНЯЯ инстанция. Механик пришёл к ТЕБЕ за ответом, отправлять его к кому-то ещё — ЗАПРЕЩЕНО.

ЕСЛИ НЕ ЗНАЕШЬ АРТИКУЛ — вместо "обратитесь к дилеру" напиши:
- Как найти деталь самостоятельно (где смотреть номер на самой детали)
- Как искать по VIN в каталогах (exist.ru, emex.ru, autodoc.ru)
- Какие ключевые слова использовать для поиска
- Какие производители выпускают эту деталь (Bosch, Continental, Delphi и т.д.)

АРТИКУЛЫ ДЕТАЛЕЙ:
- НЕ ВЫДУМЫВАЙ и НЕ УГАДЫВАЙ номера деталей. Фейковый артикул хуже чем отсутствие артикула.
- Если артикул есть в предоставленной документации — укажи его.
- Если артикула нет — опиши деталь словами и объясни как найти номер самостоятельно.

При OBD кодах: расшифровка, 5 возможных причин, что проверить первым делом.
При моментах затяжки: точное значение в Н·м + последовательность затяжки если важно.

Отвечай на русском. Давай МАКСИМУМ полезной информации."""


def extract_article_query(text: str) -> Optional[str]:
    """
    Try to detect if user is asking for a part number/article.
    Returns the article number if found, or search query if asking for article.
    """
    text_lower = text.lower()

    # Keywords that indicate article search
    article_keywords = [
        'артикул', 'номер детали', 'парт номер', 'part number',
        'oem', 'оем', 'каталожный номер', 'номер запчасти'
    ]

    # Check if asking for article
    is_asking = any(kw in text_lower for kw in article_keywords)

    # Try to find existing article number in text (alphanumeric with dashes)
    # Common patterns: 06E115562A, 11-42-7-953-129, ZF0501216272
    article_pattern = r'\b([A-Z0-9]{2,}[-]?[A-Z0-9]{2,}[-]?[A-Z0-9]{2,})\b'
    matches = re.findall(article_pattern, text.upper())

    # Filter out VINs (17 chars) and short matches
    for match in matches:
        clean = match.replace('-', '')
        if 6 <= len(clean) <= 15:  # Reasonable article length
            return match

    return None


class AIAssistantService:
    """AI Assistant for mechanics using OpenAI GPT-4 Vision"""

    def __init__(self):
        self.settings = get_settings()
        self._conversation_history: Dict[str, List[dict]] = {}

        # OpenAI credentials (always needed for vision fallback)
        self.openai_api_key = self.settings.OPENAI_API_KEY
        self.openai_api_url = "http://198.12.73.168:8080/v1/chat/completions"
        self.openai_model = "gpt-4o-mini"

        # Select LLM provider for text
        self.provider = self.settings.LLM_PROVIDER
        if self.provider == "deepseek" and self.settings.DEEPSEEK_API_KEY:
            self.api_key = self.settings.DEEPSEEK_API_KEY
            self.api_url = self.settings.DEEPSEEK_API_URL
            self.model = self.settings.DEEPSEEK_MODEL
            logger.info(f"LLM provider: DeepSeek ({self.model}), key: {self.api_key[:10]}...")
            logger.info(f"Vision fallback: OpenAI ({self.openai_model})")
        elif self.provider == "zai" and self.settings.ZAI_API_KEY:
            self.api_key = self.settings.ZAI_API_KEY
            self.api_url = self.settings.ZAI_API_URL
            self.model = self.settings.ZAI_MODEL
            logger.info(f"LLM provider: Z.ai ({self.model}), key: {self.api_key[:10]}...")
        else:
            self.api_key = self.settings.OPENAI_API_KEY
            self.api_url = self.openai_api_url
            self.model = self.openai_model
            self.provider = "openai"
            if self.api_key:
                logger.info(f"LLM provider: OpenAI ({self.model}), key: {self.api_key[:10]}...")
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

        # Try to detect and search article number for crosses/analogs
        parts_info = ""
        detected_article = extract_article_query(message)
        if detected_article and not detected_vin:  # Don't confuse VIN with article
            parts_service = get_parts_service()
            if parts_service.api_key:  # Only if API key configured
                parts_result = await parts_service.get_crosses(detected_article)
                if parts_result.get("success") and parts_result.get("count", 0) > 0:
                    parts_info = parts_service.format_crosses_for_chat(parts_result)
                    logger.info(f"Crosses found for {detected_article}: {parts_result.get('count')} results")

        # Build system prompt with car context if provided
        system = SYSTEM_PROMPT
        if car_context:
            system += f"\n\nКонтекст текущего автомобиля:\n{car_context}"

        # RAG: поиск в базе знаний (только если в вопросе есть марка/модель авто)
        rag_sources = []
        rag_results = []
        has_car_mention = self._has_car_keywords(message)
        if has_car_mention:
            try:
                from app.services.knowledge_base import get_kb_service
                kb = get_kb_service()
                rag_results = await kb.search(message, top_k=3)
                logger.info(f"RAG search returned {len(rag_results)} results for: {message[:80]}")
                if rag_results:
                    rag_context = self._format_rag_context(rag_results)
                    system += "\n\n## КОНТЕКСТ ИЗ БАЗЫ ЗНАНИЙ\n\n" \
                        "СТРОГИЕ ПРАВИЛА работы с документацией:\n" \
                        "1. Ссылку (стр. N) ставь ТОЛЬКО если факт РЕАЛЬНО написан на этой странице в тексте ниже.\n" \
                        "2. НЕ ВЫДУМЫВАЙ артикулы и номера деталей. Указывай артикул только если он есть в тексте ниже.\n" \
                        "3. Если в документации нет ответа на вопрос — отвечай из своих знаний БЕЗ ссылок на страницы.\n" \
                        "4. Чётко разделяй: что из документации (со ссылкой), что из общих знаний (без ссылки).\n" \
                        "5. ЦИТАТЫ: Когда используешь информацию из документации, ОБЯЗАТЕЛЬНО вставляй прямую цитату в формате markdown-цитаты с указанием источника:\n" \
                        "   > Текст цитаты из документации\n" \
                        "   > — *Название документа, стр. N*\n" \
                        "   Затем давай свой комментарий/пояснение обычным текстом.\n" \
                        "6. Каждый блок ответа, основанный на документации, должен содержать цитату с названием документа и номером страницы. НЕ добавляй общий список источников в конце ответа.\n" \
                        "7. НЕ ссылайся на страницы, из которых ты НЕ цитируешь конкретный текст.\n\n" \
                        "Документация:\n\n" + rag_context
                    rag_sources = list({r["filename"] for r in rag_results})
                    logger.info(f"RAG context injected: {len(rag_context)} chars, scores: {[r['score'] for r in rag_results]}")
            except Exception as e:
                logger.error(f"RAG search failed: {e}", exc_info=True)
        else:
            logger.info(f"RAG skipped: no car brand/model in message: {message[:80]}")

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

        # Switch to OpenAI for vision (image) requests
        has_image = bool(image_base64 or image_url)
        if has_image and self.provider != "openai":
            req_api_url = self.openai_api_url
            req_api_key = self.openai_api_key
            req_model = self.openai_model
            logger.info(f"Vision request: switching to OpenAI ({req_model})")
        else:
            req_api_url = self.api_url
            req_api_key = self.api_key
            req_model = self.model

        req_headers = {
            "Authorization": f"Bearer {req_api_key}",
            "Content-Type": "application/json",
        }

        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(
                    req_api_url,
                    headers=req_headers,
                    json={
                        "model": req_model,
                        "messages": messages,
                        "max_tokens": 4096,
                        "temperature": 0.3,
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
                assistant_message = data["choices"][0]["message"]["content"] or ""

                # Prepend VIN info if decoded
                if vin_info:
                    assistant_message = f"{vin_info}\n\n{assistant_message}"

                # Prepend parts info if found
                if parts_info:
                    assistant_message = f"{parts_info}\n\n{assistant_message}"

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

    async def chat_stream(
        self,
        message: str,
        session_id: str = "default",
        car_context: Optional[str] = None,
        image_base64: Optional[str] = None,
    ):
        """
        Stream chat response token by token.
        Yields chunks of text as they arrive from OpenAI.
        """
        if not self.api_key:
            yield "❌ API ключ не настроен."
            return

        # Build system prompt
        system = SYSTEM_PROMPT
        if car_context:
            system += f"\n\nКонтекст: {car_context}"

        # RAG: поиск в базе знаний (только если в вопросе есть марка/модель авто)
        rag_sources = []
        has_car_mention = self._has_car_keywords(message)
        if has_car_mention:
            try:
                from app.services.knowledge_base import get_kb_service
                kb = get_kb_service()
                rag_results = await kb.search(message, top_k=3)
                logger.info(f"RAG stream search returned {len(rag_results)} results for: {message[:80]}")
                if rag_results:
                    rag_context = self._format_rag_context(rag_results)
                    system += "\n\n## КОНТЕКСТ ИЗ БАЗЫ ЗНАНИЙ\n\n" \
                        "СТРОГИЕ ПРАВИЛА работы с документацией:\n" \
                        "1. Ссылку (стр. N) ставь ТОЛЬКО если факт РЕАЛЬНО написан на этой странице в тексте ниже.\n" \
                        "2. НЕ ВЫДУМЫВАЙ артикулы и номера деталей. Указывай артикул только если он есть в тексте ниже.\n" \
                        "3. Если в документации нет ответа на вопрос — отвечай из своих знаний БЕЗ ссылок на страницы.\n" \
                        "4. Чётко разделяй: что из документации (со ссылкой), что из общих знаний (без ссылки).\n" \
                        "5. ЦИТАТЫ: Когда используешь информацию из документации, ОБЯЗАТЕЛЬНО вставляй прямую цитату в формате markdown-цитаты с указанием источника:\n" \
                        "   > Текст цитаты из документации\n" \
                        "   > — *Название документа, стр. N*\n" \
                        "   Затем давай свой комментарий/пояснение обычным текстом.\n" \
                        "6. Каждый блок ответа, основанный на документации, должен содержать цитату с названием документа и номером страницы. НЕ добавляй общий список источников в конце ответа.\n" \
                        "7. НЕ ссылайся на страницы, из которых ты НЕ цитируешь конкретный текст.\n\n" \
                        "Документация:\n\n" + rag_context
                    rag_sources = list({r["filename"] for r in rag_results})
                    logger.info(f"RAG stream context injected: {len(rag_context)} chars")
            except Exception as e:
                logger.error(f"RAG stream search failed: {e}", exc_info=True)
        else:
            logger.info(f"RAG stream skipped: no car brand/model in message: {message[:80]}")

        # Get or create conversation history
        if session_id not in self._conversation_history:
            self._conversation_history[session_id] = []
        history = self._conversation_history[session_id]

        # Build message content
        if image_base64:
            content = [
                {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{image_base64}", "detail": "high"}},
                {"type": "text", "text": message}
            ]
        else:
            content = message

        # Add user message to history
        history.append({"role": "user", "content": content})
        if len(history) > 10:
            history = history[-10:]
            self._conversation_history[session_id] = history

        messages = [{"role": "system", "content": system}] + history

        # Switch to OpenAI for vision (image) requests
        has_image = bool(image_base64)
        if has_image and self.provider != "openai":
            req_api_url = self.openai_api_url
            req_api_key = self.openai_api_key
            req_model = self.openai_model
            logger.info(f"Vision stream: switching to OpenAI ({req_model})")
        else:
            req_api_url = self.api_url
            req_api_key = self.api_key
            req_model = self.model

        req_headers = {
            "Authorization": f"Bearer {req_api_key}",
            "Content-Type": "application/json",
        }

        full_response = ""
        try:
            async with httpx.AsyncClient(timeout=120.0) as client:
                async with client.stream(
                    "POST",
                    req_api_url,
                    headers=req_headers,
                    json={
                        "model": req_model,
                        "messages": messages,
                        "max_tokens": 4096,
                        "temperature": 0.3,
                        "stream": True,
                    },
                ) as response:
                    if response.status_code != 200:
                        yield f"❌ Ошибка API: {response.status_code}"
                        return

                    async for line in response.aiter_lines():
                        if line.startswith("data: "):
                            data = line[6:]
                            if data == "[DONE]":
                                break
                            try:
                                chunk = json.loads(data)
                                delta = chunk.get("choices", [{}])[0].get("delta", {})
                                text = delta.get("content", "")
                                if text:
                                    full_response += text
                                    yield text
                            except json.JSONDecodeError:
                                continue

            # Save to history and log
            history.append({"role": "assistant", "content": full_response})
            self._log_chat(session_id, message, full_response, bool(image_base64))

        except Exception as e:
            logger.error(f"Stream error: {e}")
            yield f"❌ Ошибка: {str(e)}"

    @staticmethod
    def _has_car_keywords(text: str) -> bool:
        """Check if text mentions any car brand or model."""
        text_lower = text.lower()
        keywords = [
            # Latin brands
            "voyah", "hyundai", "kia", "toyota", "bmw", "mercedes", "audi",
            "volkswagen", "nissan", "honda", "ford", "chevrolet", "geely",
            "changan", "haval", "zeekr", "lada", "vaz", "lexus", "infiniti",
            "subaru", "mazda", "mitsubishi", "peugeot", "citroen", "renault",
            "fiat", "opel", "skoda", "seat", "volvo", "jaguar", "land rover",
            "range rover", "porsche", "jeep", "dodge", "chrysler", "cadillac",
            "suzuki", "dacia", "ssangyong", "chery", "byd", "exeed",
            "mini", "smart", "alfa romeo",
            # Cyrillic brands
            "воях", "хендай", "хёндай", "хундай", "киа", "тойота", "бмв",
            "мерседес", "ауди", "фольксваген", "ниссан", "хонда", "форд",
            "шевроле", "джили", "чанган", "хавал", "зикр", "лада", "ваз",
            "лексус", "инфинити", "субару", "мазда", "митсубиши",
            "пежо", "ситроен", "рено", "фиат", "опель", "шкода",
            "вольво", "ягуар", "ленд ровер", "рендж ровер", "порше",
            "джип", "додж", "крайслер", "кадиллак", "сузуки", "чери",
            # Popular models (cyrillic)
            "гетц", "солярис", "туксон", "крета", "санта",
            "рио", "сид", "спортейдж", "камри", "королла", "рав4",
            "дукато", "боксер", "джампер", "эвок",
            # Popular models (latin)
            "getz", "solaris", "tucson", "creta", "sportage",
            "camry", "corolla", "rav4", "ducato", "boxer", "jumper", "evoque",
        ]
        return any(kw in text_lower for kw in keywords)

    @staticmethod
    def _format_rag_context(results: list) -> str:
        """Format RAG search results for injection into system prompt.

        Embeds page numbers directly into the text so GPT naturally cites them.
        """
        parts = []
        for i, r in enumerate(results, 1):
            source = r.get("filename", "")
            score = r.get("score", 0)
            pages = r.get("pages", "")
            text = r.get("text", "")
            page_label = f" [стр. {pages}]" if pages else ""
            # Put page reference both in header and as a reminder at the end
            header = f"[Источник {i}: {source}{page_label}, релевантность {score:.0%}]"
            if pages:
                parts.append(f"{header}\n{text}\n(Источник: стр. {pages})")
            else:
                parts.append(f"{header}\n{text}")
        return "\n\n".join(parts)

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
