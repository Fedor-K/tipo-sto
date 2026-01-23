"""Cars router - /api/cars endpoints"""
from fastapi import APIRouter, Query

from ..odata import fetch_odata, get_cache, set_cache, clear_cache

router = APIRouter(prefix="/api/cars", tags=["cars"])


@router.get("")
async def get_cars(
    q: str = Query(None, description="Search by name or VIN"),
    limit: int = Query(200, ge=1, le=500)
):
    """
    Get cars list with optional search

    - **q**: Search by name, VIN, or plate
    - **limit**: Max results (default 200)
    """
    cache_key = f"cars_{limit}_{q}"
    cached = get_cache(cache_key)
    if cached:
        return cached

    try:
        # Build filter
        filter_param = ""
        if q and len(q) >= 2:
            q_upper = q.upper()
            filter_param = f"$filter=substringof('{q_upper}', VIN) or substringof('{q}', Description)&"

        data = await fetch_odata(
            f"Catalog_Автомобили?{filter_param}$filter=IsFolder eq false&$expand=Поставщик&$top={limit}&$orderby=Description&$format=json"
        )

        if "error" in data:
            return {"cars": [], "count": 0, "error": data["error"]}

        items = data.get("value", [])
        cars = []

        for item in items:
            # Get owner info
            owner = item.get("Поставщик", {}) or {}
            owner_name = str(owner.get("Description", "") or "") if isinstance(owner, dict) else ""
            owner_ref = str(item.get("Поставщик_Key", "") or "")
            empty_ref = "00000000-0000-0000-0000-000000000000"

            cars.append({
                "code": str(item.get("Code", "")),
                "name": str(item.get("Description", "")),
                "vin": str(item.get("VIN", "") or ""),
                "plate": str(item.get("ГосНомер", "") or item.get("ГосударственныйНомер", "") or ""),
                "ref": str(item.get("Ref_Key", "")),
                "owner_name": owner_name if owner_ref != empty_ref else "",
                "owner_ref": owner_ref if owner_ref != empty_ref else ""
            })

        result = {"cars": cars, "count": len(cars)}
        set_cache(cache_key, result)
        return result

    except Exception as e:
        return {"cars": [], "count": 0, "error": str(e)}


@router.get("/{ref}")
async def get_car(ref: str):
    """Get car details by Ref_Key"""
    try:
        data = await fetch_odata(f"Catalog_Автомобили(guid'{ref}')?$format=json")

        if "error" in data:
            return {"error": data["error"]}

        return {
            "code": str(data.get("Code", "")),
            "name": str(data.get("Description", "")),
            "vin": str(data.get("VIN", "") or ""),
            "plate": str(data.get("ГосНомер", "") or ""),
            "year": str(data.get("ГодВыпуска", "") or ""),
            "ref": str(data.get("Ref_Key", ""))
        }

    except Exception as e:
        return {"error": str(e)}


@router.post("")
async def create_car(car: dict):
    """Create a new car in 1C"""
    try:
        car_data = {
            "Description": car.get("name", ""),
            "VIN": car.get("vin", ""),
            "НаименованиеПолное": car.get("name", ""),
        }

        # Set plate number
        if car.get("plate"):
            car_data["ГосНомер"] = car["plate"]

        # Link to owner (if provided)
        if car.get("owner_key"):
            car_data["Поставщик_Key"] = car["owner_key"]

        result = await fetch_odata("Catalog_Автомобили", method="POST", data=car_data)

        if "error" in result:
            return {"success": False, "error": result["error"]}
        if "odata.error" in result:
            return {
                "success": False,
                "error": result.get("odata.error", {}).get("message", {}).get("value", "OData error")
            }

        clear_cache("cars")

        return {
            "success": True,
            "code": result.get("Code", ""),
            "ref": result.get("Ref_Key", ""),
            "message": "Автомобиль создан"
        }

    except Exception as e:
        return {"success": False, "error": str(e)}
