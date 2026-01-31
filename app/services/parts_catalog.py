# -*- coding: utf-8 -*-
"""
Auto Parts Catalog Service
Uses PartsAPI.ru - Russian auto parts database
Free demo keys available, ~1200 RUB/month for production
"""
import logging
from typing import Optional, Dict, Any, List
import httpx

from app.config import get_settings

logger = logging.getLogger(__name__)


class PartsCatalogService:
    """Auto Parts Catalog using PartsAPI.ru"""

    def __init__(self):
        self.settings = get_settings()
        self.api_key = self.settings.PARTSAPI_KEY
        # Base URL for PartsAPI.ru (need to confirm after registration)
        self.api_url = "https://api.partsapi.ru"
        # Cache for responses (simple in-memory)
        self._cache: Dict[str, Any] = {}

    def _get_params(self, **kwargs) -> dict:
        """Add API key to params"""
        params = {"key": self.api_key}
        params.update(kwargs)
        return params

    async def get_crosses(self, article_number: str) -> Dict[str, Any]:
        """
        Search for part crosses/analogs by article number
        Uses CROSSBASE.RU database (~428 million crosses)

        Args:
            article_number: Part number (OEM or aftermarket)

        Returns:
            Dict with crosses info or error
        """
        if not self.api_key:
            return {
                "success": False,
                "error": "PartsAPI key not configured (PARTSAPI_KEY)"
            }

        # Normalize article number
        article_clean = article_number.upper().replace(" ", "").replace("-", "")

        # Check cache first
        cache_key = f"crosses:{article_clean}"
        if cache_key in self._cache:
            logger.info(f"Parts cache hit: {article_number}")
            return self._cache[cache_key]

        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                response = await client.get(
                    f"{self.api_url}/getCrosses",
                    params=self._get_params(number=article_clean)
                )

                if response.status_code == 200:
                    data = response.json()

                    # Check for API errors
                    if isinstance(data, dict) and data.get("error"):
                        return {
                            "success": False,
                            "error": data.get("error")
                        }

                    crosses = data if isinstance(data, list) else data.get("data", [])
                    result = {
                        "success": True,
                        "article": article_number,
                        "crosses": crosses,
                        "count": len(crosses)
                    }
                    # Cache successful response
                    self._cache[cache_key] = result
                    logger.info(f"Crosses found for {article_number}: {result['count']}")
                    return result

                elif response.status_code == 401:
                    return {
                        "success": False,
                        "error": "Invalid PartsAPI key"
                    }
                elif response.status_code == 402:
                    return {
                        "success": False,
                        "error": "PartsAPI subscription expired"
                    }
                else:
                    return {
                        "success": False,
                        "error": f"API error: {response.status_code}"
                    }

        except httpx.TimeoutException:
            return {"success": False, "error": "Request timeout"}
        except Exception as e:
            logger.error(f"Parts catalog error: {e}")
            return {"success": False, "error": str(e)}

    async def search_parts(self, query: str, lang: str = "ru") -> Dict[str, Any]:
        """
        Search parts by article number or partial number

        Args:
            query: Part number or partial (max 25 chars)
            lang: Language code (ru, en, de, etc.)

        Returns:
            Dict with parts info
        """
        if not self.api_key:
            return {
                "success": False,
                "error": "PartsAPI key not configured"
            }

        cache_key = f"search:{query.upper()}"
        if cache_key in self._cache:
            return self._cache[cache_key]

        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                response = await client.get(
                    f"{self.api_url}/searchParts",
                    params=self._get_params(query=query[:25], lang=lang)
                )

                if response.status_code == 200:
                    data = response.json()
                    parts = data if isinstance(data, list) else data.get("data", [])
                    result = {
                        "success": True,
                        "query": query,
                        "parts": parts,
                        "count": len(parts)
                    }
                    self._cache[cache_key] = result
                    return result
                else:
                    return {
                        "success": False,
                        "error": f"API error: {response.status_code}"
                    }

        except Exception as e:
            logger.error(f"Search parts error: {e}")
            return {"success": False, "error": str(e)}

    async def get_part_name(self, brand: str, number: str) -> Dict[str, Any]:
        """
        Get part name by brand and number

        Args:
            brand: Manufacturer brand name
            number: Part article number

        Returns:
            Dict with part names
        """
        if not self.api_key:
            return {"success": False, "error": "PartsAPI key not configured"}

        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                response = await client.get(
                    f"{self.api_url}/getPartnameByBrandNumber",
                    params=self._get_params(brand=brand, number=number)
                )

                if response.status_code == 200:
                    data = response.json()
                    return {
                        "success": True,
                        "brand": brand,
                        "number": number,
                        "names": data if isinstance(data, list) else [data]
                    }
                else:
                    return {"success": False, "error": f"API error: {response.status_code}"}

        except Exception as e:
            logger.error(f"Get part name error: {e}")
            return {"success": False, "error": str(e)}

    def format_crosses_for_chat(self, result: Dict[str, Any]) -> str:
        """Format crosses search result for chat response"""
        if not result.get("success"):
            return ""

        crosses = result.get("crosses", [])
        if not crosses:
            return f"Аналогов для артикула {result.get('article', '')} не найдено."

        lines = [f"🔄 **Аналоги для {result.get('article', '')}:**\n"]

        # Group by brand
        by_brand: Dict[str, List[str]] = {}
        for cross in crosses[:20]:  # Max 20 results
            brand = cross.get("crossBrand", cross.get("brand", "?"))
            number = cross.get("crossNumber", cross.get("number", "?"))
            if brand not in by_brand:
                by_brand[brand] = []
            by_brand[brand].append(number)

        for brand, numbers in list(by_brand.items())[:10]:  # Max 10 brands
            nums = ", ".join(numbers[:3])  # Max 3 numbers per brand
            if len(numbers) > 3:
                nums += f" (+{len(numbers)-3})"
            lines.append(f"• **{brand}:** {nums}")

        if len(crosses) > 20:
            lines.append(f"\n...и ещё {len(crosses) - 20} аналогов")

        return "\n".join(lines)

    def format_parts_for_chat(self, result: Dict[str, Any]) -> str:
        """Format parts search result for chat response"""
        if not result.get("success"):
            return ""

        parts = result.get("parts", [])
        if not parts:
            return f"По запросу '{result.get('query', '')}' ничего не найдено."

        lines = [f"🔧 **Найдено по запросу '{result.get('query', '')}':**\n"]

        for i, part in enumerate(parts[:5]):  # Max 5 results
            brand = part.get("BrandName", part.get("brand", ""))
            name = part.get("ArticleName", part.get("name", ""))
            number = part.get("ArticleNo", part.get("number", ""))

            lines.append(f"{i+1}. **{brand}** {number}")
            if name:
                lines.append(f"   {name}")

        if len(parts) > 5:
            lines.append(f"\n...и ещё {len(parts) - 5} результатов")

        return "\n".join(lines)


# Singleton
_parts_service: Optional[PartsCatalogService] = None


def get_parts_service() -> PartsCatalogService:
    """Get parts catalog service singleton"""
    global _parts_service
    if _parts_service is None:
        _parts_service = PartsCatalogService()
    return _parts_service
