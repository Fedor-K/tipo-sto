# -*- coding: utf-8 -*-
"""
VIN Decoder Service using Auto.dev API
Free tier: 1000 requests/month
"""
import re
import logging
from typing import Optional, Dict, Any
import httpx

from app.config import get_settings

logger = logging.getLogger(__name__)


class VINDecoderService:
    """VIN Decoder using Auto.dev API"""

    def __init__(self):
        self.settings = get_settings()
        self.api_key = self.settings.AUTODEV_API_KEY
        self.api_url = "https://api.auto.dev/vin"

    def is_valid_vin(self, vin: str) -> bool:
        """Check if VIN format is valid (17 alphanumeric, no I, O, Q)"""
        if not vin or len(vin) != 17:
            return False
        pattern = r'^[A-HJ-NPR-Z0-9]{17}$'
        return bool(re.match(pattern, vin.upper()))

    def extract_vin_from_text(self, text: str) -> Optional[str]:
        """Try to extract VIN from text message"""
        # Remove spaces and common separators
        clean_text = text.upper().replace(' ', '').replace('-', '').replace('_', '')

        # Look for 17-character alphanumeric sequences (excluding I, O, Q)
        pattern = r'[A-HJ-NPR-Z0-9]{17}'
        matches = re.findall(pattern, clean_text)

        for match in matches:
            if self.is_valid_vin(match):
                return match

        return None

    async def decode_vin(self, vin: str) -> Dict[str, Any]:
        """
        Decode VIN using Auto.dev API

        Returns:
            Dict with vehicle info or error
        """
        if not self.api_key:
            return {
                "success": False,
                "error": "VIN decoder API key not configured"
            }

        vin = vin.upper().strip()

        if not self.is_valid_vin(vin):
            return {
                "success": False,
                "error": f"Invalid VIN format: {vin}"
            }

        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                response = await client.get(
                    f"{self.api_url}/{vin}",
                    params={"apiKey": self.api_key}
                )

                if response.status_code == 200:
                    data = response.json()

                    # Extract relevant info
                    result = {
                        "success": True,
                        "vin": vin,
                        "make": data.get("make", ""),
                        "model": data.get("model", ""),
                        "year": data.get("vehicle", {}).get("year"),
                        "type": data.get("type", ""),
                        "origin": data.get("origin", ""),
                        "manufacturer": data.get("vehicle", {}).get("manufacturer", ""),
                        "valid": data.get("vinValid", False),
                    }

                    # Build summary string (без года - API часто ошибается)
                    parts = []
                    if result["make"]:
                        parts.append(result["make"])
                    if result["model"]:
                        parts.append(result["model"])
                    if result["type"]:
                        parts.append(f"({result['type']})")

                    result["summary"] = " ".join(parts) if parts else "Unknown vehicle"

                    logger.info(f"VIN decoded: {vin} -> {result['summary']}")
                    return result

                elif response.status_code == 402:
                    return {
                        "success": False,
                        "error": "VIN API limit reached (1000/month)"
                    }
                else:
                    return {
                        "success": False,
                        "error": f"VIN API error: {response.status_code}"
                    }

        except httpx.TimeoutException:
            return {
                "success": False,
                "error": "VIN decoder timeout"
            }
        except Exception as e:
            logger.error(f"VIN decode error: {e}")
            return {
                "success": False,
                "error": str(e)
            }

    def format_for_chat(self, decoded: Dict[str, Any]) -> str:
        """Format decoded VIN info for chat response"""
        if not decoded.get("success"):
            return ""

        lines = [f"🚗 **Расшифровка VIN {decoded['vin']}:**"]

        if decoded.get("make"):
            lines.append(f"• Марка: {decoded['make']}")
        if decoded.get("model"):
            lines.append(f"• Модель: {decoded['model']}")
        # Год не показываем - API часто ошибается для европейских авто
        if decoded.get("type"):
            lines.append(f"• Тип: {decoded['type']}")
        if decoded.get("origin"):
            lines.append(f"• Страна производства: {decoded['origin']}")

        return "\n".join(lines)


# Singleton
_vin_service: Optional[VINDecoderService] = None


def get_vin_service() -> VINDecoderService:
    """Get VIN decoder service singleton"""
    global _vin_service
    if _vin_service is None:
        _vin_service = VINDecoderService()
    return _vin_service
