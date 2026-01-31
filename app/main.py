# -*- coding: utf-8 -*-
"""
TIPO-STO CRM - Main FastAPI Application
"""
import logging
from contextlib import asynccontextmanager
from pathlib import Path
from typing import List

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from app.config import get_settings
from app.api import clients_router, orders_router, inspections_router, assistant_router, kb_router
from app.services import get_odata_service, get_legacy_service

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan - startup and shutdown events"""
    # Startup
    logger.info("Starting TIPO-STO CRM...")
    settings = get_settings()
    logger.info(f"OData URL: {settings.ODATA_URL}")

    # Preload legacy data
    legacy = get_legacy_service()
    stats = legacy.get_stats()
    logger.info(f"Legacy data loaded: {stats}")

    yield

    # Shutdown
    logger.info("Shutting down TIPO-STO CRM...")


# Create FastAPI app
app = FastAPI(
    title="TIPO-STO CRM",
    description="CRM для автосервиса с интеграцией 1С через OData",
    version="1.0.0",
    lifespan=lifespan,
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API routers
app.include_router(clients_router, prefix="/api")
app.include_router(orders_router, prefix="/api")
app.include_router(inspections_router, prefix="/api")
app.include_router(assistant_router, prefix="/api")
app.include_router(kb_router, prefix="/api")


# ==================== Reference Data Endpoints ====================

@app.get("/api/ref/statuses", tags=["reference"])
async def get_order_statuses():
    """Get list of order statuses"""
    odata = get_odata_service()
    return await odata.get_order_statuses()


@app.get("/api/ref/works", tags=["reference"])
async def get_works_catalog(search: str = None, limit: int = 100):
    """Get works catalog with optional search"""
    odata = get_odata_service()
    return await odata.get_works_catalog(search=search, limit=limit)


@app.get("/api/ref/employees", tags=["reference"])
async def get_employees():
    """Get list of employees"""
    odata = get_odata_service()
    return await odata.get_employees()


@app.get("/api/cars", tags=["cars"])
async def get_cars(owner_ref: str = None, limit: int = 50):
    """Get list of cars, optionally filtered by owner"""
    odata = get_odata_service()
    return await odata.get_cars(owner_ref=owner_ref, limit=limit)


@app.get("/api/cars/{ref}", tags=["cars"])
async def get_car(ref: str):
    """Get car by Ref_Key"""
    odata = get_odata_service()
    return await odata.get_car(ref)


@app.get("/api/cars/search/plate/{plate}", tags=["cars"])
async def find_car_by_plate(plate: str):
    """Find car by license plate"""
    odata = get_odata_service()
    return await odata.find_car_by_plate(plate)


# ==================== Statistics ====================

@app.get("/api/stats", tags=["stats"])
async def get_stats():
    """Get system statistics"""
    legacy = get_legacy_service()
    odata = get_odata_service()

    legacy_stats = legacy.get_stats()

    return {
        "legacy": legacy_stats,
        "system": {
            "odata_url": get_settings().ODATA_URL,
            "cache_ttl": get_settings().CACHE_TTL,
        },
    }


# ==================== Health Check ====================

@app.get("/health", tags=["system"])
async def health_check():
    """Health check endpoint"""
    return {"status": "ok", "service": "tipo-sto"}


# ==================== Static Files ====================

# Serve static UI
static_dir = Path(__file__).parent / "static"
if static_dir.exists():
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")


@app.get("/", tags=["ui"])
async def root():
    """Serve main UI page"""
    # Try new UI first
    new_ui = Path(__file__).parent / "static" / "index.html"
    if new_ui.exists():
        return FileResponse(new_ui)
    # Fallback to old demo
    old_ui = Path(__file__).parent.parent / "demo_rent1c.html"
    if old_ui.exists():
        return FileResponse(old_ui)
    return {"message": "TIPO-STO CRM API", "docs": "/docs"}


@app.get("/admin/knowledge-base", tags=["ui"])
async def knowledge_base_admin():
    """Serve knowledge base admin page"""
    kb_ui = Path(__file__).parent / "static" / "admin_kb.html"
    if kb_ui.exists():
        return FileResponse(kb_ui)
    return {"error": "Knowledge base admin UI not found"}


@app.get("/mechanic", tags=["ui"])
async def mechanic_ui():
    """Serve mobile mechanic DVI page"""
    mechanic_ui = Path(__file__).parent / "static" / "mechanic.html"
    if mechanic_ui.exists():
        return FileResponse(mechanic_ui)
    return {"error": "Mechanic UI not found"}


# ==================== Run Server ====================

if __name__ == "__main__":
    import uvicorn
    settings = get_settings()
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
    )
