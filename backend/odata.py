"""OData client for Rent1C API"""
import base64
import json
from datetime import datetime, timedelta
from typing import Optional

import httpx

from .config import settings


# Simple in-memory cache
_cache: dict = {}


def get_cache(key: str) -> Optional[dict]:
    """Get cached value if not expired"""
    if key in _cache:
        data, expires = _cache[key]
        if datetime.now() < expires:
            return data
    return None


def set_cache(key: str, data: dict) -> None:
    """Set cache with TTL"""
    _cache[key] = (data, datetime.now() + timedelta(seconds=settings.CACHE_TTL))


def clear_cache(prefix: str = None) -> None:
    """Clear cache entries matching prefix or all"""
    global _cache
    if prefix:
        keys_to_remove = [k for k in _cache if k.startswith(prefix)]
        for k in keys_to_remove:
            _cache.pop(k, None)
    else:
        _cache.clear()


def get_auth_headers() -> dict:
    """Get basic auth headers for OData"""
    credentials = f"{settings.ODATA_USER}:{settings.ODATA_PASS}"
    encoded = base64.b64encode(credentials.encode('utf-8')).decode('ascii')
    return {
        "Authorization": f"Basic {encoded}",
        "Accept": "application/json"
    }


async def fetch_odata(
    endpoint: str,
    method: str = "GET",
    data: dict = None,
    timeout: float = 30.0
) -> dict:
    """
    Fetch data from Rent1C OData API

    Args:
        endpoint: OData endpoint path
        method: HTTP method (GET, POST, PATCH)
        data: Request body for POST/PATCH
        timeout: Request timeout in seconds

    Returns:
        JSON response as dict
    """
    try:
        headers = get_auth_headers()
        async with httpx.AsyncClient(timeout=timeout) as client:
            url = f"{settings.ODATA_URL}/{endpoint}"

            if method == "GET":
                response = await client.get(url, headers=headers)
            elif method == "POST":
                headers["Content-Type"] = "application/json; charset=utf-8"
                json_str = json.dumps(data, ensure_ascii=False)
                response = await client.post(
                    url, headers=headers, content=json_str.encode('utf-8')
                )
            elif method == "PATCH":
                headers["Content-Type"] = "application/json; charset=utf-8"
                json_str = json.dumps(data, ensure_ascii=False)
                response = await client.patch(
                    url, headers=headers, content=json_str.encode('utf-8')
                )
            else:
                return {"error": f"Unsupported method: {method}"}

            return response.json()
    except httpx.TimeoutException:
        return {"error": "Request timeout"}
    except httpx.HTTPStatusError as e:
        return {"error": f"HTTP error: {e.response.status_code}"}
    except Exception as e:
        return {"error": str(e)}


async def fetch_odata_cached(
    endpoint: str,
    cache_key: str = None,
    timeout: float = 30.0
) -> dict:
    """Fetch with caching for GET requests"""
    key = cache_key or endpoint
    cached = get_cache(key)
    if cached:
        return cached

    result = await fetch_odata(endpoint, timeout=timeout)
    if "error" not in result:
        set_cache(key, result)
    return result
