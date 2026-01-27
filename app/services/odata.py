# -*- coding: utf-8 -*-
"""
OData Service for Rent1C API
"""
import base64
import json
import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List
from functools import lru_cache

import httpx

from app.config import get_settings, DEFAULT_GUIDS

logger = logging.getLogger(__name__)


class ODataError(Exception):
    """OData API Error"""
    def __init__(self, message: str, status_code: int = None, details: dict = None):
        self.message = message
        self.status_code = status_code
        self.details = details or {}
        super().__init__(self.message)


class ODataService:
    """Service for OData API interactions with Rent1C"""

    def __init__(self):
        self.settings = get_settings()
        self._cache: Dict[str, tuple] = {}  # key -> (data, expires_at)

    def _get_headers(self) -> dict:
        """Get authentication headers"""
        credentials = f"{self.settings.ODATA_USER}:{self.settings.ODATA_PASS}"
        encoded = base64.b64encode(credentials.encode("utf-8")).decode("ascii")
        return {
            "Authorization": f"Basic {encoded}",
            "Accept": "application/json",
            "Content-Type": "application/json; charset=utf-8",
        }

    def _get_cache(self, key: str) -> Optional[dict]:
        """Get cached value if not expired"""
        if key in self._cache:
            data, expires_at = self._cache[key]
            if datetime.now() < expires_at:
                return data
            del self._cache[key]
        return None

    def _set_cache(self, key: str, data: dict, ttl: int = None) -> None:
        """Set cache with TTL"""
        ttl = ttl or self.settings.CACHE_TTL
        self._cache[key] = (data, datetime.now() + timedelta(seconds=ttl))

    def clear_cache(self, prefix: str = None) -> None:
        """Clear cache entries"""
        if prefix:
            keys_to_remove = [k for k in self._cache if k.startswith(prefix)]
            for k in keys_to_remove:
                del self._cache[k]
        else:
            self._cache.clear()

    async def _request(
        self,
        method: str,
        endpoint: str,
        data: dict = None,
        timeout: float = None,
        retries: int = 3,
    ) -> dict:
        """Make HTTP request to OData API with retry logic"""
        url = f"{self.settings.ODATA_URL}/{endpoint}"
        timeout = timeout or self.settings.ODATA_TIMEOUT

        last_error = None
        for attempt in range(retries):
            try:
                async with httpx.AsyncClient(timeout=timeout, verify=False) as client:
                    if method == "GET":
                        response = await client.get(url, headers=self._get_headers())
                    elif method == "POST":
                        content = json.dumps(data, ensure_ascii=False).encode("utf-8")
                        response = await client.post(
                            url, headers=self._get_headers(), content=content
                        )
                    elif method == "PATCH":
                        content = json.dumps(data, ensure_ascii=False).encode("utf-8")
                        response = await client.patch(
                            url, headers=self._get_headers(), content=content
                        )
                    else:
                        raise ValueError(f"Unsupported method: {method}")

                    result = response.json()

                    # Check for OData error
                    if "odata.error" in result:
                        error_msg = result["odata.error"].get("message", {}).get("value", "Unknown error")
                        raise ODataError(error_msg, response.status_code, result)

                    return result

            except httpx.TimeoutException as e:
                last_error = ODataError(f"Request timeout (attempt {attempt + 1}/{retries})", details={"url": url})
                logger.warning(f"OData timeout: {url} (attempt {attempt + 1})")
            except httpx.HTTPStatusError as e:
                last_error = ODataError(f"HTTP error: {e.response.status_code}", e.response.status_code)
                logger.error(f"OData HTTP error: {e.response.status_code}")
                break  # Don't retry on HTTP errors
            except ODataError:
                raise
            except Exception as e:
                last_error = ODataError(str(e))
                logger.error(f"OData error: {e}")

        raise last_error

    async def get(self, endpoint: str, use_cache: bool = False, cache_ttl: int = None) -> dict:
        """GET request with optional caching"""
        if use_cache:
            cached = self._get_cache(endpoint)
            if cached:
                return cached

        result = await self._request("GET", endpoint)

        if use_cache and "error" not in result:
            self._set_cache(endpoint, result, cache_ttl)

        return result

    async def post(self, endpoint: str, data: dict) -> dict:
        """POST request"""
        return await self._request("POST", endpoint, data)

    async def patch(self, endpoint: str, data: dict) -> dict:
        """PATCH request"""
        return await self._request("PATCH", endpoint, data)

    # ==================== Client Operations ====================

    async def get_clients(
        self, search: str = None, limit: int = 50, offset: int = 0
    ) -> List[dict]:
        """Get list of clients (Контрагенты)"""
        filter_parts = []

        if search:
            # Capitalize for 1C search
            search_cap = " ".join(word.capitalize() for word in search.split())
            filter_parts.append(f"substringof('{search_cap}', Description)")

        filter_str = f"$filter={' and '.join(filter_parts)}&" if filter_parts else ""
        endpoint = (
            f"Catalog_Контрагенты?"
            f"{filter_str}"
            f"$top={limit}&$skip={offset}&"
            f"$orderby=Description&$format=json"
        )

        data = await self.get(endpoint)
        return data.get("value", [])

    async def get_client(self, ref: str) -> Optional[dict]:
        """Get client by Ref_Key"""
        endpoint = f"Catalog_Контрагенты(guid'{ref}')?$format=json"
        return await self.get(endpoint)

    async def find_client_by_phone(self, phone: str) -> Optional[dict]:
        """Find client by phone number"""
        # Normalize phone
        normalized = self._normalize_phone(phone)

        # Search in КонтактнаяИнформация
        # This is tricky in OData - we need to search differently
        # For now, get all clients and filter in Python
        # TODO: Optimize with proper OData filter

        clients = await self.get_clients(limit=1000)
        for client in clients:
            # Check if phone matches in contact info
            contact_info = client.get("КонтактнаяИнформация", "")
            if normalized in self._normalize_phone(contact_info):
                return client

        return None

    async def create_client(self, data: dict) -> dict:
        """Create new client"""
        payload = {
            "Description": data["name"],
            "ИНН": data.get("inn", ""),
            "Комментарий": data.get("comment", ""),
            # Add contact info if provided
        }
        return await self.post("Catalog_Контрагенты", payload)

    # ==================== Car Operations ====================

    async def get_cars(self, owner_ref: str = None, limit: int = 50) -> List[dict]:
        """Get list of cars (Автомобили)"""
        filter_str = ""
        if owner_ref:
            filter_str = f"$filter=Владелец_Key eq guid'{owner_ref}'&"

        endpoint = f"Catalog_Автомобили?{filter_str}$top={limit}&$format=json"
        data = await self.get(endpoint)
        return data.get("value", [])

    async def get_car(self, ref: str) -> Optional[dict]:
        """Get car by Ref_Key"""
        endpoint = f"Catalog_Автомобили(guid'{ref}')?$format=json"
        return await self.get(endpoint)

    async def find_car_by_plate(self, plate: str) -> Optional[dict]:
        """Find car by license plate (ГосНомер)"""
        # Normalize plate (remove spaces, uppercase)
        normalized = plate.upper().replace(" ", "")

        # Convert cyrillic to latin for search
        plate_latin = self._cyrillic_to_latin(normalized)

        endpoint = (
            f"Catalog_Автомобили?"
            f"$filter=substringof('{plate_latin}', ГосНомер)&"
            f"$top=10&$format=json"
        )
        data = await self.get(endpoint)
        cars = data.get("value", [])

        if cars:
            return cars[0]
        return None

    # ==================== Order Operations ====================

    async def get_orders(
        self,
        client_ref: str = None,
        status_ref: str = None,
        date_from: str = None,
        date_to: str = None,
        limit: int = 50,
    ) -> List[dict]:
        """Get list of orders (ЗаказНаряд)"""
        filter_parts = []

        if client_ref:
            filter_parts.append(f"Контрагент_Key eq guid'{client_ref}'")
        if status_ref:
            filter_parts.append(f"Состояние_Key eq guid'{status_ref}'")
        if date_from:
            filter_parts.append(f"Date ge datetime'{date_from}T00:00:00'")
        if date_to:
            filter_parts.append(f"Date le datetime'{date_to}T23:59:59'")

        filter_str = f"$filter={' and '.join(filter_parts)}&" if filter_parts else ""
        endpoint = (
            f"Document_ЗаказНаряд?"
            f"{filter_str}"
            f"$top={limit}&$orderby=Date desc&$format=json"
        )

        data = await self.get(endpoint)
        return data.get("value", [])

    async def get_order(self, ref: str) -> Optional[dict]:
        """Get order by Ref_Key with expanded data"""
        endpoint = f"Document_ЗаказНаряд(guid'{ref}')?$format=json"
        order = await self.get(endpoint)

        if order:
            # Get tabular parts
            order["_works"] = await self._get_order_works(ref)
            order["_parts"] = await self._get_order_parts(ref)
            order["_cars"] = await self._get_order_cars(ref)

        return order

    async def _get_order_works(self, order_ref: str) -> List[dict]:
        """Get order works (Автоработы)"""
        endpoint = f"Document_ЗаказНаряд(guid'{order_ref}')/Автоработы?$format=json"
        data = await self.get(endpoint)
        return data.get("value", [])

    async def _get_order_parts(self, order_ref: str) -> List[dict]:
        """Get order parts (Товары)"""
        endpoint = f"Document_ЗаказНаряд(guid'{order_ref}')/Товары?$format=json"
        data = await self.get(endpoint)
        return data.get("value", [])

    async def _get_order_cars(self, order_ref: str) -> List[dict]:
        """Get order cars (Автомобили)"""
        endpoint = f"Document_ЗаказНаряд(guid'{order_ref}')/Автомобили?$format=json"
        data = await self.get(endpoint)
        return data.get("value", [])

    async def create_repair_request(self, data: dict) -> dict:
        """Create repair request (ЗаявкаНаРемонт)

        According to CLAUDE.md, the document requires specific structure:
        - Header with required fields
        - ПричиныОбращения tabular part (links works to reason)
        - Автоработы tabular part with Авторабота_Key
        """
        now = datetime.now()

        # Required header fields
        payload = {
            "Date": data.get("date", now.isoformat()),
            "Posted": True,
            "Организация_Key": DEFAULT_GUIDS["org"],
            "ПодразделениеКомпании_Key": DEFAULT_GUIDS["division"],
            "Заказчик_Key": data["client_ref"],
            "Контрагент_Key": data["client_ref"],
            "ВидРемонта_Key": DEFAULT_GUIDS["repair_type"],
            "Цех_Key": DEFAULT_GUIDS["workshop"],
            "ТипЦен_Key": DEFAULT_GUIDS["price_type"],
            "ТипЦенРабот_Key": DEFAULT_GUIDS["price_type"],
            "ВалютаДокумента_Key": DEFAULT_GUIDS["currency"],
            "КурсДокумента": 1,
            "Автор_Key": DEFAULT_GUIDS["author"],
            "Состояние": "НеУказано",
            "ОписаниеПричиныОбращения": data.get("comment", ""),
            "ДатаНачала": now.replace(hour=9, minute=0, second=0).isoformat(),
            "ДатаОкончания": now.replace(hour=18, minute=0, second=0).isoformat(),
        }

        # Add car if provided
        if data.get("car_ref"):
            payload["Автомобиль_Key"] = data["car_ref"]

        # Add ПричиныОбращения (required for linking works)
        payload["ПричиныОбращения"] = [{
            "LineNumber": "1",
            "ИдентификаторПричиныОбращения": "1",
            "ПричинаОбращения_Key": "7d9f8933-1a7f-11e6-bee5-20689d8f1e0d",  # Ремонт
            "ПричинаОбращенияСодержание": data.get("comment", "Из DVI осмотра"),
            "ВидРемонтаПричиныОбращения_Key": DEFAULT_GUIDS["repair_type"],
        }]

        # Add works if provided
        if data.get("works"):
            autoworks = []
            for i, w in enumerate(data["works"], start=1):
                autoworks.append({
                    "LineNumber": str(i),
                    "Авторабота_Key": w["work_ref"],
                    "ИдентификаторРаботы": str(i),
                    "ИдентификаторПричиныОбращения": "1",
                    "Количество": w.get("quantity", 1),
                    "Коэффициент": 0,
                    "Цена": w.get("price", 0),
                    "Сумма": w.get("price", 0) * w.get("quantity", 1),
                    "СуммаВсего": w.get("price", 0) * w.get("quantity", 1),
                    "СпособРасчетаСтоимостиРаботы": "ФиксированнойСуммой",
                })
            payload["Автоработы"] = autoworks

        return await self.post("Document_ЗаявкаНаРемонт", payload)

    # ==================== Reference Data ====================

    async def get_order_statuses(self) -> List[dict]:
        """Get order statuses (ВидыСостоянийЗаказНарядов)"""
        endpoint = "Catalog_ВидыСостоянийЗаказНарядов?$format=json"
        data = await self.get(endpoint, use_cache=True, cache_ttl=3600)
        return data.get("value", [])

    async def get_works_catalog(self, search: str = None, limit: int = 100) -> List[dict]:
        """Get works catalog (Автоработы)"""
        filter_str = ""
        if search:
            filter_str = f"$filter=substringof('{search}', Description)&"

        endpoint = f"Catalog_Автоработы?{filter_str}$top={limit}&$format=json"
        data = await self.get(endpoint, use_cache=True)
        return data.get("value", [])

    async def get_employees(self) -> List[dict]:
        """Get employees (Сотрудники)"""
        endpoint = "Catalog_Сотрудники?$format=json"
        data = await self.get(endpoint, use_cache=True, cache_ttl=3600)
        return data.get("value", [])

    # ==================== Utility Methods ====================

    @staticmethod
    def _normalize_phone(phone: str) -> str:
        """Normalize phone number for comparison"""
        if not phone:
            return ""
        # Keep only digits
        digits = "".join(c for c in phone if c.isdigit())
        # Normalize to 10 digits (remove country code)
        if len(digits) == 11 and digits.startswith("7"):
            digits = digits[1:]
        elif len(digits) == 11 and digits.startswith("8"):
            digits = digits[1:]
        return digits

    @staticmethod
    def _cyrillic_to_latin(text: str) -> str:
        """Convert cyrillic letters to latin (for license plates)"""
        mapping = {
            "А": "A", "В": "B", "Е": "E", "К": "K", "М": "M",
            "Н": "H", "О": "O", "Р": "P", "С": "C", "Т": "T",
            "У": "Y", "Х": "X",
        }
        result = ""
        for char in text.upper():
            result += mapping.get(char, char)
        return result


# Singleton instance
_odata_service: Optional[ODataService] = None


def get_odata_service() -> ODataService:
    """Get OData service singleton"""
    global _odata_service
    if _odata_service is None:
        _odata_service = ODataService()
    return _odata_service
