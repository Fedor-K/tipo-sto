"""
TIPO-STO Backend - FastAPI Application

CRM для автосервиса, работающий через Rent1C OData API.
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import os

from .config import settings
from .odata import fetch_odata
from .routers import clients, orders, cars, catalogs, stats

# Create FastAPI app
app = FastAPI(
    title="TIPO-STO API",
    description="CRM для автосервиса - API для работы с 1С через OData",
    version="2.0.0"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(clients.router)
app.include_router(orders.router)
app.include_router(cars.router)
app.include_router(catalogs.router)
app.include_router(stats.router)

# Get base directory
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FRONTEND_DIR = os.path.join(BASE_DIR, "frontend")


@app.get("/")
async def root():
    """Serve frontend index.html or API status"""
    index_path = os.path.join(FRONTEND_DIR, "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path)
    return {
        "status": "ok",
        "message": "TIPO-STO API is running",
        "version": "2.0.0",
        "mode": "odata",
        "source": "Rent1C"
    }


@app.get("/api")
async def api_root():
    """API status endpoint"""
    return {
        "status": "ok",
        "message": "TIPO-STO API is running",
        "version": "2.0.0",
        "endpoints": {
            "clients": "/api/clients",
            "orders": "/api/orders",
            "cars": "/api/cars",
            "catalogs": "/api/catalogs/*",
            "stats": "/api/stats/dashboard"
        }
    }


@app.get("/api/test-odata")
async def test_odata():
    """Test OData connection"""
    data = await fetch_odata("")
    return data


@app.get("/api/search")
async def search(q: str):
    """
    Universal search across clients, cars, and orders

    - **q**: Search query (minimum 2 characters)
    """
    if not q or len(q) < 2:
        return {"results": [], "query": q, "total": 0}

    results = []

    # Search clients
    try:
        clients_data = await fetch_odata(
            f"Catalog_Контрагенты?$filter=substringof('{q}', Description) or substringof('{q}', Code)&$top=20&$format=json"
        )
        for item in clients_data.get("value", []):
            results.append({
                "type": "client",
                "code": str(item.get("Code", "")).strip(),
                "name": str(item.get("Description", "")),
                "ref": str(item.get("Ref_Key", ""))
            })
    except:
        pass

    # Search cars
    try:
        q_upper = q.upper()
        cars_data = await fetch_odata(
            f"Catalog_Автомобили?$filter=substringof('{q_upper}', VIN) or substringof('{q}', Description)&$top=20&$format=json"
        )
        for item in cars_data.get("value", []):
            results.append({
                "type": "car",
                "code": str(item.get("Code", "")),
                "name": str(item.get("Description", "")),
                "vin": str(item.get("VIN", "") or ""),
                "plate": str(item.get("ГосНомер", "") or ""),
                "ref": str(item.get("Ref_Key", ""))
            })
    except:
        pass

    # Search orders by number
    try:
        orders_data = await fetch_odata(
            f"Document_ЗаказНаряд?$filter=substringof('{q}', Number)&$top=10&$orderby=Date desc&$format=json"
        )
        for item in orders_data.get("value", []):
            results.append({
                "type": "order",
                "number": str(item.get("Number", "")).strip(),
                "date": str(item.get("Date", ""))[:10] if item.get("Date") else "",
                "sum": float(item.get("СуммаДокумента", 0) or 0),
                "status": "Проведен" if item.get("Posted") else "Черновик",
                "ref": str(item.get("Ref_Key", ""))
            })
    except:
        pass

    return {"results": results[:50], "query": q, "total": len(results)}


# Mount static files for frontend (must be after routes)
if os.path.exists(FRONTEND_DIR):
    app.mount("/css", StaticFiles(directory=os.path.join(FRONTEND_DIR, "css")), name="css")
    app.mount("/js", StaticFiles(directory=os.path.join(FRONTEND_DIR, "js")), name="js")


# For running with: python -m uvicorn backend.main:app
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "backend.main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG
    )
