"""Clients router - /api/clients endpoints"""
from fastapi import APIRouter, Query

from ..odata import fetch_odata, fetch_odata_cached, get_cache, set_cache, clear_cache

router = APIRouter(prefix="/api/clients", tags=["clients"])


def extract_contact_info(item: dict) -> tuple:
    """Extract phone and address from КонтактнаяИнформация"""
    phone = ""
    address = ""
    contact_info = item.get("КонтактнаяИнформация", [])
    for ci in contact_info:
        ci_type = ci.get("Тип", "")
        if ci_type == "Телефон" and ci.get("НомерТелефона"):
            phone = ci.get("НомерТелефона", "")
        if ci_type == "Адрес" and not address:
            address = ci.get("Представление", "")
    return phone, address


@router.get("")
async def get_clients(
    q: str = Query(None, description="Search query"),
    sort: str = Query("code", description="Sort by: code, name, name_desc"),
    limit: int = Query(500, ge=1, le=1000)
):
    """
    Get clients list with optional search and sorting

    - **q**: Search by name or code
    - **sort**: code (default), name, name_desc
    - **limit**: Max results (default 500)
    """
    cache_key = f"clients_{sort}_{limit}_{q}"
    cached = get_cache(cache_key)
    if cached:
        return cached

    try:
        # Build orderby parameter
        orderby_map = {
            "name": "Description asc",
            "name_desc": "Description desc",
            "code": "Code desc"
        }
        orderby = orderby_map.get(sort, "Code desc")

        # Build filter for search
        filter_param = ""
        if q and len(q) >= 2:
            filter_param = f"$filter=substringof('{q}', Description) or substringof('{q}', Code)&"

        data = await fetch_odata(
            f"Catalog_Контрагенты?{filter_param}$top={limit}&$orderby={orderby}&$format=json"
        )

        if "error" in data:
            return {"clients": [], "count": 0, "error": data["error"]}

        items = data.get("value", [])
        clients = []

        for item in items:
            phone, address = extract_contact_info(item)
            clients.append({
                "code": str(item.get("Code", "")).strip(),
                "name": str(item.get("Description", "")),
                "phone": phone,
                "address": address,
                "ref": str(item.get("Ref_Key", "")),
                "inn": str(item.get("ИНН", "") or "")
            })

        result = {"clients": clients, "count": len(clients), "sort": sort}
        set_cache(cache_key, result)
        return result

    except Exception as e:
        return {"clients": [], "count": 0, "error": str(e)}


@router.get("/{ref}")
async def get_client(ref: str):
    """
    Get client details by Ref_Key

    Returns client info, their cars (from order history), and orders
    """
    try:
        # Get client info
        client_data = await fetch_odata(f"Catalog_Контрагенты(guid'{ref}')?$format=json")
        if "error" in client_data:
            return {"error": client_data["error"]}

        phone, address = extract_contact_info(client_data)

        client = {
            "code": str(client_data.get("Code", "")).strip(),
            "name": str(client_data.get("Description", "")),
            "full_name": str(client_data.get("НаименованиеПолное", "") or client_data.get("Description", "")),
            "phone": phone,
            "address": address,
            "ref": str(client_data.get("Ref_Key", "")),
            "inn": str(client_data.get("ИНН", "") or ""),
            "comment": str(client_data.get("Комментарий", "") or ""),
            "type": str(client_data.get("ВидКонтрагента", "") or "Клиент")
        }

        # Get client's orders
        orders = []
        orders_data = await fetch_odata(
            f"Document_ЗаказНаряд?$filter=Контрагент_Key eq guid'{ref}'&$orderby=Date desc&$top=50&$format=json"
        )
        if orders_data.get("value"):
            for item in orders_data["value"]:
                orders.append({
                    "number": str(item.get("Number", "")).strip(),
                    "date": str(item.get("Date", ""))[:10] if item.get("Date") else "",
                    "sum": float(item.get("СуммаДокумента", 0) or item.get("СуммаНоменклатурыДокумента", 0) or 0) +
                           float(item.get("СуммаРаботДокумента", 0) or 0),
                    "status": "Проведен" if item.get("Posted", False) else "Черновик",
                    "comment": str(item.get("ОписаниеПричиныОбращения", "") or ""),
                    "ref": str(item.get("Ref_Key", ""))
                })

        # Get client's cars - BOTH from ownership (Поставщик_Key) and order history
        cars = []
        car_refs_seen = set()

        # 1. Get cars where client is owner (Поставщик_Key)
        owned_cars = await fetch_odata(
            f"Catalog_Автомобили?$filter=Поставщик_Key eq guid'{ref}'&$format=json"
        )
        for item in owned_cars.get("value", []):
            car_ref = str(item.get("Ref_Key", ""))
            if car_ref not in car_refs_seen:
                car_refs_seen.add(car_ref)
                cars.append({
                    "code": str(item.get("Code", "")),
                    "name": str(item.get("Description", "")),
                    "vin": str(item.get("VIN", "") or ""),
                    "plate": str(item.get("ГосНомер", "") or ""),
                    "ref": car_ref,
                    "owned": True
                })

        # 2. Also get cars from order history (for backwards compatibility)
        car_keys = set()
        for order in orders_data.get("value", [])[:20]:
            order_ref = order.get("Ref_Key")
            if order_ref:
                cars_data = await fetch_odata(
                    f"Document_ЗаказНаряд(guid'{order_ref}')/Автомобили?$format=json"
                )
                for car_row in cars_data.get("value", []):
                    car_key = car_row.get("Автомобиль_Key")
                    if car_key and car_key != "00000000-0000-0000-0000-000000000000":
                        car_keys.add(car_key)

        # Load car details from history (if not already loaded)
        for car_key in list(car_keys)[:20]:
            if car_key not in car_refs_seen:
                car_data = await fetch_odata(f"Catalog_Автомобили(guid'{car_key}')?$format=json")
                if car_data and "Ref_Key" in car_data:
                    car_refs_seen.add(car_key)
                    cars.append({
                        "code": str(car_data.get("Code", "")),
                        "name": str(car_data.get("Description", "")),
                        "vin": str(car_data.get("VIN", "") or ""),
                        "plate": str(car_data.get("ГосНомер", "") or ""),
                        "ref": str(car_data.get("Ref_Key", "")),
                        "owned": False
                    })

        return {
            "client": client,
            "cars": cars,
            "orders": orders,
            "cars_count": len(cars),
            "orders_count": len(orders),
            "total_sum": sum(o["sum"] for o in orders)
        }

    except Exception as e:
        return {"error": str(e)}


@router.get("/{ref}/cars")
async def get_client_cars(ref: str):
    """Get cars associated with client (from order history)"""
    try:
        # Get orders for this client
        orders_data = await fetch_odata(
            f"Document_ЗаказНаряд?$filter=Контрагент_Key eq guid'{ref}'&$top=30&$format=json"
        )

        car_keys = set()

        # Collect car keys from orders' tabular parts
        for order in orders_data.get("value", []):
            order_ref = order.get("Ref_Key")
            if order_ref:
                cars_data = await fetch_odata(
                    f"Document_ЗаказНаряд(guid'{order_ref}')/Автомобили?$format=json"
                )
                for car_row in cars_data.get("value", []):
                    car_key = car_row.get("Автомобиль_Key")
                    if car_key and car_key != "00000000-0000-0000-0000-000000000000":
                        car_keys.add(car_key)

        if not car_keys:
            return {"cars": [], "count": 0, "client_ref": ref}

        # Load car details
        filter_str = " or ".join([f"Ref_Key eq guid'{k}'" for k in list(car_keys)[:20]])
        cars_data = await fetch_odata(
            f"Catalog_Автомобили?$filter={filter_str}&$format=json"
        )

        cars = []
        for item in cars_data.get("value", []):
            cars.append({
                "code": str(item.get("Code", "")),
                "name": str(item.get("Description", "")),
                "vin": str(item.get("VIN", "") or ""),
                "plate": str(item.get("ГосНомер", "") or ""),
                "ref": str(item.get("Ref_Key", ""))
            })

        return {"cars": cars, "count": len(cars), "client_ref": ref}

    except Exception as e:
        return {"cars": [], "count": 0, "error": str(e)}


@router.get("/{ref}/orders")
async def get_client_orders(ref: str, limit: int = Query(50, ge=1, le=200)):
    """Get orders for a specific client"""
    try:
        data = await fetch_odata(
            f"Document_ЗаказНаряд?$filter=Контрагент_Key eq guid'{ref}'&$orderby=Date desc&$top={limit}&$format=json"
        )

        if "error" in data:
            return {"orders": [], "count": 0, "error": data["error"]}

        orders = []
        for item in data.get("value", []):
            orders.append({
                "number": str(item.get("Number", "")).strip(),
                "date": str(item.get("Date", ""))[:10] if item.get("Date") else "",
                "sum": float(item.get("СуммаДокумента", 0) or 0) +
                       float(item.get("СуммаРаботДокумента", 0) or 0),
                "status": "Проведен" if item.get("Posted", False) else "Черновик",
                "comment": str(item.get("ОписаниеПричиныОбращения", "") or ""),
                "ref": str(item.get("Ref_Key", ""))
            })

        return {"orders": orders, "count": len(orders), "client_ref": ref}

    except Exception as e:
        return {"orders": [], "count": 0, "error": str(e)}


@router.post("")
async def create_client(client: dict):
    """Create a new client in 1C"""
    try:
        client_data = {
            "Description": client.get("name", ""),
            "НаименованиеПолное": client.get("name", ""),
        }

        if client.get("inn"):
            client_data["ИНН"] = client["inn"]
        if client.get("comment"):
            client_data["Комментарий"] = client["comment"]

        result = await fetch_odata("Catalog_Контрагенты", method="POST", data=client_data)

        if "error" in result:
            return {"success": False, "error": result["error"]}
        if "odata.error" in result:
            return {
                "success": False,
                "error": result.get("odata.error", {}).get("message", {}).get("value", "OData error")
            }

        clear_cache("clients")

        return {
            "success": True,
            "code": result.get("Code", ""),
            "ref": result.get("Ref_Key", ""),
            "message": "Клиент создан"
        }

    except Exception as e:
        return {"success": False, "error": str(e)}
