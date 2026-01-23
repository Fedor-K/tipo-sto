"""Configuration module - loads settings from environment variables"""
import os
from functools import lru_cache

# Try to load .env file if python-dotenv is available
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass


class Settings:
    """Application settings loaded from environment variables"""

    # OData connection settings
    ODATA_URL: str = os.getenv(
        "ODATA_URL",
        "https://aclient.1c-hosting.com/1R96614/1R96614_AA61AS_e771ys34or/odata/standard.odata"
    )
    ODATA_USER: str = os.getenv("ODATA_USER", "Администратор")
    ODATA_PASS: str = os.getenv("ODATA_PASS", "")

    # Cache settings
    CACHE_TTL: int = int(os.getenv("CACHE_TTL", "300"))  # 5 minutes

    # Server settings
    HOST: str = os.getenv("HOST", "0.0.0.0")
    PORT: int = int(os.getenv("PORT", "8000"))
    DEBUG: bool = os.getenv("DEBUG", "false").lower() == "true"

    # Default GUIDs for ООО Сервис-Авто
    DEFAULT_ORG: str = "39b4c1f1-fa7c-11e5-9841-6cf049a63e1b"
    DEFAULT_DIVISION: str = "39b4c1f0-fa7c-11e5-9841-6cf049a63e1b"
    DEFAULT_PRICE_TYPE: str = "65ce4042-fa7c-11e5-9841-6cf049a63e1b"
    DEFAULT_REPAIR_TYPE: str = "7d9f8931-1a7f-11e6-bee5-20689d8f1e0d"
    DEFAULT_STATUS: str = "6bd193fc-fa7c-11e5-9841-6cf049a63e1b"  # Заявка
    DEFAULT_WORKSHOP: str = "65ce404a-fa7c-11e5-9841-6cf049a63e1b"
    DEFAULT_MASTER: str = "c94de32f-fa7c-11e5-9841-6cf049a63e1b"
    DEFAULT_MANAGER: str = "c94de33e-fa7c-11e5-9841-6cf049a63e1b"
    DEFAULT_AUTHOR: str = "39b4c1f2-fa7c-11e5-9841-6cf049a63e1b"
    DEFAULT_CURRENCY: str = "6bd1932d-fa7c-11e5-9841-6cf049a63e1b"
    DEFAULT_OPERATION: str = "530d99ea-fa7c-11e5-9841-6cf049a63e1b"
    DEFAULT_WAREHOUSE: str = "65ce4049-fa7c-11e5-9841-6cf049a63e1b"
    DEFAULT_REPAIR_ORDER: str = "c7194270-d152-11e8-87a5-f46d0425712d"


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance"""
    return Settings()


settings = get_settings()
