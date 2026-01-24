# -*- coding: utf-8 -*-
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional
from datetime import datetime, timedelta
import httpx
import json
import os

app = FastAPI(title="TIPO-STO API")

# Frontend directory
FRONTEND_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "frontend")

# Mount CSS and JS directories
if os.path.exists(FRONTEND_DIR):
    css_dir = os.path.join(FRONTEND_DIR, "css")
    js_dir = os.path.join(FRONTEND_DIR, "js")
    if os.path.exists(css_dir):
        app.mount("/css", StaticFiles(directory=css_dir), name="css")
    if os.path.exists(js_dir):
        app.mount("/js", StaticFiles(directory=js_dir), name="js")

@app.get("/")
async def root():
    """Serve frontend index.html"""
    index_path = os.path.join(FRONTEND_DIR, "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path)
    return {"message": "TIPO-STO API", "docs": "/docs"}

# Load data from old database files
ORDERS_HISTORY = []
EMPLOYEES_DATA = []
WORKSHOPS_DATA = []
REPAIR_TYPES_DATA = []

def load_json_file(filename):
    try:
        path = os.path.join(os.path.dirname(__file__), filename)
        if not os.path.exists(path):
            path = f"C:\\tipoSTO\\{filename}"
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
    except:
        pass
    return []

ORDERS_HISTORY = load_json_file("orders_history.json")
EMPLOYEES_DATA = load_json_file("employees.json")
WORKSHOPS_DATA = load_json_file("workshops.json")
REPAIR_TYPES_DATA = load_json_file("repair_types.json")

print(f"Loaded: {len(ORDERS_HISTORY)} orders, {len(EMPLOYEES_DATA)} employees, {len(WORKSHOPS_DATA)} workshops, {len(REPAIR_TYPES_DATA)} repair types")

# Кэш для ускорения
cache = {}
CACHE_TTL = 300  # 5 минут

def get_cache(key):
    if key in cache:
        data, expires = cache[key]
        if datetime.now() < expires:
            return data
    return None

def set_cache(key, data):
    cache[key] = (data, datetime.now() + timedelta(seconds=CACHE_TTL))

def clear_cache(key=None):
    if key:
        cache.pop(key, None)
    else:
        cache.clear()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Rent1C OData - РАБОТАЕТ!
ODATA_URL = "https://aclient.1c-hosting.com/1R96614/1R96614_AA61AS_e771ys34or/odata/standard.odata"
ODATA_USER = "Администратор"
ODATA_PASS = ""  # Пустой пароль

# Models
class OrderCreate(BaseModel):
    client_code: str
    car: str = ""
    comment: str = ""

class OrderUpdate(BaseModel):
    status: Optional[str] = None
    comment: Optional[str] = None

def get_odata_auth():
    """Get basic auth for OData"""
    import base64
    credentials = f"{ODATA_USER}:{ODATA_PASS}"
    encoded = base64.b64encode(credentials.encode('utf-8')).decode('ascii')
    return {"Authorization": f"Basic {encoded}", "Accept": "application/json"}

async def fetch_odata(endpoint: str, method: str = "GET", data: dict = None):
    """Fetch data from Rent1C OData"""
    try:
        headers = get_odata_auth()
        async with httpx.AsyncClient(timeout=30.0) as client:
            url = f"{ODATA_URL}/{endpoint}"
            if method == "GET":
                response = await client.get(url, headers=headers)
            elif method == "POST":
                headers["Content-Type"] = "application/json; charset=utf-8"
                json_str = json.dumps(data, ensure_ascii=False)
                response = await client.post(url, headers=headers, content=json_str.encode('utf-8'))
            elif method == "PATCH":
                headers["Content-Type"] = "application/json; charset=utf-8"
                json_str = json.dumps(data, ensure_ascii=False)
                response = await client.patch(url, headers=headers, content=json_str.encode('utf-8'))
            return response.json()
    except Exception as e:
        return {"error": str(e)}

async def fetch_from_1c(endpoint: str, method: str = "GET", data: dict = None):
    """Fetch data from 1C API Gateway (COM connector fallback)"""
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            if method == "GET":
                response = await client.get(f"{API_1C_URL}{endpoint}")
            elif method == "POST":
                response = await client.post(f"{API_1C_URL}{endpoint}", json=data)
            elif method == "PUT":
                response = await client.put(f"{API_1C_URL}{endpoint}", json=data)
            return response.json()
    except Exception as e:
        return {"error": str(e)}

@app.get("/")
async def root():
    return {"status": "ok", "message": "TIPO-STO API is running", "mode": "odata", "source": "Rent1C"}

@app.get("/api/test-odata")
async def test_odata():
    """Test OData connection"""
    data = await fetch_odata("")
    return data

@app.get("/api/clients")
async def get_clients(sort: str = "code", limit: int = 500, search: str = None):
    """Get clients with optional sorting and search"""
    cache_key = f"clients_{sort}_{limit}_{search}"
    cached = get_cache(cache_key)
    if cached:
        return cached
    try:
        # Build orderby parameter
        if sort == "name":
            orderby = "Description asc"
        elif sort == "name_desc":
            orderby = "Description desc"
        else:  # code
            orderby = "Code desc"

        # Build filter for search
        filter_param = ""
        if search and len(search) >= 2:
            filter_param = f"$filter=substringof('{search}', Description) or substringof('{search}', Code)&"

        data = await fetch_odata(f"Catalog_Контрагенты?{filter_param}$top={limit}&$orderby={orderby}&$format=json")
        if "error" in data:
            return {"clients": [], "count": 0, "error": data["error"]}
        items = data.get("value", [])
        clients = []
        for item in items:
            # Extract phone and address from КонтактнаяИнформация
            phone = ""
            address = ""
            contact_info = item.get("КонтактнаяИнформация", [])
            for ci in contact_info:
                ci_type = ci.get("Тип", "")
                if ci_type == "Телефон" and ci.get("НомерТелефона"):
                    phone = ci.get("НомерТелефона", "")
                    break
                if ci_type == "Адрес" and not address:
                    address = ci.get("Представление", "")
            clients.append({
                "code": str(item.get("Code", "")).strip(),
                "name": str(item.get("Description", "")),
                "phone": phone,
                "address": address,
                "ref": str(item.get("Ref_Key", "")),
                "car": ""
            })
        result = {"clients": clients, "count": len(clients), "sort": sort}
        set_cache(cache_key, result)
        return result
    except Exception as e:
        return {"clients": [], "count": 0, "error": str(e)}

@app.get("/api/clients/{client_ref}")
async def get_client(client_ref: str):
    """Get single client by ref"""
    try:
        data = await fetch_odata(f"Catalog_Контрагенты(guid'{client_ref}')?$format=json")
        if "error" in data or not data.get("Ref_Key"):
            return {"error": "Клиент не найден"}

        # Get client's orders
        orders_data = await fetch_odata(f"Document_ЗаказНаряд?$filter=Контрагент_Key eq guid'{client_ref}'&$top=50&$orderby=Date desc&$format=json")
        orders = []
        for o in orders_data.get("value", []):
            orders.append({
                "ref": o.get("Ref_Key", ""),
                "number": o.get("Number", ""),
                "date": o.get("Date", ""),
                "sum": o.get("СуммаДокумента", 0),
                "status": o.get("Состояние_Key", ""),
            })

        return {
            "ref": data.get("Ref_Key", ""),
            "code": data.get("Code", ""),
            "name": data.get("Description", ""),
            "type": "Покупатель",
            "orders": orders
        }
    except Exception as e:
        return {"error": str(e)}

@app.get("/api/clients/{client_ref}/cars")
async def get_client_cars_by_ref(client_ref: str):
    """Get cars for a client from their order history (tabular part Автомобили)"""
    try:
        # Get orders for this client with their car tabular parts
        orders_data = await fetch_odata(f"Document_ЗаказНаряд?$filter=Контрагент_Key eq guid'{client_ref}'&$top=50&$format=json")

        car_refs = set()
        for o in orders_data.get("value", []):
            # Cars are in tabular part "Автомобили"
            cars_tab = o.get("Автомобили", [])
            for car_row in cars_tab:
                car_key = car_row.get("Автомобиль_Key")
                if car_key and car_key != "00000000-0000-0000-0000-000000000000":
                    car_refs.add(car_key)

        cars = []
        for car_ref in list(car_refs)[:20]:
            car_data = await fetch_odata(f"Catalog_Автомобили(guid'{car_ref}')?$format=json")
            if car_data.get("Ref_Key"):
                cars.append({
                    "ref": car_data.get("Ref_Key", ""),
                    "name": car_data.get("Description", ""),
                    "vin": car_data.get("VIN", "") or car_data.get("ВИН", ""),
                })

        return {"cars": cars, "count": len(cars)}
    except Exception as e:
        return {"cars": [], "error": str(e)}

@app.get("/api/orders")
async def get_orders(status: str = None, period: str = None, date_from: str = None, date_to: str = None, limit: int = 100):
    """Get orders with optional filters"""
    cache_key = f"orders_{status}_{period}_{date_from}_{date_to}_{limit}"
    cached = get_cache(cache_key)
    if cached:
        return cached
    try:
        # Build OData filter
        filters = []
        if status == "draft":
            filters.append("Posted eq false")
        elif status == "done":
            filters.append("Posted eq true")

        # Период или конкретные даты
        if date_from:
            filters.append(f"Date ge datetime'{date_from}T00:00:00'")
        elif period and period != "all":
            now = datetime.now()
            if period == "today":
                df = now.replace(hour=0, minute=0, second=0, microsecond=0)
            elif period == "week":
                df = now - timedelta(days=7)
            elif period == "month":
                df = now - timedelta(days=30)
            elif period == "quarter":
                df = now - timedelta(days=90)
            elif period == "year":
                df = now - timedelta(days=365)
            else:
                df = None
            if df:
                filters.append(f"Date ge datetime'{df.strftime('%Y-%m-%dT%H:%M:%S')}'")

        if date_to:
            filters.append(f"Date le datetime'{date_to}T23:59:59'")

        filter_str = " and ".join(filters) if filters else ""
        filter_param = f"$filter={filter_str}&" if filter_str else ""

        # Get orders with expanded Контрагент
        data = await fetch_odata(f"Document_ЗаказНаряд?{filter_param}$top={limit}&$orderby=Date desc&$expand=Контрагент&$format=json")
        if "error" in data:
            return {"orders": [], "count": 0, "error": data["error"]}
        items = data.get("value", [])
        orders = []
        for item in items:
            posted = item.get("Posted", False)
            status = "Проведен" if posted else "Черновик"
            date_str = str(item.get("Date", ""))[:10] if item.get("Date") else ""
            # Get client name from expanded Контрагент or Контрагент_Key
            client_name = ""
            if item.get("Контрагент"):
                client_name = str(item["Контрагент"].get("Description", ""))
            # Get car from Автомобили array (first item if exists)
            car_name = ""
            cars_array = item.get("Автомобили", [])
            if cars_array and len(cars_array) > 0:
                car_name = str(cars_array[0].get("Автомобиль", "") or cars_array[0].get("Description", "") or "")
            orders.append({
                "number": str(item.get("Number", "")),
                "date": date_str,
                "client": client_name,
                "client_key": str(item.get("Контрагент_Key", "")),
                "car": car_name,
                "status": status,
                "sum": float(item.get("СуммаДокумента", 0) or item.get("DocumentSum", 0) or 0),
                "comment": str(item.get("Комментарий", "") or item.get("Comment", "") or "")
            })
        result = {"orders": orders, "count": len(orders), "filters": {"status": status, "period": period}}
        set_cache(cache_key, result)
        return result
    except Exception as e:
        return {"orders": [], "count": 0, "error": str(e)}

@app.get("/api/orders/{order_number}")
async def get_order(order_number: str):
    try:
        data = await fetch_odata(f"Document_ЗаказНаряд?$filter=Number eq '{order_number}'&$format=json")
        if "error" in data:
            return {"error": data["error"]}
        items = data.get("value", [])
        if not items:
            return {"error": f"Order {order_number} not found"}
        item = items[0]
        posted = item.get("Posted", False)
        return {
            "number": str(item.get("Number", "")),
            "date": str(item.get("Date", ""))[:10] if item.get("Date") else "",
            "client": str(item.get("Контрагент", "") or ""),
            "comment": str(item.get("Комментарий", "") or ""),
            "sum": float(item.get("СуммаДокумента", 0) or 0),
            "status": "Проведен" if posted else "Черновик"
        }
    except Exception as e:
        return {"error": str(e)}

@app.get("/api/catalogs/works")
async def get_works_catalog(limit: int = 100, q: str = None):
    """Get works catalog (Автоработы) from OData"""
    cache_key = f"works_{limit}_{q or ''}"
    cached = get_cache(cache_key)
    if cached:
        return cached
    try:
        filter_str = ""
        if q:
            filter_str = f"&$filter=contains(Description,'{q}')"
        data = await fetch_odata(f"Catalog_Автоработы?$top={limit}&$select=Ref_Key,Code,Description,ВремяВыполнения{filter_str}&$format=json")
        if "error" in data:
            return {"items": [], "count": 0, "error": data["error"]}
        items = []
        for item in data.get("value", []):
            items.append({
                "ref": item.get("Ref_Key", ""),
                "code": item.get("Code", ""),
                "name": item.get("Description", ""),
                "time": item.get("ВремяВыполнения", 0),
            })
        result = {"items": items, "count": len(items)}
        set_cache(cache_key, result)
        return result
    except Exception as e:
        return {"items": [], "count": 0, "error": str(e)}

@app.get("/api/catalogs/parts")
async def get_parts_catalog(limit: int = 100, q: str = None):
    """Get parts catalog (Номенклатура) from OData"""
    cache_key = f"parts_{limit}_{q or ''}"
    cached = get_cache(cache_key)
    if cached:
        return cached
    try:
        filter_str = ""
        if q:
            filter_str = f"&$filter=contains(Description,'{q}')"
        data = await fetch_odata(f"Catalog_Номенклатура?$top={limit}&$select=Ref_Key,Code,Description,Артикул{filter_str}&$format=json")
        if "error" in data:
            return {"items": [], "count": 0, "error": data["error"]}
        items = []
        for item in data.get("value", []):
            items.append({
                "ref": item.get("Ref_Key", ""),
                "code": item.get("Code", ""),
                "name": item.get("Description", ""),
                "article": item.get("Артикул", ""),
            })
        result = {"items": items, "count": len(items)}
        set_cache(cache_key, result)
        return result
    except Exception as e:
        return {"items": [], "count": 0, "error": str(e)}

@app.get("/api/catalogs/repair-types")
async def get_repair_types_catalog(limit: int = 50):
    """Get repair types from OData"""
    try:
        data = await fetch_odata(f"Catalog_ВидыРемонта?$top={limit}&$format=json")
        items = []
        for item in data.get("value", []):
            items.append({
                "ref": item.get("Ref_Key", ""),
                "code": item.get("Code", ""),
                "name": item.get("Description", ""),
            })
        return {"items": items, "count": len(items)}
    except Exception as e:
        return {"items": [], "count": 0, "error": str(e)}

@app.get("/api/catalogs/workshops")
async def get_workshops_catalog(limit: int = 50):
    """Get workshops from OData"""
    try:
        data = await fetch_odata(f"Catalog_Цеха?$top={limit}&$format=json")
        items = []
        for item in data.get("value", []):
            items.append({
                "ref": item.get("Ref_Key", ""),
                "code": item.get("Code", ""),
                "name": item.get("Description", ""),
            })
        return {"items": items, "count": len(items)}
    except Exception as e:
        return {"items": [], "count": 0, "error": str(e)}

@app.get("/api/catalogs/employees")
async def get_employees_catalog(limit: int = 100):
    """Get employees from OData"""
    try:
        data = await fetch_odata(f"Catalog_Сотрудники?$top={limit}&$format=json")
        items = []
        for item in data.get("value", []):
            items.append({
                "ref": item.get("Ref_Key", ""),
                "code": item.get("Code", ""),
                "name": item.get("Description", ""),
            })
        return {"items": items, "count": len(items)}
    except Exception as e:
        return {"items": [], "count": 0, "error": str(e)}

@app.get("/api/catalogs/{name}")
async def get_catalog(name: str, limit: int = 100):
    """Get catalog - generic endpoint for other catalogs"""

    # For other catalogs - use OData
    cache_key = f"catalog_{name}_{limit}"
    cached = get_cache(cache_key)
    if cached:
        return cached
    try:
        # Map names to OData catalog names (Альфа-Авто)
        catalog_map = {
            "clients": "Catalog_Контрагенты",
            "cars": "Catalog_Автомобили",
            "warehouses": "Catalog_СкладыКомпании",
            "organizations": "Catalog_Организации",
        }
        odata_name = catalog_map.get(name, f"Catalog_{name}")
        data = await fetch_odata(f"{odata_name}?$top={limit}&$format=json")
        if "error" in data:
            return {"items": [], "count": 0, "error": data["error"]}
        items = data.get("value", [])
        result_items = []
        for item in items:
            result_items.append({
                "code": str(item.get("Code", "") or item.get("Ref_Key", "")),
                "name": str(item.get("Description", "") or item.get("Наименование", "")),
                "ref": str(item.get("Ref_Key", ""))
            })
        result = {"items": result_items, "count": len(result_items)}
        set_cache(cache_key, result)
        return result
    except Exception as e:
        return {"items": [], "count": 0, "error": str(e)}

@app.get("/api/cars")
async def get_cars(limit: int = 200):
    """Get cars catalog with details"""
    cache_key = f"cars_{limit}"
    cached = get_cache(cache_key)
    if cached:
        return cached
    try:
        data = await fetch_odata(f"Catalog_Автомобили?$top={limit}&$format=json")
        if "error" in data:
            return {"cars": [], "count": 0, "error": data["error"]}
        items = data.get("value", [])
        cars = []
        for item in items:
            cars.append({
                "code": str(item.get("Code", "")),
                "name": str(item.get("Description", "")),
                "vin": str(item.get("VIN", "") or item.get("ВИН", "") or ""),
                "plate": str(item.get("ГосНомер", "") or item.get("ГосударственныйНомер", "") or item.get("РегистрационныйНомер", "") or ""),
                "owner": str(item.get("Владелец", "") or item.get("Owner_Key", "") or ""),
                "ref": str(item.get("Ref_Key", ""))
            })
        result = {"cars": cars, "count": len(cars)}
        set_cache(cache_key, result)
        return result
    except Exception as e:
        return {"cars": [], "count": 0, "error": str(e)}

@app.get("/api/client/{client_ref}/cars")
async def get_client_cars(client_ref: str):
    """Get cars owned by a specific client"""
    try:
        # Search cars by owner (Поставщик_Key in Альфа-Авто)
        data = await fetch_odata(f"Catalog_Автомобили?$filter=Поставщик_Key eq guid'{client_ref}'&$top=100&$format=json")
        if "error" in data:
            return {"cars": [], "count": 0, "error": data.get("error", "Unknown error")}

        items = data.get("value", [])
        cars = []
        for item in items:
            cars.append({
                "code": str(item.get("Code", "")),
                "name": str(item.get("Description", "")),
                "vin": str(item.get("VIN", "") or item.get("ВИН", "") or ""),
                "plate": str(item.get("ГосНомер", "") or item.get("ГосударственныйНомер", "") or item.get("РегистрационныйНомер", "") or ""),
                "ref": str(item.get("Ref_Key", ""))
            })
        return {"cars": cars, "count": len(cars), "client_ref": client_ref}
    except Exception as e:
        return {"cars": [], "count": 0, "error": str(e)}

@app.get("/api/search")
async def search(q: str):
    """Universal search by license plate, VIN, name, phone - searches directly in 1C"""
    if not q or len(q) < 2:
        return {"results": [], "query": q}

    results = []

    # Search clients directly in 1C using filter
    try:
        # OData filter for substring search
        clients_data = await fetch_odata(f"Catalog_Контрагенты?$filter=substringof('{q}', Description) or substringof('{q}', Code)&$top=20&$format=json")
        if clients_data.get("value"):
            for item in clients_data["value"]:
                results.append({
                    "type": "client",
                    "code": str(item.get("Code", "")).strip(),
                    "name": str(item.get("Description", "")),
                    "phone": "",
                    "ref": str(item.get("Ref_Key", ""))
                })
    except:
        pass

    # Search cars directly in 1C
    try:
        cars_data = await fetch_odata(f"Catalog_Автомобили?$filter=substringof('{q.upper()}', VIN) or substringof('{q}', Description)&$top=20&$format=json")
        if cars_data.get("value"):
            for item in cars_data["value"]:
                results.append({
                    "type": "car",
                    "code": str(item.get("Code", "")),
                    "name": str(item.get("Description", "")),
                    "plate": str(item.get("ГосНомер", "") or ""),
                    "vin": str(item.get("VIN", "") or ""),
                    "owner_key": str(item.get("Поставщик_Key", "") or ""),
                    "ref": str(item.get("Ref_Key", ""))
                })
    except:
        pass

    # Search orders by number
    try:
        orders_data = await fetch_odata(f"Document_ЗаказНаряд?$filter=substringof('{q}', Number)&$top=10&$orderby=Date desc&$format=json")
        if orders_data.get("value"):
            for item in orders_data["value"]:
                results.append({
                    "type": "order",
                    "number": str(item.get("Number", "")),
                    "date": str(item.get("Date", ""))[:10] if item.get("Date") else "",
                    "sum": float(item.get("СуммаДокумента", 0) or 0),
                    "status": "Проведен" if item.get("Posted") else "Черновик",
                    "ref": str(item.get("Ref_Key", ""))
                })
    except:
        pass

    return {"results": results[:50], "query": q, "total": len(results)}

@app.get("/api/client/{ref_key}")
async def get_client_details(ref_key: str):
    """Get client with their cars and orders"""
    try:
        # Get client info
        client_data = await fetch_odata(f"Catalog_Контрагенты(guid'{ref_key}')?$format=json")
        if "error" in client_data:
            return {"error": client_data["error"]}

        # Extract contact info
        phone = ""
        address = ""
        contact_info = client_data.get("КонтактнаяИнформация", [])
        for ci in contact_info:
            ci_type = ci.get("Тип", "")
            if ci_type == "Телефон" and ci.get("НомерТелефона"):
                phone = ci.get("НомерТелефона", "")
            if ci_type == "Адрес" and not address:
                address = ci.get("Представление", "")

        client = {
            "code": str(client_data.get("Code", "")).strip(),
            "name": str(client_data.get("Description", "")),
            "phone": phone,
            "address": address,
            "ref": str(client_data.get("Ref_Key", ""))
        }

        # Get client's cars
        cars = []
        try:
            cars_data = await fetch_odata(f"Catalog_Автомобили?$filter=Поставщик_Key eq guid'{ref_key}'&$format=json")
            if cars_data.get("value"):
                for item in cars_data["value"]:
                    cars.append({
                        "code": str(item.get("Code", "")),
                        "name": str(item.get("Description", "")),
                        "plate": str(item.get("ГосНомер", "") or ""),
                        "vin": str(item.get("VIN", "") or "")
                    })
        except:
            pass

        # Get client's orders from 1C
        orders = []
        try:
            orders_data = await fetch_odata(f"Document_ЗаказНаряд?$filter=Контрагент_Key eq guid'{ref_key}'&$orderby=Date desc&$top=50&$format=json")
            if orders_data.get("value"):
                for item in orders_data["value"]:
                    orders.append({
                        "number": str(item.get("Number", "")),
                        "date": str(item.get("Date", ""))[:10] if item.get("Date") else "",
                        "sum": float(item.get("СуммаДокумента", 0) or 0),
                        "status": "Проведен" if item.get("Posted", False) else "Черновик"
                    })
        except:
            pass

        # Also search in historical orders by client code
        client_code = client["code"]
        for hist_order in ORDERS_HISTORY:
            if hist_order.get("client_code") == client_code:
                # Check if not already in orders list
                if not any(o["number"] == hist_order["number"] for o in orders):
                    orders.append({
                        "number": hist_order.get("number", ""),
                        "date": hist_order.get("date", ""),
                        "sum": float(hist_order.get("sum", 0)),
                        "status": "Проведен" if hist_order.get("posted") else "Черновик",
                        "comment": hist_order.get("comment", "")
                    })

        # Sort orders by sum descending
        orders.sort(key=lambda x: x.get("sum", 0), reverse=True)

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

@app.post("/api/clients")
async def create_client(client: dict):
    """Create client via OData"""
    try:
        client_data = {
            "Description": client.get("name", ""),
            "НаименованиеПолное": client.get("name", ""),
        }

        result = await fetch_odata("Catalog_Контрагенты", method="POST", data=client_data)
        if "error" in result:
            return {"success": False, "error": result["error"]}

        clear_cache("clients")
        return {
            "success": True,
            "code": result.get("Code", ""),
            "ref": result.get("Ref_Key", ""),
            "message": "Клиент создан"
        }
    except Exception as e:
        return {"success": False, "error": str(e)}

@app.post("/api/cars")
async def create_car(car: dict):
    """Create car via OData"""
    try:
        # Prepare car data
        car_data = {
            "Description": car.get("name", ""),
            "VIN": car.get("vin", ""),
            "НаименованиеПолное": car.get("name", ""),
        }

        # If owner specified, link to counterparty
        if car.get("owner_key"):
            car_data["Поставщик_Key"] = car.get("owner_key")

        # Create via OData
        result = await fetch_odata("Catalog_Автомобили", method="POST", data=car_data)
        if "error" in result:
            return {"success": False, "error": result["error"]}

        clear_cache("cars")
        return {
            "success": True,
            "code": result.get("Code", ""),
            "ref": result.get("Ref_Key", ""),
            "message": "Автомобиль создан"
        }
    except Exception as e:
        return {"success": False, "error": str(e)}

@app.get("/api/stats")
async def get_stats():
    """Get dashboard statistics"""
    try:
        # Get orders
        orders_data = await fetch_odata("Document_ЗаказНаряд?$top=500&$orderby=Date desc&$format=json")
        orders = orders_data.get("value", [])

        # Today's date
        today = datetime.now().strftime("%Y-%m-%d")

        # Calculate stats
        orders_today = 0
        sum_today = 0
        in_progress = 0
        total_sum = 0

        for order in orders:
            order_date = str(order.get("Date", ""))[:10]
            order_sum = float(order.get("СуммаДокумента", 0) or 0)
            posted = order.get("Posted", False)

            total_sum += order_sum

            if order_date == today:
                orders_today += 1
                sum_today += order_sum

            if not posted:
                in_progress += 1

        # Count clients and cars
        clients_count = 0
        cars_count = 0
        try:
            clients_resp = await fetch_odata("Catalog_Контрагенты/$count")
            if isinstance(clients_resp, int):
                clients_count = clients_resp
            elif isinstance(clients_resp, str):
                clients_count = int(clients_resp)
        except:
            pass

        try:
            cars_resp = await fetch_odata("Catalog_Автомобили/$count")
            if isinstance(cars_resp, int):
                cars_count = cars_resp
            elif isinstance(cars_resp, str):
                cars_count = int(cars_resp)
        except:
            pass

        return {
            "orders_today": orders_today,
            "sum_today": sum_today,
            "in_progress": in_progress,
            "total_orders": len(orders),
            "total_sum": total_sum,
            "clients_count": clients_count,
            "cars_count": cars_count
        }
    except Exception as e:
        return {"error": str(e)}

@app.post("/api/orders")
async def create_order(order: dict):
    """Create order via OData with works and parts"""
    try:
        # Correct GUID values for ООО Сервис-Авто organization
        DEFAULT_ORG = "39b4c1f1-fa7c-11e5-9841-6cf049a63e1b"
        DEFAULT_DIVISION = "39b4c1f0-fa7c-11e5-9841-6cf049a63e1b"
        DEFAULT_PRICE_TYPE = "65ce4042-fa7c-11e5-9841-6cf049a63e1b"  # Основной тип цен продажи
        DEFAULT_PRICE_TYPE_WORKS = "c93d5c5a-1928-11e6-a20f-6cf049a63e1b"  # Тип цен авторабот
        DEFAULT_REPAIR_TYPE = "7d9f8931-1a7f-11e6-bee5-20689d8f1e0d"
        DEFAULT_STATUS = "6bd193fc-fa7c-11e5-9841-6cf049a63e1b"  # Заявка
        DEFAULT_WORKSHOP = "65ce404a-fa7c-11e5-9841-6cf049a63e1b"  # Основной цех
        DEFAULT_AUTHOR = "39b4c1f2-fa7c-11e5-9841-6cf049a63e1b"
        DEFAULT_CURRENCY = "6bd1932d-fa7c-11e5-9841-6cf049a63e1b"
        DEFAULT_OPERATION = "530d99ea-fa7c-11e5-9841-6cf049a63e1b"
        DEFAULT_WAREHOUSE = "65ce4049-fa7c-11e5-9841-6cf049a63e1b"
        DEFAULT_REPAIR_ORDER = "c7194270-d152-11e8-87a5-f46d0425712d"
        DEFAULT_VAT = "6bd192f4-fa7c-11e5-9841-6cf049a63e1b"  # 18%
        DEFAULT_NORMHOUR = "c93d5c5b-1928-11e6-a20f-6cf049a63e1b"  # Стандартный
        DEFAULT_MASTER = "c94de32f-fa7c-11e5-9841-6cf049a63e1b"  # Мастер по умолчанию
        DEFAULT_MANAGER = "c94de33e-fa7c-11e5-9841-6cf049a63e1b"  # Менеджер по умолчанию

        # Prepare OData document with ALL required fields
        doc_data = {
            "Date": datetime.now().strftime("%Y-%m-%dT%H:%M:%S"),
            "Организация_Key": DEFAULT_ORG,
            "ПодразделениеКомпании_Key": DEFAULT_DIVISION,
            "ТипЦен_Key": DEFAULT_PRICE_TYPE,
            "ТипЦенРабот_Key": DEFAULT_PRICE_TYPE_WORKS,
            "ВидРемонта_Key": DEFAULT_REPAIR_TYPE,
            "Состояние_Key": DEFAULT_STATUS,
            "Цех_Key": DEFAULT_WORKSHOP,
            "Автор_Key": DEFAULT_AUTHOR,
            "Мастер_Key": DEFAULT_MASTER,
            "Менеджер_Key": DEFAULT_MANAGER,
            "ВалютаДокумента_Key": DEFAULT_CURRENCY,
            "ХозОперация_Key": DEFAULT_OPERATION,
            "СкладКомпании_Key": DEFAULT_WAREHOUSE,
            "СводныйРемонтныйЗаказ_Key": DEFAULT_REPAIR_ORDER,
            "КурсДокумента": 1,
            "КурсВалютыВзаиморасчетов": 1,
            "КурсВалютыУпр": 90.0945,
            "СпособЗачетаАвансов": "НеЗачитывать",
            "РегламентированныйУчет": True,
            "ЗакрыватьЗаказыТолькоПоДанномуЗаказНаряду": True,
            "ВерсияОбъекта": "02.00",
        }

        # Map client - support both client_key (ref) and client_code
        client_ref = order.get("client_key")  # Frontend sends ref directly
        if not client_ref and order.get("client_code"):
            client_data = await fetch_odata(f"Catalog_Контрагенты?$filter=Code eq '{order['client_code']}'&$format=json")
            if not client_data.get("value"):
                return {"success": False, "error": f"Клиент с кодом '{order['client_code']}' не найден"}
            client_ref = client_data["value"][0].get("Ref_Key")

        if not client_ref:
            return {"success": False, "error": "Не указан клиент (client_key или client_code)"}

        doc_data["Контрагент_Key"] = client_ref

        # Get client's contract
        contract_data = await fetch_odata(f"Catalog_ДоговорыВзаиморасчетов?$filter=Owner_Key eq guid'{client_ref}'&$top=1&$format=json")
        if contract_data.get("value"):
            doc_data["ДоговорВзаиморасчетов_Key"] = contract_data["value"][0].get("Ref_Key")
        else:
            # Create contract for client if not exists
            client_info = await fetch_odata(f"Catalog_Контрагенты(guid'{client_ref}')?$select=Description&$format=json")
            client_name = client_info.get("Description", "Клиент")[:30] if client_info else "Клиент"
            contract_doc = {
                "Owner_Key": client_ref,
                "Description": f"Договор сервиса {client_name}",
                "ВалютаВзаиморасчетов_Key": DEFAULT_CURRENCY,
                "ВидДоговора": "Прочее",
                "ДатаНачала": datetime.now().strftime("%Y-%m-%dT00:00:00"),
                "Основной": True,
                "ДляАвтосервиса": True,
            }
            new_contract = await fetch_odata("Catalog_ДоговорыВзаиморасчетов?$format=json", method="POST", data=contract_doc)
            if new_contract.get("Ref_Key"):
                doc_data["ДоговорВзаиморасчетов_Key"] = new_contract["Ref_Key"]
                print(f"Created new contract for client: {new_contract['Ref_Key']}")

        # Map car - support both car_key (ref) and car_code
        car_ref = order.get("car_key")
        if not car_ref and order.get("car_code"):
            car_data = await fetch_odata(f"Catalog_Автомобили?$filter=Code eq '{order['car_code']}'&$format=json")
            if car_data.get("value"):
                car_ref = car_data["value"][0].get("Ref_Key")
        if car_ref:
            # Машина добавляется в табличную часть Автомобили, не в шапку
            doc_data["Автомобили"] = [{"LineNumber": "1", "Автомобиль_Key": car_ref}]

        # Map other fields from UI
        if order.get("comment"):
            doc_data["ОписаниеПричиныОбращения"] = order["comment"]
        if order.get("mileage"):
            doc_data["Пробег"] = str(order["mileage"])

        # Map workshop - support both key and code
        workshop_ref = order.get("workshop_key")
        if not workshop_ref and order.get("workshop_code"):
            workshop_data = await fetch_odata(f"Catalog_Цеха?$filter=Code eq '{order['workshop_code']}'&$format=json")
            if workshop_data.get("value"):
                workshop_ref = workshop_data["value"][0].get("Ref_Key")
        if workshop_ref:
            doc_data["Цех_Key"] = workshop_ref

        # Map master - support both key and code
        master_ref = order.get("master_key")
        if not master_ref and order.get("master_code"):
            master_data = await fetch_odata(f"Catalog_Сотрудники?$filter=Code eq '{order['master_code']}'&$format=json")
            if master_data.get("value"):
                master_ref = master_data["value"][0].get("Ref_Key")
        if master_ref:
            doc_data["Мастер_Key"] = master_ref

        # Map manager by code (legacy)
        if order.get("manager_code"):
            manager_data = await fetch_odata(f"Catalog_Сотрудники?$filter=Code eq '{order['manager_code']}'&$format=json")
            if manager_data.get("value"):
                doc_data["Менеджер_Key"] = manager_data["value"][0].get("Ref_Key")

        # Map repair type - support both key and code
        repair_ref = order.get("repair_type_key")
        if not repair_ref and order.get("repair_type_code"):
            repair_data = await fetch_odata(f"Catalog_ВидыРемонта?$filter=Code eq '{order['repair_type_code']}'&$format=json")
            if repair_data.get("value"):
                repair_ref = repair_data["value"][0].get("Ref_Key")
        if repair_ref:
            doc_data["ВидРемонта_Key"] = repair_ref

        # Add works (Автоработы) to tabular part
        if order.get("works"):
            autoworks = []
            for idx, work in enumerate(order["works"], 1):
                # Support both work_key (from frontend) and work_ref (legacy)
                work_ref = work.get("work_key") or work.get("work_ref")
                qty = work.get("qty", work.get("quantity", 1))
                price = work.get("price", 0)

                # Fetch price from catalog if not provided
                if work_ref and price == 0:
                    work_data = await fetch_odata(f"Catalog_Автоработы(guid'{work_ref}')?$select=Цена&$format=json")
                    if work_data and work_data.get("Цена"):
                        price = float(work_data.get("Цена", 0))

                total = work.get("sum") if work.get("sum") else qty * price

                work_row = {
                    "LineNumber": str(idx),
                    "Авторабота_Key": work_ref,
                    "Количество": qty,
                    "Нормочас_Key": work.get("normhour_ref", DEFAULT_NORMHOUR),
                    "Коэффициент": work.get("coefficient", 1),
                    "Цена": price,
                    "Сумма": total,
                    "СтавкаНДС_Key": work.get("vat_ref", DEFAULT_VAT),
                    "СуммаНДС": work.get("vat_sum", 0),
                    "СуммаВсего": total,
                }
                autoworks.append(work_row)
            doc_data["Автоработы"] = autoworks

        # Add parts (Товары) to tabular part
        if order.get("parts"):
            goods = []
            for idx, part in enumerate(order["parts"], 1):
                # Support both part_key (from frontend) and nomenclature_ref (legacy)
                nom_ref = part.get("part_key") or part.get("nomenclature_ref")
                qty = part.get("qty", part.get("quantity", 1))
                price = part.get("price", 0)
                discount = part.get("discount", 0)

                # Get unit of measurement and price from nomenclature
                unit_ref = part.get("unit_ref")
                part_vat = part.get("vat_ref", DEFAULT_VAT)
                if nom_ref:
                    nom_data = await fetch_odata(f"Catalog_Номенклатура(guid'{nom_ref}')?$select=ОсновнаяЕдиницаИзмерения_Key,СтавкаНДС_Key,Цена&$format=json")
                    if nom_data:
                        if not unit_ref:
                            unit_ref = nom_data.get("ОсновнаяЕдиницаИзмерения_Key", "00000000-0000-0000-0000-000000000000")
                        if not part.get("vat_ref"):
                            part_vat = nom_data.get("СтавкаНДС_Key", DEFAULT_VAT)
                        # Fetch price from catalog if not provided
                        if price == 0 and nom_data.get("Цена"):
                            price = float(nom_data.get("Цена", 0))

                total = part.get("sum") if part.get("sum") else qty * price * (1 - discount / 100)

                part_row = {
                    "LineNumber": str(idx),
                    "Номенклатура_Key": nom_ref,
                    "Количество": qty,
                    "ЕдиницаИзмерения_Key": unit_ref or "00000000-0000-0000-0000-000000000000",
                    "Коэффициент": part.get("coefficient", 1),
                    "Цена": price,
                    "Сумма": total,
                    "СтавкаНДС_Key": part_vat,
                    "СуммаНДС": part.get("vat_sum", 0),
                    "ПроцентСкидки": discount,
                    "СуммаВсего": total,
                    "СкладКомпании_Key": part.get("warehouse_ref", DEFAULT_WAREHOUSE),
                    "ХарактеристикаНоменклатуры_Key": part.get("characteristic_ref", "00000000-0000-0000-0000-000000000000"),
                }
                goods.append(part_row)
            doc_data["Товары"] = goods

        # Create document
        print(f"Creating order with data: {doc_data}")
        result = await fetch_odata("Document_ЗаказНаряд?$format=json", method="POST", data=doc_data)
        print(f"OData result: {result}")

        if "error" in result:
            return {"success": False, "error": result["error"]}
        if "odata.error" in result:
            return {"success": False, "error": result.get("odata.error", {}).get("message", {}).get("value", "OData error")}

        clear_cache("orders")
        return {
            "success": True,
            "number": result.get("Number", result.get("Номер", "")),
            "ref": result.get("Ref_Key", ""),
            "message": "Заказ создан через OData",
            "works_count": len(order.get("works", [])),
            "parts_count": len(order.get("parts", []))
        }
    except Exception as e:
        return {"success": False, "error": str(e)}

@app.put("/api/orders/{order_number}")
async def update_order(order_number: str, order: OrderUpdate):
    return {"error": "Update via OData not implemented yet"}

@app.get("/ui", response_class=HTMLResponse)
async def ui():
    return """
<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>TIPO-STO</title>
    <style>
        * { box-sizing: border-box; margin: 0; padding: 0; }
        body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #f5f5f5; }
        .header { background: linear-gradient(135deg, #1976D2, #2196F3); color: white; padding: 15px 20px; display: flex; justify-content: space-between; align-items: center; box-shadow: 0 2px 8px rgba(0,0,0,0.15); }
        .header h1 { font-size: 22px; font-weight: 700; letter-spacing: -0.5px; }
        .header h1 span { font-weight: 400; opacity: 0.9; font-size: 14px; margin-left: 10px; }
        .header-right { display: flex; gap: 10px; align-items: center; }
        .refresh-btn { background: rgba(255,255,255,0.2); border: none; color: white; padding: 8px 16px; border-radius: 6px; cursor: pointer; }
        .container { max-width: 1200px; margin: 15px auto; padding: 0 15px; }
        .search-container { position: relative; margin-bottom: 15px; }
        .search-box { width: 100%; padding: 12px 16px; border: 2px solid #E0E0E0; border-radius: 8px; font-size: 16px; }
        .search-box:focus { border-color: #2196F3; outline: none; }
        .search-results { position: absolute; top: 100%; left: 0; right: 0; background: white; border: 2px solid #2196F3; border-top: none; border-radius: 0 0 8px 8px; max-height: 400px; overflow-y: auto; z-index: 100; display: none; box-shadow: 0 4px 12px rgba(0,0,0,0.15); }
        .search-results.active { display: block; }
        .search-result { padding: 12px 16px; cursor: pointer; border-bottom: 1px solid #f0f0f0; }
        .search-result:hover { background: #E3F2FD; }
        .search-result-type { font-size: 10px; text-transform: uppercase; color: #888; margin-bottom: 4px; }
        .search-result-title { font-weight: 600; color: #333; }
        .search-result-subtitle { font-size: 13px; color: #666; margin-top: 2px; }
        .search-result-car .search-result-type { color: #2196F3; }
        .search-result-client .search-result-type { color: #4CAF50; }
        .filters-panel { background: white; border-radius: 10px; padding: 15px; margin-bottom: 15px; box-shadow: 0 1px 3px rgba(0,0,0,0.1); }
        .filters-row { display: flex; gap: 12px; flex-wrap: wrap; align-items: flex-end; margin-bottom: 10px; }
        .filters-row:last-child { margin-bottom: 0; }
        .filter-group { display: flex; flex-direction: column; gap: 4px; min-width: 120px; }
        .filter-group label { font-size: 11px; color: #888; text-transform: uppercase; font-weight: 500; }
        .filter-select { padding: 8px 12px; border: 1px solid #E0E0E0; border-radius: 6px; font-size: 13px; background: white; cursor: pointer; }
        .filter-select:focus { outline: none; border-color: #2196F3; }
        .filter-input { padding: 8px 12px; border: 1px solid #E0E0E0; border-radius: 6px; font-size: 13px; }
        .filter-input:focus { outline: none; border-color: #2196F3; }
        .btn-sm { padding: 8px 14px; font-size: 12px; }
        .tabs { display: flex; gap: 8px; margin-bottom: 15px; overflow-x: auto; }
        .tab { padding: 10px 20px; background: white; border: none; cursor: pointer; border-radius: 8px; font-size: 14px; white-space: nowrap; }
        .tab.active { background: #2196F3; color: white; }
        .card { background: white; border-radius: 10px; padding: 15px; margin-bottom: 12px; box-shadow: 0 1px 3px rgba(0,0,0,0.1); cursor: pointer; transition: all 0.2s; }
        .card:hover { box-shadow: 0 3px 8px rgba(0,0,0,0.15); }
        .card-header { display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 8px; }
        .card-title { font-size: 16px; font-weight: 600; color: #333; }
        .card-subtitle { color: #666; font-size: 13px; margin-top: 2px; }
        .card-car { color: #2196F3; font-size: 13px; margin-top: 4px; }
        .card-plate { background: #E3F2FD; color: #1976D2; padding: 4px 8px; border-radius: 4px; font-weight: 600; font-size: 14px; }
        .badge { padding: 4px 10px; border-radius: 12px; font-size: 11px; font-weight: 500; }
        .badge-work { background: #FFF3E0; color: #F57C00; }
        .badge-done { background: #E8F5E9; color: #2E7D32; }
        .badge-new { background: #E3F2FD; color: #1976D2; }
        .info-row { display: flex; justify-content: space-between; align-items: center; margin-top: 10px; padding-top: 10px; border-top: 1px solid #f0f0f0; }
        .info-left { color: #888; font-size: 13px; }
        .sum { font-size: 16px; font-weight: 600; color: #2196F3; }
        .stats { display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px; margin-bottom: 20px; }
        .stat-card { background: white; padding: 18px 15px; border-radius: 12px; text-align: center; cursor: pointer; transition: all 0.2s; border-left: 4px solid #2196F3; }
        .stat-card:hover { box-shadow: 0 4px 12px rgba(0,0,0,0.15); transform: translateY(-2px); }
        .stat-card.green { border-left-color: #4CAF50; }
        .stat-card.orange { border-left-color: #FF9800; }
        .stat-card.purple { border-left-color: #9C27B0; }
        .stat-icon { font-size: 28px; margin-bottom: 8px; }
        .stat-value { font-size: 28px; font-weight: 700; color: #333; }
        .stat-label { color: #888; font-size: 12px; margin-top: 4px; }
        .quick-actions { display: flex; gap: 10px; margin-bottom: 20px; flex-wrap: wrap; }
        .quick-btn { padding: 12px 20px; border: none; border-radius: 8px; cursor: pointer; font-size: 14px; font-weight: 500; display: flex; align-items: center; gap: 8px; transition: all 0.2s; }
        .quick-btn:hover { transform: translateY(-1px); box-shadow: 0 3px 8px rgba(0,0,0,0.2); }
        .quick-btn-primary { background: linear-gradient(135deg, #2196F3, #1976D2); color: white; }
        .quick-btn-success { background: linear-gradient(135deg, #4CAF50, #388E3C); color: white; }
        .quick-btn-warning { background: linear-gradient(135deg, #FF9800, #F57C00); color: white; }
        .btn { padding: 10px 20px; border: none; border-radius: 8px; cursor: pointer; font-size: 14px; }
        .btn-primary { background: #2196F3; color: white; }
        .btn-success { background: #4CAF50; color: white; }
        .btn-secondary { background: #E0E0E0; color: #333; }
        .modal { display: none; position: fixed; top: 0; left: 0; width: 100%; height: 100%; background: rgba(0,0,0,0.5); z-index: 1000; }
        .modal.active { display: flex; align-items: center; justify-content: center; }
        .modal-content { background: white; border-radius: 12px; padding: 20px; width: 95%; max-width: 600px; max-height: 90vh; overflow-y: auto; }
        .modal-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px; }
        .modal-title { font-size: 20px; font-weight: 600; }
        .close-btn { background: none; border: none; font-size: 24px; cursor: pointer; color: #888; }
        .form-group { margin-bottom: 16px; }
        .form-label { display: block; margin-bottom: 6px; font-weight: 500; font-size: 14px; color: #555; }
        .form-input, .form-select, .form-textarea { width: 100%; padding: 10px 12px; border: 2px solid #E0E0E0; border-radius: 8px; font-size: 15px; }
        .form-input:focus, .form-select:focus, .form-textarea:focus { border-color: #2196F3; outline: none; }
        .form-textarea { min-height: 80px; resize: vertical; }
        .form-row { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }
        .form-actions { display: flex; gap: 10px; justify-content: flex-end; margin-top: 20px; }
        .alert { padding: 12px 16px; border-radius: 8px; margin-bottom: 15px; font-size: 14px; }
        .alert-success { background: #E8F5E9; color: #2E7D32; }
        .alert-error { background: #FFEBEE; color: #C62828; }
        .loading { text-align: center; padding: 40px; color: #888; }
        .spinner { display: inline-block; width: 30px; height: 30px; border: 3px solid #E0E0E0; border-top-color: #2196F3; border-radius: 50%; animation: spin 1s linear infinite; }
        @keyframes spin { to { transform: rotate(360deg); } }
        .client-search { position: relative; }
        .client-list { position: absolute; top: 100%; left: 0; right: 0; background: white; border: 2px solid #E0E0E0; border-top: none; border-radius: 0 0 8px 8px; max-height: 200px; overflow-y: auto; z-index: 10; display: none; }
        .client-list.active { display: block; }
        .client-item { padding: 10px 12px; cursor: pointer; border-bottom: 1px solid #f0f0f0; }
        .client-item:hover { background: #f5f5f5; }
        .client-item:last-child { border-bottom: none; }
        .detail-section { margin-bottom: 20px; }
        .detail-section h3 { font-size: 14px; color: #888; margin-bottom: 10px; text-transform: uppercase; }
        .detail-row { display: flex; justify-content: space-between; padding: 8px 0; border-bottom: 1px solid #f0f0f0; }
        .detail-label { color: #666; }
        .detail-value { font-weight: 500; color: #333; }
        .mini-card { background: #f5f5f5; border-radius: 8px; padding: 10px; margin-bottom: 8px; }
        .mini-card-title { font-weight: 600; }
        .mini-card-subtitle { font-size: 12px; color: #666; }
        @media (max-width: 600px) {
            .stats { grid-template-columns: repeat(2, 1fr); }
        }
    </style>
</head>
<body>
    <div class="header">
        <h1>TIPO-STO <span>CRM для автосервиса</span></h1>
        <div class="header-right">
            <span id="status"></span>
            <button class="refresh-btn" onclick="loadData()">Обновить</button>
        </div>
    </div>
    <div class="container">
        <div id="alert"></div>
        <div class="quick-actions">
            <button class="quick-btn quick-btn-primary" onclick="openCreateModal()">+ Новый заказ-наряд</button>
            <button class="quick-btn quick-btn-success" onclick="openClientModal()">+ Новый клиент</button>
            <button class="quick-btn quick-btn-warning" onclick="openCarModal()">+ Добавить авто</button>
        </div>
        <div class="stats" id="stats"><div class="loading"><div class="spinner"></div><p>Загрузка...</p></div></div>
        <div class="search-container">
            <input type="text" class="search-box" id="searchBox" placeholder="Поиск по госномеру, VIN, имени клиента..." oninput="globalSearch()">
            <div class="search-results" id="searchResults"></div>
        </div>
        <div class="tabs">
            <button class="tab active" onclick="showTab('orders')">Заказ-наряды</button>
            <button class="tab" onclick="showTab('clients')">Клиенты</button>
            <button class="tab" onclick="showTab('cars')">Автомобили</button>
        </div>
        <div id="ordersSection">
            <div class="filters-panel" id="ordersFilters">
                <div class="filters-row">
                    <div class="filter-group">
                        <label>Статус</label>
                        <select class="filter-select" id="filterStatus" onchange="applyOrderFilters()">
                            <option value="">Все</option>
                            <option value="draft">Черновики</option>
                            <option value="done">Проведены</option>
                        </select>
                    </div>
                    <div class="filter-group">
                        <label>Период</label>
                        <select class="filter-select" id="filterPeriod" onchange="applyOrderFilters()">
                            <option value="">Все время</option>
                            <option value="today">Сегодня</option>
                            <option value="week">Неделя</option>
                            <option value="month">Месяц</option>
                            <option value="quarter">Квартал</option>
                            <option value="year">Год</option>
                        </select>
                    </div>
                    <div class="filter-group">
                        <label>Дата с</label>
                        <input type="date" class="filter-input" id="filterDateFrom" onchange="applyOrderFilters()">
                    </div>
                    <div class="filter-group">
                        <label>Дата по</label>
                        <input type="date" class="filter-input" id="filterDateTo" onchange="applyOrderFilters()">
                    </div>
                </div>
                <div class="filters-row">
                    <div class="filter-group">
                        <label>Клиент</label>
                        <input type="text" class="filter-input" id="filterClient" placeholder="Имя клиента..." oninput="applyOrderFiltersDebounced()">
                    </div>
                    <div class="filter-group">
                        <label>Автомобиль</label>
                        <input type="text" class="filter-input" id="filterCar" placeholder="Марка или номер..." oninput="applyOrderFiltersDebounced()">
                    </div>
                    <div class="filter-group">
                        <label>Сумма от</label>
                        <input type="number" class="filter-input" id="filterSumFrom" placeholder="0" oninput="applyOrderFiltersDebounced()">
                    </div>
                    <div class="filter-group">
                        <label>Сумма до</label>
                        <input type="number" class="filter-input" id="filterSumTo" placeholder="999999" oninput="applyOrderFiltersDebounced()">
                    </div>
                    <div class="filter-group">
                        <label>Показать</label>
                        <select class="filter-select" id="filterOrdersLimit" onchange="applyOrderFilters()">
                            <option value="100">100 записей</option>
                            <option value="500" selected>500 записей</option>
                            <option value="1000">1000 записей</option>
                            <option value="3000">Все (до 3000)</option>
                        </select>
                    </div>
                    <div class="filter-group" style="align-self:flex-end;">
                        <button class="btn btn-secondary btn-sm" onclick="resetOrderFilters()">Сбросить</button>
                    </div>
                    <span id="ordersCount" style="margin-left:auto;align-self:flex-end;color:#666;font-size:13px;font-weight:500;"></span>
                </div>
            </div>
            <div id="orders"><div class="loading"><div class="spinner"></div></div></div>
        </div>
        <div id="clientsSection" style="display:none">
            <div class="filters-panel" id="clientsFilters">
                <div class="filters-row">
                    <div class="filter-group">
                        <label>Поиск</label>
                        <input type="text" class="filter-input" id="filterClientName" placeholder="Имя, код, телефон..." oninput="applyClientFiltersDebounced()">
                    </div>
                    <div class="filter-group">
                        <label>Сортировка</label>
                        <select class="filter-select" id="filterClientSort" onchange="applyClientFilters()">
                            <option value="code">По коду (новые первые)</option>
                            <option value="name">По имени А-Я</option>
                            <option value="name_desc">По имени Я-А</option>
                        </select>
                    </div>
                    <div class="filter-group">
                        <label>Тип</label>
                        <select class="filter-select" id="filterClientType" onchange="applyClientFilters()">
                            <option value="">Все</option>
                            <option value="with_phone">С телефоном</option>
                            <option value="with_address">С адресом</option>
                        </select>
                    </div>
                    <div class="filter-group">
                        <label>Показать</label>
                        <select class="filter-select" id="filterClientsLimit" onchange="applyClientFilters()">
                            <option value="100">100 записей</option>
                            <option value="500" selected>500 записей</option>
                            <option value="1000">1000 записей</option>
                            <option value="5000">Все (до 5000)</option>
                        </select>
                    </div>
                    <div class="filter-group" style="align-self:flex-end;">
                        <button class="btn btn-secondary btn-sm" onclick="resetClientFilters()">Сбросить</button>
                    </div>
                    <span id="clientsCount" style="margin-left:auto;align-self:flex-end;color:#666;font-size:13px;font-weight:500;"></span>
                </div>
            </div>
            <div id="clients"></div>
        </div>
        <div id="carsSection" style="display:none">
            <div class="filters-panel" id="carsFilters">
                <div class="filters-row">
                    <div class="filter-group">
                        <label>Поиск</label>
                        <input type="text" class="filter-input" id="filterCarName" placeholder="Марка, модель..." oninput="applyCarFiltersDebounced()">
                    </div>
                    <div class="filter-group">
                        <label>Госномер</label>
                        <input type="text" class="filter-input" id="filterCarPlate" placeholder="А123БВ..." oninput="applyCarFiltersDebounced()">
                    </div>
                    <div class="filter-group">
                        <label>VIN</label>
                        <input type="text" class="filter-input" id="filterCarVin" placeholder="VIN код..." oninput="applyCarFiltersDebounced()">
                    </div>
                    <div class="filter-group">
                        <label>Тип</label>
                        <select class="filter-select" id="filterCarShow" onchange="applyCarFilters()">
                            <option value="">Все</option>
                            <option value="with_plate">С госномером</option>
                            <option value="with_vin">С VIN</option>
                            <option value="with_owner">С владельцем</option>
                        </select>
                    </div>
                    <div class="filter-group">
                        <label>Показать</label>
                        <select class="filter-select" id="filterCarsLimit" onchange="loadCarsWithFilters()">
                            <option value="200">200 записей</option>
                            <option value="500" selected>500 записей</option>
                            <option value="1000">1000 записей</option>
                            <option value="3000">Все (до 3000)</option>
                        </select>
                    </div>
                    <div class="filter-group" style="align-self:flex-end;">
                        <button class="btn btn-secondary btn-sm" onclick="resetCarFilters()">Сбросить</button>
                    </div>
                    <span id="carsCount" style="margin-left:auto;align-self:flex-end;color:#666;font-size:13px;font-weight:500;"></span>
                </div>
            </div>
            <div id="cars"></div>
        </div>
    </div>

    <div class="modal" id="createModal">
        <div class="modal-content">
            <div class="modal-header">
                <h2 class="modal-title">Новый заказ-наряд</h2>
                <button class="close-btn" onclick="closeModal('createModal')">&times;</button>
            </div>
            <form onsubmit="createOrder(event)">
                <div class="form-group client-search">
                    <label class="form-label">Контрагент (плательщик) *</label>
                    <input type="text" class="form-input" id="clientSearch" placeholder="Начните вводить имя..." oninput="searchClients()" onfocus="showClientList()" autocomplete="off">
                    <input type="hidden" id="clientCode">
                    <div class="client-list" id="clientList"></div>
                </div>
                <div class="form-group client-search">
                    <label class="form-label">Заказчик (если отличается)</label>
                    <input type="text" class="form-input" id="customerSearch" placeholder="Начните вводить имя..." oninput="searchCustomers()" onfocus="showCustomerList()" autocomplete="off">
                    <input type="hidden" id="customerCode">
                    <div class="client-list" id="customerList"></div>
                </div>
                <div class="form-group client-search">
                    <label class="form-label">Автомобиль</label>
                    <input type="text" class="form-input" id="carSearch" placeholder="Начните вводить марку/номер..." oninput="searchCars()" onfocus="showCarList()" autocomplete="off">
                    <input type="hidden" id="carCode">
                    <div class="client-list" id="carList"></div>
                </div>
                <div class="form-row">
                    <div class="form-group">
                        <label class="form-label">Пробег (км)</label>
                        <input type="number" class="form-input" id="mileageInput" placeholder="0">
                    </div>
                    <div class="form-group">
                        <label class="form-label">Вид ремонта</label>
                        <select class="form-select" id="repairTypeSelect"><option value="">Выберите...</option></select>
                    </div>
                </div>
                <div class="form-row">
                    <div class="form-group">
                        <label class="form-label">Мастер</label>
                        <select class="form-select" id="masterSelect"><option value="">Выберите...</option></select>
                    </div>
                    <div class="form-group">
                        <label class="form-label">Менеджер</label>
                        <select class="form-select" id="managerSelect"><option value="">Выберите...</option></select>
                    </div>
                </div>
                <div class="form-row">
                    <div class="form-group">
                        <label class="form-label">Цех</label>
                        <select class="form-select" id="workshopSelect"><option value="">Выберите...</option></select>
                    </div>
                    <div class="form-group">
                        <label class="form-label">Вид оплаты</label>
                        <select class="form-select" id="paymentTypeSelect"><option value="">Выберите...</option></select>
                    </div>
                </div>
                <div class="form-row">
                    <div class="form-group">
                        <label class="form-label">Дата начала</label>
                        <input type="datetime-local" class="form-input" id="dateStartInput">
                    </div>
                    <div class="form-group">
                        <label class="form-label">Дата окончания</label>
                        <input type="datetime-local" class="form-input" id="dateEndInput">
                    </div>
                </div>
                <div class="form-row">
                    <div class="form-group">
                        <label class="form-label">Сумма (руб)</label>
                        <input type="number" class="form-input" id="sumInput" placeholder="0" step="0.01">
                    </div>
                    <div class="form-group">
                        <label class="form-label">&nbsp;</label>
                    </div>
                </div>
                <div class="form-group">
                    <label class="form-label">Комментарий / Описание работ</label>
                    <textarea class="form-textarea" id="commentInput" placeholder="Опишите работы..."></textarea>
                </div>
                <div class="form-actions">
                    <button type="button" class="btn btn-secondary" onclick="closeModal('createModal')">Отмена</button>
                    <button type="submit" class="btn btn-success" id="createBtn">Создать</button>
                </div>
            </form>
        </div>
    </div>

    <div class="modal" id="viewModal">
        <div class="modal-content">
            <div class="modal-header">
                <h2 class="modal-title">Заказ-наряд <span id="viewNumber"></span></h2>
                <button class="close-btn" onclick="closeModal('viewModal')">&times;</button>
            </div>
            <div id="viewContent"></div>
        </div>
    </div>

    <div class="modal" id="clientModal">
        <div class="modal-content">
            <div class="modal-header">
                <h2 class="modal-title" id="clientModalTitle">Клиент</h2>
                <button class="close-btn" onclick="closeModal('clientModal')">&times;</button>
            </div>
            <div id="clientModalContent"><div class="loading"><div class="spinner"></div></div></div>
        </div>
    </div>

    <div class="modal" id="carModal">
        <div class="modal-content">
            <div class="modal-header">
                <h2 class="modal-title">Новый автомобиль</h2>
                <button class="close-btn" onclick="closeModal('carModal')">&times;</button>
            </div>
            <form onsubmit="createCar(event)">
                <div class="form-group">
                    <label class="form-label">Название (Марка Модель) *</label>
                    <input type="text" class="form-input" id="carNameInput" placeholder="Toyota Camry" required>
                </div>
                <div class="form-group">
                    <label class="form-label">VIN</label>
                    <input type="text" class="form-input" id="carVinInput" placeholder="JTDKN3DU5A0123456" maxlength="17">
                </div>
                <div class="form-group">
                    <label class="form-label">Госномер</label>
                    <input type="text" class="form-input" id="carPlateInput" placeholder="А123БВ777">
                </div>
                <div class="form-group client-search">
                    <label class="form-label">Владелец (клиент)</label>
                    <input type="text" class="form-input" id="carOwnerSearch" placeholder="Начните вводить имя..." oninput="searchCarOwners()" onfocus="showCarOwnerList()" autocomplete="off">
                    <input type="hidden" id="carOwnerKey">
                    <div class="client-list" id="carOwnerList"></div>
                </div>
                <div class="form-actions">
                    <button type="button" class="btn btn-secondary" onclick="closeModal('carModal')">Отмена</button>
                    <button type="submit" class="btn btn-success" id="createCarBtn">Создать</button>
                </div>
            </form>
        </div>
    </div>

    <div class="modal" id="orderDetailModal">
        <div class="modal-content">
            <div class="modal-header">
                <h2 class="modal-title">Заказ-наряд <span id="orderDetailNumber"></span></h2>
                <button class="close-btn" onclick="closeModal('orderDetailModal')">&times;</button>
            </div>
            <div id="orderDetailContent"></div>
        </div>
    </div>

    <div class="modal" id="newClientModal">
        <div class="modal-content">
            <div class="modal-header">
                <h2 class="modal-title">Новый клиент</h2>
                <button class="close-btn" onclick="closeModal('newClientModal')">&times;</button>
            </div>
            <form onsubmit="createNewClient(event)">
                <div class="form-group">
                    <label class="form-label">ФИО / Название организации *</label>
                    <input type="text" class="form-input" id="newClientName" placeholder="Иванов Иван Иванович" required>
                </div>
                <div class="form-group">
                    <label class="form-label">Телефон</label>
                    <input type="tel" class="form-input" id="newClientPhone" placeholder="+7 999 123-45-67">
                </div>
                <div class="form-actions">
                    <button type="button" class="btn btn-secondary" onclick="closeModal('newClientModal')">Отмена</button>
                    <button type="submit" class="btn btn-success" id="createClientBtn">Создать</button>
                </div>
            </form>
        </div>
    </div>

    <script>
        let clientsData = [], ordersData = [], carsData = [], carsFullData = [], repairTypesData = [], mastersData = [], workshopsData = [], paymentTypesData = [], currentTab = 'orders', searchQuery = '', searchTimeout = null;

        // Debounce таймеры
        let orderFilterTimeout = null;
        let clientFilterTimeout = null;
        let carFilterTimeout = null;

        // === ФИЛЬТРЫ ЗАКАЗОВ ===
        function applyOrderFilters() {
            clearTimeout(orderFilterTimeout);
            loadOrdersWithFilters();
        }

        function applyOrderFiltersDebounced() {
            clearTimeout(orderFilterTimeout);
            orderFilterTimeout = setTimeout(loadOrdersWithFilters, 400);
        }

        async function loadOrdersWithFilters() {
            document.getElementById('orders').innerHTML = '<div class="loading"><div class="spinner"></div><p>Загрузка из 1С...</p></div>';
            document.getElementById('ordersCount').textContent = 'Загрузка...';
            try {
                const params = new URLSearchParams();
                const status = document.getElementById('filterStatus').value;
                const period = document.getElementById('filterPeriod').value;
                const dateFrom = document.getElementById('filterDateFrom').value;
                const dateTo = document.getElementById('filterDateTo').value;
                const limit = document.getElementById('filterOrdersLimit').value || '500';

                if (status) params.append('status', status);
                if (period) params.append('period', period);
                if (dateFrom) params.append('date_from', dateFrom);
                if (dateTo) params.append('date_to', dateTo);
                params.append('limit', limit);

                const data = await fetch('/api/orders?' + params.toString()).then(r => r.json());
                ordersData = data.orders || [];

                // Локальная фильтрация по клиенту, авто, сумме
                const clientFilter = document.getElementById('filterClient').value.toLowerCase();
                const carFilter = document.getElementById('filterCar').value.toLowerCase();
                const sumFrom = parseFloat(document.getElementById('filterSumFrom').value) || 0;
                const sumTo = parseFloat(document.getElementById('filterSumTo').value) || Infinity;

                let filtered = ordersData;
                if (clientFilter) filtered = filtered.filter(x => x.client && x.client.toLowerCase().includes(clientFilter));
                if (carFilter) filtered = filtered.filter(x => x.car && x.car.toLowerCase().includes(carFilter));
                filtered = filtered.filter(x => (x.sum || 0) >= sumFrom && (x.sum || 0) <= sumTo);

                ordersData = filtered;
                renderOrders();
            } catch(e) {
                document.getElementById('orders').innerHTML = '<div class="card"><p style="color:red;">Ошибка загрузки: ' + e + '</p></div>';
                document.getElementById('ordersCount').textContent = 'Ошибка';
            }
        }

        function resetOrderFilters() {
            document.getElementById('filterStatus').value = '';
            document.getElementById('filterPeriod').value = '';
            document.getElementById('filterDateFrom').value = '';
            document.getElementById('filterDateTo').value = '';
            document.getElementById('filterClient').value = '';
            document.getElementById('filterCar').value = '';
            document.getElementById('filterSumFrom').value = '';
            document.getElementById('filterSumTo').value = '';
            document.getElementById('filterOrdersLimit').value = '500';
            loadOrdersWithFilters();
        }

        // === ФИЛЬТРЫ КЛИЕНТОВ ===
        function applyClientFilters() {
            clearTimeout(clientFilterTimeout);
            loadClientsWithFilters();
        }

        function applyClientFiltersDebounced() {
            clearTimeout(clientFilterTimeout);
            clientFilterTimeout = setTimeout(loadClientsWithFilters, 400);
        }

        async function loadClientsWithFilters() {
            document.getElementById('clients').innerHTML = '<div class="loading"><div class="spinner"></div><p>Загрузка из 1С...</p></div>';
            document.getElementById('clientsCount').textContent = 'Загрузка...';
            try {
                const params = new URLSearchParams();
                const sort = document.getElementById('filterClientSort').value;
                const search = document.getElementById('filterClientName').value;
                const limit = document.getElementById('filterClientsLimit').value || '500';

                params.append('sort', sort);
                params.append('limit', limit);
                if (search && search.length >= 2) params.append('search', search);

                const data = await fetch('/api/clients?' + params.toString()).then(r => r.json());
                clientsData = data.clients || [];

                // Локальная фильтрация по типу
                const typeFilter = document.getElementById('filterClientType').value;
                if (typeFilter === 'with_phone') {
                    clientsData = clientsData.filter(x => x.phone && x.phone.trim() !== '');
                } else if (typeFilter === 'with_address') {
                    clientsData = clientsData.filter(x => x.address && x.address.trim() !== '');
                }

                renderClients();
            } catch(e) {
                document.getElementById('clients').innerHTML = '<div class="card"><p style="color:red;">Ошибка загрузки: ' + e + '</p></div>';
                document.getElementById('clientsCount').textContent = 'Ошибка';
            }
        }

        function resetClientFilters() {
            document.getElementById('filterClientName').value = '';
            document.getElementById('filterClientSort').value = 'code';
            document.getElementById('filterClientType').value = '';
            document.getElementById('filterClientsLimit').value = '500';
            loadClientsWithFilters();
        }

        // === ФИЛЬТРЫ АВТОМОБИЛЕЙ ===
        function applyCarFilters() {
            renderCars();
        }

        function applyCarFiltersDebounced() {
            clearTimeout(carFilterTimeout);
            carFilterTimeout = setTimeout(renderCars, 300);
        }

        async function loadCarsWithFilters() {
            document.getElementById('cars').innerHTML = '<div class="loading"><div class="spinner"></div><p>Загрузка из 1С...</p></div>';
            document.getElementById('carsCount').textContent = 'Загрузка...';
            try {
                const limit = document.getElementById('filterCarsLimit').value || '500';
                const data = await fetch('/api/cars?limit=' + limit).then(r => r.json());
                carsFullData = data.cars || [];
                renderCars();
            } catch(e) {
                document.getElementById('cars').innerHTML = '<div class="card"><p style="color:red;">Ошибка загрузки: ' + e + '</p></div>';
                document.getElementById('carsCount').textContent = 'Ошибка';
            }
        }

        function resetCarFilters() {
            document.getElementById('filterCarName').value = '';
            document.getElementById('filterCarPlate').value = '';
            document.getElementById('filterCarVin').value = '';
            document.getElementById('filterCarShow').value = '';
            document.getElementById('filterCarsLimit').value = '500';
            loadCarsWithFilters();
        }

        async function loadCatalogs() {
            try {
                const [cars, repairTypes, employees, workshops] = await Promise.all([
                    fetch('/api/catalogs/cars?limit=500').then(r => r.json()),
                    fetch('/api/catalogs/repair_types?limit=50').then(r => r.json()),
                    fetch('/api/catalogs/employees?limit=200').then(r => r.json()),
                    fetch('/api/catalogs/workshops?limit=50').then(r => r.json())
                ]);
                carsData = cars.items || [];
                repairTypesData = repairTypes.items || [];
                mastersData = employees.items || [];
                workshopsData = workshops.items || [];

                document.getElementById('repairTypeSelect').innerHTML = '<option value="">Выберите...</option>' +
                    repairTypesData.map(r => `<option value="${r.code}">${r.name}</option>`).join('');
                document.getElementById('masterSelect').innerHTML = '<option value="">Выберите...</option>' +
                    mastersData.map(r => `<option value="${r.code}">${r.name}</option>`).join('');
                document.getElementById('managerSelect').innerHTML = '<option value="">Выберите...</option>' +
                    mastersData.map(r => `<option value="${r.code}">${r.name}</option>`).join('');
                document.getElementById('workshopSelect').innerHTML = '<option value="">Выберите...</option>' +
                    workshopsData.map(r => `<option value="${r.code}">${r.name}</option>`).join('');
                // Виды оплаты - хардкод (нет справочника в Альфа-Авто)
                document.getElementById('paymentTypeSelect').innerHTML =
                    '<option value="">Выберите...</option>' +
                    '<option value="cash">Наличные</option>' +
                    '<option value="card">Банковская карта</option>' +
                    '<option value="transfer">Безналичный расчёт</option>';
            } catch(e) { console.log('Catalogs error:', e); }
        }

        async function loadCars() {
            try {
                const data = await fetch('/api/cars?limit=500').then(r => r.json());
                carsFullData = data.cars || [];
                renderCars();
            } catch(e) { console.log('Cars error:', e); }
        }

        function renderCars() {
            // Получаем значения фильтров
            const nameFilter = document.getElementById('filterCarName').value.toLowerCase();
            const plateFilter = document.getElementById('filterCarPlate').value.toLowerCase();
            const vinFilter = document.getElementById('filterCarVin').value.toLowerCase();
            const showFilter = document.getElementById('filterCarShow').value;

            let filtered = carsFullData;

            // Фильтрация по названию
            if (nameFilter) {
                filtered = filtered.filter(x => x.name.toLowerCase().includes(nameFilter));
            }
            // Фильтрация по госномеру
            if (plateFilter) {
                filtered = filtered.filter(x => x.plate && x.plate.toLowerCase().includes(plateFilter));
            }
            // Фильтрация по VIN
            if (vinFilter) {
                filtered = filtered.filter(x => x.vin && x.vin.toLowerCase().includes(vinFilter));
            }
            // Фильтрация по типу
            if (showFilter === 'with_plate') {
                filtered = filtered.filter(x => x.plate && x.plate.trim() !== '');
            } else if (showFilter === 'with_vin') {
                filtered = filtered.filter(x => x.vin && x.vin.trim() !== '');
            } else if (showFilter === 'with_owner') {
                filtered = filtered.filter(x => x.owner && x.owner.trim() !== '');
            }

            // Показываем счётчик
            document.getElementById('carsCount').textContent = `Показано: ${filtered.length}`;

            const addBtn = '<div style="margin-bottom:15px;"><button class="btn btn-primary" onclick="openCarModal()">+ Добавить автомобиль</button></div>';
            document.getElementById('cars').innerHTML = addBtn + (filtered.length ? filtered.map(x =>
                `<div class="card">
                    <div class="card-header">
                        <div>
                            <div class="card-title">${x.name}</div>
                            ${x.plate ? `<span class="card-plate">${x.plate}</span>` : ''}
                        </div>
                    </div>
                    ${x.vin ? `<div class="card-subtitle">VIN: ${x.vin}</div>` : ''}
                </div>`
            ).join('') : '<div class="card"><p style="text-align:center;color:#888;">Нет автомобилей по выбранным фильтрам</p></div>');
        }

        function globalSearch() {
            const q = document.getElementById('searchBox').value;
            searchQuery = q;
            const resultsDiv = document.getElementById('searchResults');

            if (q.length < 2) {
                resultsDiv.classList.remove('active');
                filterLocalData();
                return;
            }

            // Filter local data for tabs
            filterLocalData();

            // Debounce API search
            clearTimeout(searchTimeout);
            searchTimeout = setTimeout(async () => {
                try {
                    const data = await fetch('/api/search?q=' + encodeURIComponent(q)).then(r => r.json());
                    if (data.results && data.results.length > 0) {
                        resultsDiv.innerHTML = data.results.map(r => {
                            if (r.type === 'order') {
                                return `<div class="search-result" style="border-left:3px solid #FF9800;" onclick="selectSearchResult('order', '${r.number}', ${r.sum || 0}, '${r.status}', '${r.date}')">
                                    <div class="search-result-type" style="color:#FF9800;">Заказ-наряд</div>
                                    <div class="search-result-title">№${r.number}</div>
                                    <div class="search-result-subtitle">${r.date} | ${(r.sum || 0).toLocaleString('ru-RU')} ₽ | ${r.status}</div>
                                </div>`;
                            } else if (r.type === 'car') {
                                return `<div class="search-result search-result-car" onclick="selectSearchResult('car', '${r.ref}')">
                                    <div class="search-result-type">Автомобиль</div>
                                    <div class="search-result-title">${r.name}</div>
                                    <div class="search-result-subtitle">${r.plate ? 'Госномер: ' + r.plate : ''} ${r.vin ? 'VIN: ' + r.vin : ''}</div>
                                </div>`;
                            } else {
                                return `<div class="search-result search-result-client" onclick="selectSearchResult('client', '${r.ref}')">
                                    <div class="search-result-type">Клиент</div>
                                    <div class="search-result-title">${r.name}</div>
                                    <div class="search-result-subtitle">${r.code} ${r.phone ? '| ' + r.phone : ''}</div>
                                </div>`;
                            }
                        }).join('');
                        resultsDiv.classList.add('active');
                    } else {
                        resultsDiv.classList.remove('active');
                    }
                } catch(e) {
                    resultsDiv.classList.remove('active');
                }
            }, 300);
        }

        function selectSearchResult(type, ref, sum, status, date) {
            document.getElementById('searchResults').classList.remove('active');
            document.getElementById('searchBox').value = '';
            searchQuery = '';
            filterLocalData();

            if (type === 'client') {
                viewClient(ref);
            } else if (type === 'car') {
                // For now just show alert, later can show car detail
                showAlert('Автомобиль выбран');
            } else if (type === 'order') {
                // Show order detail modal
                viewOrderDetail(ref, sum || 0, status || 'Черновик', '', date || '');
            }
        }

        async function viewClient(refKey) {
            document.getElementById('clientModal').classList.add('active');
            document.getElementById('clientModalContent').innerHTML = '<div class="loading"><div class="spinner"></div></div>';

            try {
                const data = await fetch('/api/client/' + refKey).then(r => r.json());
                if (data.error) {
                    document.getElementById('clientModalContent').innerHTML = '<p style="color:red;">Ошибка: ' + data.error + '</p>';
                    return;
                }

                document.getElementById('clientModalTitle').textContent = data.client.name;

                let html = `
                    <div class="detail-section">
                        <h3>Информация</h3>
                        <div class="detail-row"><span class="detail-label">Код</span><span class="detail-value">${data.client.code}</span></div>
                        <div class="detail-row"><span class="detail-label">Телефон</span><span class="detail-value">${data.client.phone || '-'}</span></div>
                        <div class="detail-row"><span class="detail-label">Адрес</span><span class="detail-value" style="font-size:12px;">${data.client.address || '-'}</span></div>
                        <div class="detail-row"><span class="detail-label">Всего заказов</span><span class="detail-value">${data.orders_count}</span></div>
                        <div class="detail-row"><span class="detail-label">Общая сумма</span><span class="detail-value">${data.total_sum.toLocaleString('ru-RU')} ₽</span></div>
                    </div>
                `;

                if (data.cars.length > 0) {
                    html += `<div class="detail-section"><h3>Автомобили (${data.cars_count})</h3>`;
                    data.cars.forEach(car => {
                        html += `<div class="mini-card">
                            <div class="mini-card-title">${car.name}</div>
                            <div class="mini-card-subtitle">${car.plate ? 'Госномер: ' + car.plate : ''} ${car.vin ? 'VIN: ' + car.vin : ''}</div>
                        </div>`;
                    });
                    html += '</div>';
                }

                if (data.orders.length > 0) {
                    html += `<div class="detail-section"><h3>Последние заказы (${data.orders.length})</h3>`;
                    data.orders.slice(0, 20).forEach(order => {
                        const comment = (order.comment || '').replace(/'/g, "\\'").replace(/"/g, '&quot;');
                        html += `<div class="mini-card" style="cursor:pointer;transition:all 0.2s;" onmouseover="this.style.background='#e3f2fd'" onmouseout="this.style.background='#f5f5f5'" onclick="viewOrderDetail('${order.number}', ${order.sum}, '${order.status}', '${comment}', '${order.date || ''}')">
                            <div class="mini-card-title">${order.number} - ${order.sum.toLocaleString('ru-RU')} ₽</div>
                            <div class="mini-card-subtitle">${order.date || ''} | ${order.status}</div>
                            ${order.comment ? `<div style="color:#666;font-size:11px;margin-top:4px;">${order.comment.substring(0,60)}${order.comment.length > 60 ? '...' : ''}</div>` : ''}
                        </div>`;
                    });
                    html += '</div>';
                }

                document.getElementById('clientModalContent').innerHTML = html;
            } catch(e) {
                document.getElementById('clientModalContent').innerHTML = '<p style="color:red;">Ошибка загрузки</p>';
            }
        }

        function filterLocalData() {
            renderOrders();
            renderClients();
            renderCars();
        }

        // Client creation functions
        function openClientModal() {
            document.getElementById('newClientName').value = '';
            document.getElementById('newClientPhone').value = '';
            document.getElementById('newClientModal').classList.add('active');
        }

        async function createNewClient(e) {
            e.preventDefault();
            const name = document.getElementById('newClientName').value.trim();
            if (!name) { showAlert('Введите имя клиента', 'error'); return; }

            const btn = document.getElementById('createClientBtn');
            btn.disabled = true; btn.textContent = 'Создание...';

            const phone = document.getElementById('newClientPhone').value.trim();

            try {
                const r = await fetch('/api/clients', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({ name: name, phone: phone })
                });
                const res = await r.json();
                if (res.success) {
                    showAlert('Клиент создан: ' + name);
                    closeModal('newClientModal');
                    loadData();
                } else {
                    showAlert(res.error || 'Ошибка создания', 'error');
                }
            } catch (err) {
                showAlert('Ошибка: ' + err, 'error');
            }
            btn.disabled = false; btn.textContent = 'Создать';
        }

        // Car creation functions
        function openCarModal() {
            document.getElementById('carNameInput').value = '';
            document.getElementById('carVinInput').value = '';
            document.getElementById('carPlateInput').value = '';
            document.getElementById('carOwnerSearch').value = '';
            document.getElementById('carOwnerKey').value = '';
            document.getElementById('carOwnerList').classList.remove('active');
            document.getElementById('carModal').classList.add('active');
        }

        let searchCarOwnersTimeout = null;
        function searchCarOwners() {
            const q = document.getElementById('carOwnerSearch').value;
            const list = document.getElementById('carOwnerList');
            if (q.length < 2) { list.classList.remove('active'); return; }

            clearTimeout(searchCarOwnersTimeout);
            searchCarOwnersTimeout = setTimeout(async () => {
                try {
                    list.innerHTML = '<div class="client-item" style="color:#888">Поиск...</div>';
                    list.classList.add('active');

                    const resp = await fetch('/api/search?q=' + encodeURIComponent(q));
                    const data = await resp.json();
                    const clients = data.results.filter(r => r.type === 'client');

                    if (clients.length > 0) {
                        list.innerHTML = clients.slice(0, 10).map(c =>
                            `<div class="client-item" onclick="selectCarOwner('${c.ref || c.code}', '${c.name.replace(/'/g, "\\'")}')">${c.name}<br><small style="color:#888">${c.code}</small></div>`
                        ).join('');
                    } else {
                        list.innerHTML = '<div class="client-item" style="color:#888">Не найдено</div>';
                    }
                } catch(e) {
                    list.innerHTML = '<div class="client-item" style="color:#888">Ошибка поиска</div>';
                }
            }, 300);
        }

        function showCarOwnerList() {
            if (document.getElementById('carOwnerSearch').value) searchCarOwners();
        }

        function selectCarOwner(key, name) {
            document.getElementById('carOwnerKey').value = key;
            document.getElementById('carOwnerSearch').value = name;
            document.getElementById('carOwnerList').classList.remove('active');
        }

        async function createCar(e) {
            e.preventDefault();
            const name = document.getElementById('carNameInput').value.trim();
            if (!name) { showAlert('Введите название автомобиля', 'error'); return; }

            const btn = document.getElementById('createCarBtn');
            btn.disabled = true; btn.textContent = 'Создание...';

            const vin = document.getElementById('carVinInput').value.trim();
            const plate = document.getElementById('carPlateInput').value.trim();
            const ownerKey = document.getElementById('carOwnerKey').value;

            // Include plate in name if provided
            const fullName = plate ? `${name} ${plate}` : name;

            const data = {
                name: fullName,
                vin: vin,
                owner_key: ownerKey || undefined
            };

            try {
                const r = await fetch('/api/cars', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify(data)
                });
                const res = await r.json();
                if (res.success) {
                    showAlert('Автомобиль создан: ' + fullName);
                    closeModal('carModal');
                    loadData();  // Reload data
                } else {
                    showAlert(res.error || 'Ошибка создания', 'error');
                }
            } catch (err) {
                showAlert('Ошибка: ' + err, 'error');
            }
            btn.disabled = false; btn.textContent = 'Создать';
        }

        // Hide search results on click outside
        document.addEventListener('click', (e) => {
            if (!e.target.closest('.search-container')) {
                document.getElementById('searchResults').classList.remove('active');
            }
            if (!e.target.closest('.client-search')) {
                document.getElementById('carOwnerList').classList.remove('active');
            }
        });

        function searchCars() {
            const q = document.getElementById('carSearch').value.toLowerCase();
            const list = document.getElementById('carList');

            // If client has cars, search in them first
            if (clientCars.length > 0) {
                if (q.length === 0) {
                    showClientCars();
                    return;
                }
                const filtered = clientCars.filter(c =>
                    c.name.toLowerCase().includes(q) ||
                    (c.plate && c.plate.toLowerCase().includes(q)) ||
                    (c.vin && c.vin.toLowerCase().includes(q))
                );
                if (filtered.length > 0) {
                    list.innerHTML = filtered.map(c =>
                        `<div class="client-item" onclick="selectCar('${c.code}', '${c.name.replace(/'/g, "\\'")}')">
                            <strong>${c.name}</strong>
                            ${c.plate ? '<br><span style="color:#2196F3">' + c.plate + '</span>' : ''}
                            ${c.vin ? '<br><small style="color:#888">VIN: ' + c.vin + '</small>' : ''}
                        </div>`
                    ).join('');
                    list.classList.add('active');
                    return;
                }
            }

            // Fallback: search all cars
            if (q.length < 2) { list.classList.remove('active'); return; }
            const filtered = carsData.filter(c => c.name.toLowerCase().includes(q)).slice(0, 10);
            list.innerHTML = filtered.length ? filtered.map(c =>
                `<div class="client-item" onclick="selectCar('${c.code}', '${c.name.replace(/'/g, "\\'")}')">${c.name}<br><small style="color:#888">${c.code}</small></div>`
            ).join('') : '<div class="client-item" style="color:#888">Не найдено</div>';
            list.classList.add('active');
        }

        function showCarList() {
            // If client has cars, show them
            if (clientCars.length > 0) {
                showClientCars();
            } else if (document.getElementById('carSearch').value.length >= 2) {
                searchCars();
            }
        }

        function selectCar(code, name) {
            document.getElementById('carCode').value = code;
            document.getElementById('carSearch').value = name;
            document.getElementById('carList').classList.remove('active');
        }

        function searchCustomers() {
            const q = document.getElementById('customerSearch').value.toLowerCase();
            const list = document.getElementById('customerList');
            if (q.length < 1) { list.classList.remove('active'); return; }
            const filtered = clientsData.filter(c => c.name.toLowerCase().includes(q)).slice(0, 10);
            list.innerHTML = filtered.map(c =>
                `<div class="client-item" onclick="selectCustomer('${c.code}', '${c.name.replace(/'/g, "\\'")}')">${c.name}<br><small style="color:#888">${c.code}</small></div>`
            ).join('') || '<div class="client-item" style="color:#888">Не найдено</div>';
            list.classList.add('active');
        }

        function showCustomerList() {
            if (document.getElementById('customerSearch').value) searchCustomers();
        }

        function selectCustomer(code, name) {
            document.getElementById('customerCode').value = code;
            document.getElementById('customerSearch').value = name;
            document.getElementById('customerList').classList.remove('active');
        }

        function showTab(t) {
            currentTab = t;
            document.querySelectorAll('.tab').forEach(x => x.classList.remove('active'));
            event.target.classList.add('active');
            document.getElementById('ordersSection').style.display = t === 'orders' ? 'block' : 'none';
            document.getElementById('clientsSection').style.display = t === 'clients' ? 'block' : 'none';
            document.getElementById('carsSection').style.display = t === 'cars' ? 'block' : 'none';
            filterLocalData();
        }

        function showAlert(m, t = 'success') {
            document.getElementById('alert').innerHTML = `<div class="alert alert-${t}">${m}</div>`;
            setTimeout(() => document.getElementById('alert').innerHTML = '', 4000);
        }

        function filterData() {
            searchQuery = document.getElementById('searchBox').value.toLowerCase();
            filterLocalData();
        }

        function renderOrders() {
            // Показываем счётчик
            document.getElementById('ordersCount').textContent = `Показано: ${ordersData.length}`;

            document.getElementById('orders').innerHTML = ordersData.length ? ordersData.map(x => {
                const badgeClass = x.status === 'Проведен' ? 'badge-done' : (x.status === 'Черновик' ? 'badge-new' : 'badge-work');
                return `<div class="card" onclick="viewOrder('${x.number}')">
                    <div class="card-header">
                        <div>
                            <div class="card-title">${x.number}</div>
                            <div class="card-subtitle">${x.client || 'Без клиента'}</div>
                            ${x.car ? `<div class="card-car">${x.car}</div>` : ''}
                        </div>
                        <span class="badge ${badgeClass}">${x.status}</span>
                    </div>
                    <div class="info-row">
                        <span class="info-left">${x.date}</span>
                        <span class="sum">${(x.sum || 0).toLocaleString('ru-RU')} ₽</span>
                    </div>
                </div>`;
            }).join('') : '<div class="card"><p style="text-align:center;color:#888;">Нет заказов по выбранным фильтрам</p></div>';
        }

        function renderClients() {
            // Показываем счётчик
            document.getElementById('clientsCount').textContent = `Показано: ${clientsData.length}`;

            document.getElementById('clients').innerHTML = clientsData.length ? clientsData.map(x =>
                `<div class="card" onclick="viewClient('${x.ref}')">
                    <div class="card-title">${x.name}</div>
                    <div class="card-subtitle">${x.code}${x.phone ? ' | ' + x.phone : ''}</div>
                    ${x.address ? `<div class="card-car" style="color:#666;font-size:12px;margin-top:4px;">${x.address.substring(0,60)}${x.address.length > 60 ? '...' : ''}</div>` : ''}
                </div>`
            ).join('') : '<div class="card"><p style="text-align:center;color:#888;">Нет клиентов</p></div>';
        }

        function viewOrder(num) {
            const order = ordersData.find(x => x.number === num);
            if (!order) return;
            document.getElementById('viewNumber').textContent = order.number;
            document.getElementById('viewContent').innerHTML = `
                <div style="margin-bottom:12px;"><strong>Дата:</strong> ${order.date}</div>
                <div style="margin-bottom:12px;"><strong>Клиент:</strong> ${order.client || '-'}</div>
                <div style="margin-bottom:12px;"><strong>Автомобиль:</strong> ${order.car || '-'}</div>
                <div style="margin-bottom:12px;"><strong>Статус:</strong> ${order.status}</div>
                <div style="margin-bottom:12px;"><strong>Сумма:</strong> ${(order.sum || 0).toLocaleString('ru-RU')} ₽</div>
            `;
            document.getElementById('viewModal').classList.add('active');
        }

        function viewOrderDetail(number, sum, status, comment, date) {
            document.getElementById('orderDetailNumber').textContent = number;
            document.getElementById('orderDetailContent').innerHTML = `
                <div class="detail-section">
                    <div class="detail-row">
                        <span class="detail-label">Номер</span>
                        <span class="detail-value">${number}</span>
                    </div>
                    <div class="detail-row">
                        <span class="detail-label">Дата</span>
                        <span class="detail-value">${date || 'Не указана'}</span>
                    </div>
                    <div class="detail-row">
                        <span class="detail-label">Статус</span>
                        <span class="detail-value"><span class="badge ${status === 'Проведен' ? 'badge-done' : 'badge-new'}">${status}</span></span>
                    </div>
                    <div class="detail-row">
                        <span class="detail-label">Сумма</span>
                        <span class="detail-value" style="font-size:20px;color:#2196F3;font-weight:700;">${sum.toLocaleString('ru-RU')} ₽</span>
                    </div>
                </div>
                ${comment ? `
                <div class="detail-section">
                    <h3>Комментарий / Описание работ</h3>
                    <div style="background:#f5f5f5;padding:12px;border-radius:8px;margin-top:8px;white-space:pre-wrap;font-size:14px;">${comment.replace(/&quot;/g, '"')}</div>
                </div>
                ` : ''}
            `;
            document.getElementById('orderDetailModal').classList.add('active');
        }

        function openCreateModal() {
            document.getElementById('clientSearch').value = '';
            document.getElementById('clientCode').value = '';
            document.getElementById('customerSearch').value = '';
            document.getElementById('customerCode').value = '';
            document.getElementById('carSearch').value = '';
            document.getElementById('carSearch').placeholder = 'Сначала выберите контрагента';
            document.getElementById('carCode').value = '';
            document.getElementById('mileageInput').value = '';
            document.getElementById('repairTypeSelect').value = '';
            document.getElementById('masterSelect').value = '';
            document.getElementById('managerSelect').value = '';
            document.getElementById('workshopSelect').value = '';
            document.getElementById('paymentTypeSelect').value = '';
            document.getElementById('dateStartInput').value = '';
            document.getElementById('dateEndInput').value = '';
            document.getElementById('sumInput').value = '';
            document.getElementById('commentInput').value = '';
            document.getElementById('clientList').classList.remove('active');
            document.getElementById('customerList').classList.remove('active');
            document.getElementById('carList').classList.remove('active');
            // Reset client cars
            selectedClientRef = '';
            clientCars = [];
            document.getElementById('createModal').classList.add('active');
        }

        function closeModal(id) {
            document.getElementById(id).classList.remove('active');
        }

        let searchClientsTimeout = null;
        function searchClients() {
            const q = document.getElementById('clientSearch').value;
            const list = document.getElementById('clientList');
            if (q.length < 2) { list.classList.remove('active'); return; }

            clearTimeout(searchClientsTimeout);
            searchClientsTimeout = setTimeout(async () => {
                try {
                    list.innerHTML = '<div class="client-item" style="color:#888">Поиск...</div>';
                    list.classList.add('active');

                    const resp = await fetch('/api/search?q=' + encodeURIComponent(q));
                    const data = await resp.json();
                    const clients = data.results.filter(r => r.type === 'client');

                    if (clients.length > 0) {
                        list.innerHTML = clients.slice(0, 10).map(c =>
                            `<div class="client-item" onclick="selectClient('${c.code}', '${c.name.replace(/'/g, "\\'")}', '${c.ref}')">${c.name}<br><small style="color:#888">${c.code}</small></div>`
                        ).join('');
                    } else {
                        list.innerHTML = '<div class="client-item" style="color:#888">Не найдено</div>';
                    }
                } catch(e) {
                    list.innerHTML = '<div class="client-item" style="color:#888">Ошибка поиска</div>';
                }
            }, 300);
        }

        function showClientList() {
            if (document.getElementById('clientSearch').value) searchClients();
        }

        let selectedClientRef = '';
        let clientCars = [];

        async function selectClient(code, name, ref) {
            document.getElementById('clientCode').value = code;
            document.getElementById('clientSearch').value = name;
            document.getElementById('clientList').classList.remove('active');
            selectedClientRef = ref || code;

            // Clear car selection
            document.getElementById('carCode').value = '';
            document.getElementById('carSearch').value = '';
            clientCars = [];

            // Load client's cars
            if (selectedClientRef) {
                document.getElementById('carSearch').placeholder = 'Загрузка авто клиента...';
                try {
                    const data = await fetch('/api/client/' + selectedClientRef + '/cars').then(r => r.json());
                    clientCars = data.cars || [];
                    if (clientCars.length > 0) {
                        document.getElementById('carSearch').placeholder = `Выберите авто (${clientCars.length} шт.)`;
                        // Auto-show car list
                        showClientCars();
                    } else {
                        document.getElementById('carSearch').placeholder = 'У клиента нет авто - введите для поиска';
                    }
                } catch(e) {
                    document.getElementById('carSearch').placeholder = 'Ошибка загрузки авто';
                }
            }
        }

        function showClientCars() {
            const list = document.getElementById('carList');
            if (clientCars.length > 0) {
                list.innerHTML = clientCars.map(c =>
                    `<div class="client-item" onclick="selectCar('${c.code}', '${c.name.replace(/'/g, "\\'")}')">
                        <strong>${c.name}</strong>
                        ${c.plate ? '<br><span style="color:#2196F3">' + c.plate + '</span>' : ''}
                        ${c.vin ? '<br><small style="color:#888">VIN: ' + c.vin + '</small>' : ''}
                    </div>`
                ).join('');
                list.classList.add('active');
            }
        }

        document.addEventListener('click', (e) => {
            if (!e.target.closest('.client-search')) {
                document.getElementById('clientList').classList.remove('active');
                document.getElementById('customerList').classList.remove('active');
                document.getElementById('carList').classList.remove('active');
            }
        });

        async function createOrder(e) {
            e.preventDefault();
            const code = document.getElementById('clientCode').value;
            if (!code) { showAlert('Выберите контрагента из списка', 'error'); return; }
            const btn = document.getElementById('createBtn');
            btn.disabled = true; btn.textContent = 'Создание...';
            const data = {
                client_code: code,
                customer_code: document.getElementById('customerCode').value,
                car_code: document.getElementById('carCode').value,
                mileage: document.getElementById('mileageInput').value,
                repair_type_code: document.getElementById('repairTypeSelect').value,
                master_code: document.getElementById('masterSelect').value,
                manager_code: document.getElementById('managerSelect').value,
                workshop_code: document.getElementById('workshopSelect').value,
                payment_type_code: document.getElementById('paymentTypeSelect').value,
                date_start: document.getElementById('dateStartInput').value,
                date_end: document.getElementById('dateEndInput').value,
                sum: document.getElementById('sumInput').value,
                comment: document.getElementById('commentInput').value
            };
            // Удаляем пустые поля
            Object.keys(data).forEach(k => { if (!data[k]) delete data[k]; });
            try {
                const r = await fetch('/api/orders', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify(data)
                });
                const res = await r.json();
                if (res.success) {
                    closeModal('createModal');
                    await loadData();
                    // Show success with order number prominently
                    const orderNum = res.number || 'Новый';
                    showAlert('Заказ-наряд №' + orderNum + ' успешно создан!');
                    // Scroll to orders tab and highlight
                    document.querySelectorAll('.tab')[0].click();
                } else {
                    showAlert(res.error || 'Ошибка создания', 'error');
                }
            } catch (e) {
                showAlert('Ошибка: ' + e, 'error');
            }
            btn.disabled = false; btn.textContent = 'Создать';
        }

        async function loadData() {
            document.getElementById('status').textContent = 'Загрузка...';
            try {
                const [c, o, cars, stats] = await Promise.all([
                    fetch('/api/clients').then(r => r.json()),
                    fetch('/api/orders').then(r => r.json()),
                    fetch('/api/cars?limit=500').then(r => r.json()),
                    fetch('/api/stats').then(r => r.json())
                ]);
                clientsData = c.clients || [];
                ordersData = o.orders || [];
                carsFullData = cars.cars || [];

                const formatSum = (sum) => {
                    if (sum >= 1000000) return (sum/1000000).toFixed(1) + 'M';
                    if (sum >= 1000) return (sum/1000).toFixed(0) + 'K';
                    return sum.toString();
                };

                document.getElementById('stats').innerHTML = `
                    <div class="stat-card" onclick="document.querySelectorAll('.tab')[0].click();">
                        <div class="stat-value" style="color:#2196F3;">${stats.orders_today || 0}</div>
                        <div class="stat-label">Заказов сегодня</div>
                    </div>
                    <div class="stat-card orange" onclick="document.querySelectorAll('.tab')[0].click();">
                        <div class="stat-value" style="color:#FF9800;">${stats.in_progress || 0}</div>
                        <div class="stat-label">В работе</div>
                    </div>
                    <div class="stat-card green" onclick="document.querySelectorAll('.tab')[1].click();">
                        <div class="stat-value" style="color:#4CAF50;">${stats.clients_count || c.count || 0}</div>
                        <div class="stat-label">Клиентов</div>
                    </div>
                    <div class="stat-card purple" onclick="document.querySelectorAll('.tab')[2].click();">
                        <div class="stat-value" style="color:#9C27B0;">${stats.cars_count || carsFullData.length}</div>
                        <div class="stat-label">Автомобилей</div>
                    </div>
                `;
                renderOrders();
                renderClients();
                renderCars();
                document.getElementById('status').textContent = '';
            } catch (e) {
                showAlert('Ошибка загрузки: ' + e, 'error');
                document.getElementById('status').textContent = 'Ошибка';
            }
        }

        loadData();
        loadCatalogs();
    </script>
</body>
</html>
"""

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
