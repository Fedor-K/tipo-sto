"""Catalogs router - /api/catalogs endpoints for reference data"""
from fastapi import APIRouter, Query

from ..odata import fetch_odata, get_cache, set_cache

router = APIRouter(prefix="/api/catalogs", tags=["catalogs"])


@router.get("/works")
async def get_works(
    q: str = Query(None, description="Search query"),
    limit: int = Query(100, ge=1, le=500)
):
    """Get auto works catalog (Автоработы)"""
    cache_key = f"works_{limit}_{q}"
    cached = get_cache(cache_key)
    if cached:
        return cached

    try:
        filter_param = "IsFolder eq false"
        if q and len(q) >= 2:
            filter_param = f"IsFolder eq false and substringof('{q}', Description)"

        data = await fetch_odata(
            f"Catalog_Автоработы?$filter={filter_param}&$top={limit}&$orderby=Description&$format=json"
        )

        if "error" in data:
            return {"items": [], "count": 0, "error": data["error"]}

        items = []
        for item in data.get("value", []):
            items.append({
                "code": str(item.get("Code", "")),
                "name": str(item.get("Description", "")),
                "time": float(item.get("ВремяВыполнения", 0) or 0),
                "ref": str(item.get("Ref_Key", ""))
            })

        result = {"items": items, "count": len(items)}
        set_cache(cache_key, result)
        return result

    except Exception as e:
        return {"items": [], "count": 0, "error": str(e)}


@router.get("/parts")
async def get_parts(
    q: str = Query(None, description="Search query"),
    limit: int = Query(100, ge=1, le=500)
):
    """Get parts catalog (Номенклатура)"""
    cache_key = f"parts_{limit}_{q}"
    cached = get_cache(cache_key)
    if cached:
        return cached

    try:
        filter_param = "IsFolder eq false"
        if q and len(q) >= 2:
            filter_param = f"IsFolder eq false and (substringof('{q}', Description) or substringof('{q}', Артикул))"

        data = await fetch_odata(
            f"Catalog_Номенклатура?$filter={filter_param}&$top={limit}&$orderby=Description&$format=json"
        )

        if "error" in data:
            return {"items": [], "count": 0, "error": data["error"]}

        items = []
        for item in data.get("value", []):
            items.append({
                "code": str(item.get("Code", "")),
                "name": str(item.get("Description", "")),
                "article": str(item.get("Артикул", "") or ""),
                "ref": str(item.get("Ref_Key", ""))
            })

        result = {"items": items, "count": len(items)}
        set_cache(cache_key, result)
        return result

    except Exception as e:
        return {"items": [], "count": 0, "error": str(e)}


@router.get("/repair-types")
async def get_repair_types():
    """Get repair types catalog (ВидыРемонта)"""
    cache_key = "repair_types"
    cached = get_cache(cache_key)
    if cached:
        return cached

    try:
        data = await fetch_odata("Catalog_ВидыРемонта?$format=json")

        if "error" in data:
            return {"items": [], "count": 0, "error": data["error"]}

        items = []
        for item in data.get("value", []):
            items.append({
                "code": str(item.get("Code", "")),
                "name": str(item.get("Description", "")),
                "ref": str(item.get("Ref_Key", ""))
            })

        result = {"items": items, "count": len(items)}
        set_cache(cache_key, result)
        return result

    except Exception as e:
        return {"items": [], "count": 0, "error": str(e)}


@router.get("/workshops")
async def get_workshops():
    """Get workshops catalog (Цеха)"""
    cache_key = "workshops"
    cached = get_cache(cache_key)
    if cached:
        return cached

    try:
        data = await fetch_odata("Catalog_Цеха?$format=json")

        if "error" in data:
            return {"items": [], "count": 0, "error": data["error"]}

        items = []
        for item in data.get("value", []):
            items.append({
                "code": str(item.get("Code", "")),
                "name": str(item.get("Description", "")),
                "ref": str(item.get("Ref_Key", ""))
            })

        result = {"items": items, "count": len(items)}
        set_cache(cache_key, result)
        return result

    except Exception as e:
        return {"items": [], "count": 0, "error": str(e)}


@router.get("/employees")
async def get_employees(limit: int = Query(50, ge=1, le=200)):
    """Get employees catalog (Сотрудники)"""
    cache_key = f"employees_{limit}"
    cached = get_cache(cache_key)
    if cached:
        return cached

    try:
        data = await fetch_odata(
            f"Catalog_Сотрудники?$filter=IsFolder eq false&$top={limit}&$orderby=Description&$format=json"
        )

        if "error" in data:
            return {"items": [], "count": 0, "error": data["error"]}

        items = []
        for item in data.get("value", []):
            items.append({
                "code": str(item.get("Code", "")),
                "name": str(item.get("Description", "")),
                "ref": str(item.get("Ref_Key", ""))
            })

        result = {"items": items, "count": len(items)}
        set_cache(cache_key, result)
        return result

    except Exception as e:
        return {"items": [], "count": 0, "error": str(e)}


@router.get("/order-statuses")
async def get_order_statuses():
    """Get order statuses catalog (ВидыСостоянийЗаказНарядов)"""
    cache_key = "order_statuses"
    cached = get_cache(cache_key)
    if cached:
        return cached

    try:
        data = await fetch_odata("Catalog_ВидыСостоянийЗаказНарядов?$format=json")

        if "error" in data:
            return {"items": [], "count": 0, "error": data["error"]}

        items = []
        for item in data.get("value", []):
            items.append({
                "code": str(item.get("Code", "")),
                "name": str(item.get("Description", "")),
                "ref": str(item.get("Ref_Key", ""))
            })

        result = {"items": items, "count": len(items)}
        set_cache(cache_key, result)
        return result

    except Exception as e:
        return {"items": [], "count": 0, "error": str(e)}


@router.get("/organizations")
async def get_organizations():
    """Get organizations catalog (Организации)"""
    cache_key = "organizations"
    cached = get_cache(cache_key)
    if cached:
        return cached

    try:
        data = await fetch_odata("Catalog_Организации?$format=json")

        if "error" in data:
            return {"items": [], "count": 0, "error": data["error"]}

        items = []
        for item in data.get("value", []):
            items.append({
                "code": str(item.get("Code", "")),
                "name": str(item.get("Description", "")),
                "ref": str(item.get("Ref_Key", ""))
            })

        result = {"items": items, "count": len(items)}
        set_cache(cache_key, result)
        return result

    except Exception as e:
        return {"items": [], "count": 0, "error": str(e)}
