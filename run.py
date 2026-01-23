#!/usr/bin/env python3
"""
TIPO-STO Entry Point

Run the application with:
    python run.py

Or with uvicorn directly:
    uvicorn backend.main:app --reload --port 8000
"""
import uvicorn
import os
import sys

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from backend.config import settings


def main():
    """Run the TIPO-STO server"""
    print("=" * 50)
    print("  TIPO-STO - CRM для автосервиса")
    print("=" * 50)
    print(f"  Server: http://{settings.HOST}:{settings.PORT}")
    print(f"  OData:  {settings.ODATA_URL[:50]}...")
    print(f"  Debug:  {settings.DEBUG}")
    print("=" * 50)
    print()

    uvicorn.run(
        "backend.main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG
    )


if __name__ == "__main__":
    main()
