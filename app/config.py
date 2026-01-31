# -*- coding: utf-8 -*-
"""
TIPO-STO CRM Configuration
"""
import os
from pathlib import Path
from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    """Application settings"""

    # App info
    APP_NAME: str = "TIPO-STO CRM"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False

    # Rent1C OData
    ODATA_URL: str = "https://aclient.1c-hosting.com/1R96614/1R96614_AA61AS_e771ys34or/odata/standard.odata"
    ODATA_USER: str = "Администратор"
    ODATA_PASS: str = ""
    ODATA_TIMEOUT: float = 30.0

    # 1C Web Client (for report links)
    WEB_CLIENT_URL: str = "https://aclient.1c-hosting.com/1R96614/1R96614_AA61AS_e771ys34or"

    # Cache settings
    CACHE_TTL: int = 300  # 5 minutes

    # AI Assistant
    OPENAI_API_KEY: str = ""

    # Z.ai (Zhipu AI) - alternative LLM provider
    ZAI_API_KEY: str = ""
    ZAI_API_URL: str = "https://api.z.ai/api/paas/v4/chat/completions"
    ZAI_MODEL: str = "glm-4.5-air"
    # DeepSeek - best price/quality for Russian
    DEEPSEEK_API_KEY: str = ""
    DEEPSEEK_API_URL: str = "https://api.deepseek.com/chat/completions"
    DEEPSEEK_MODEL: str = "deepseek-chat"
    # LLM provider: "openai", "zai", or "deepseek"
    LLM_PROVIDER: str = "openai"

    # Auto.dev VIN Decoder API (1000 free/month)
    AUTODEV_API_KEY: str = ""

    # PartsAPI.ru - Russian auto parts catalog (~1200 RUB/month, demo keys free)
    PARTSAPI_KEY: str = ""

    # RAG / Knowledge Base
    RAG_COLLECTION_NAME: str = "knowledge_base"
    RAG_CHUNK_SIZE: int = 800
    RAG_CHUNK_OVERLAP: int = 100
    RAG_TOP_K: int = 5
    RAG_MIN_RELEVANCE: float = 0.3
    EMBEDDING_MODEL: str = "text-embedding-3-small"

    # Server
    HOST: str = "0.0.0.0"
    PORT: int = 8000

    # Paths
    BASE_DIR: Path = Path(__file__).parent.parent
    DATA_DIR: Path = BASE_DIR / "data"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


# Default GUIDs for Rent1C
DEFAULT_GUIDS = {
    "org": "39b4c1f1-fa7c-11e5-9841-6cf049a63e1b",
    "division": "39b4c1f0-fa7c-11e5-9841-6cf049a63e1b",
    "price_type": "65ce4042-fa7c-11e5-9841-6cf049a63e1b",
    "repair_type": "7d9f8931-1a7f-11e6-bee5-20689d8f1e0d",
    "status_new": "6bd193fc-fa7c-11e5-9841-6cf049a63e1b",
    "workshop": "65ce404a-fa7c-11e5-9841-6cf049a63e1b",
    "master": "eca30c81-f82d-11f0-9fbb-b02628ea963d",
    "manager": "eca30c81-f82d-11f0-9fbb-b02628ea963d",
    "author": "39b4c1f2-fa7c-11e5-9841-6cf049a63e1b",
    "currency": "6bd1932d-fa7c-11e5-9841-6cf049a63e1b",
    "operation": "530d99ea-fa7c-11e5-9841-6cf049a63e1b",
    "warehouse": "65ce4049-fa7c-11e5-9841-6cf049a63e1b",
    "repair_order": "c7194270-d152-11e8-87a5-f46d0425712d",
    "unit": "6ceca65d-18f4-11e6-a20f-6cf049a63e1b",
}

# Legacy data file paths
LEGACY_FILES = {
    "client_cars_mapping": "client_cars_mapping.json",
    "order_history": "order_history.json",
    "order_details": "order_details.json",
}


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance"""
    return Settings()
