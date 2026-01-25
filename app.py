"""
TIPO-STO Backend - FastAPI + OData 1C
Простой MVP для автосервиса
"""
from fastapi import FastAPI, HTTPException, Query
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import Optional, List
import httpx
import base64
from datetime import datetime

# ============================================================
# КОНФИГ
# ============================================================

ODATA_URL = "https://aclient.1c-hosting.com/1R96614/1R96614_AA61AS_e771ys34or/odata/standard.odata"
ODATA_USER = "Администратор"
ODATA_PASS = ""

# Константы (GUID из базы)
CONST = {
    "org": "39b4c1f1-fa7c-11e5-9841-6cf049a63e1b",           # ООО Сервис-Авто
    "division": "39b4c1f0-fa7c-11e5-9841-6cf049a63e1b",      # Вся компания
    "warehouse": "65ce4049-fa7c-11e5-9841-6cf049a63e1b",     # Склад Медведково
    "workshop": "65ce404a-fa7c-11e5-9841-6cf049a63e1b",      # Основной цех
    "price_type": "65ce4042-fa7c-11e5-9841-6cf049a63e1b",    # Тип цен продажи
    "price_type_works": "c93d5c5a-1928-11e6-a20f-6cf049a63e1b",  # Тип цен авторабот
    "repair_type": "7d9f8931-1a7f-11e6-bee5-20689d8f1e0d",   # Ремонт
    "currency": "6bd1932d-fa7c-11e5-9841-6cf049a63e1b",      # RUB
    "vat": "55cfa059-5765-11e9-9848-f82fa8e6b382",           # НДС 20%
    "normhour": "c93d5c5b-1928-11e6-a20f-6cf049a63e1b",      # Стандартный нормочас
    "author": "39b4c1f2-fa7c-11e5-9841-6cf049a63e1b",        # Автор (системный)
    # Статусы заказов
    "status_new": "6bd193fc-fa7c-11e5-9841-6cf049a63e1b",    # Заявка
    "status_work": "6bd193f9-fa7c-11e5-9841-6cf049a63e1b",   # В работе
    "status_done": "6bd193fa-fa7c-11e5-9841-6cf049a63e1b",   # Выполнен
    "status_closed": "6bd193fb-fa7c-11e5-9841-6cf049a63e1b", # Закрыт
    # Виды контактной информации
    "contact_phone": "59278e9a-fa7c-11e5-9841-6cf049a63e1b", # Телефон
    "contact_email": "59278e9d-fa7c-11e5-9841-6cf049a63e1b", # Email
}

EMPTY_GUID = "00000000-0000-0000-0000-000000000000"

# ============================================================
# OData КЛИЕНТ
# ============================================================

def odata_headers():
    """Заголовки для OData запросов"""
    creds = f"{ODATA_USER}:{ODATA_PASS}".encode('utf-8')
    return {
        "Authorization": f"Basic {base64.b64encode(creds).decode()}",
        "Content-Type": "application/json",
        "Accept": "application/json"
    }

async def odata_get(path: str, params: dict = None):
    """GET запрос к OData"""
    url = f"{ODATA_URL}/{path}"
    if params:
        query = "&".join(f"${k}={v}" for k, v in params.items())
        url = f"{url}?{query}&$format=json"
    else:
        url = f"{url}?$format=json"

    async with httpx.AsyncClient(timeout=30, verify=False) as client:
        r = await client.get(url, headers=odata_headers())
        if r.status_code == 200:
            return r.json()
        elif r.status_code == 404:
            return None
        else:
            raise HTTPException(status_code=r.status_code, detail=r.text[:500])

async def odata_post(path: str, data: dict):
    """POST запрос к OData (создание)"""
    url = f"{ODATA_URL}/{path}?$format=json"
    async with httpx.AsyncClient(timeout=30, verify=False) as client:
        r = await client.post(url, headers=odata_headers(), json=data)
        if r.status_code in (200, 201):
            return r.json()
        else:
            # Подробная ошибка для отладки
            print(f"OData POST error: {r.status_code}")
            print(f"URL: {url}")
            print(f"Data: {data}")
            print(f"Response: {r.text[:1000]}")
            raise HTTPException(status_code=r.status_code, detail=f"OData error: {r.text[:500]}")

async def odata_patch(path: str, data: dict):
    """PATCH запрос к OData (обновление)"""
    url = f"{ODATA_URL}/{path}?$format=json"
    async with httpx.AsyncClient(timeout=30, verify=False) as client:
        r = await client.patch(url, headers=odata_headers(), json=data)
        if r.status_code in (200, 204):
            return r.json() if r.text else {"ok": True}
        else:
            raise HTTPException(status_code=r.status_code, detail=r.text[:500])

# ============================================================
# МОДЕЛИ (Pydantic)
# ============================================================

class ClientCreate(BaseModel):
    name: str                    # ФИО или название
    phone: Optional[str] = None
    inn: Optional[str] = None
    is_company: bool = False     # Юрлицо или физлицо

class CarCreate(BaseModel):
    owner_ref: str               # Ref_Key контрагента (Поставщик_Key)
    vin: Optional[str] = None
    plate: Optional[str] = None  # Гос. номер (НомерГаражный)
    description: Optional[str] = None  # Описание (марка модель)

class OrderCreate(BaseModel):
    client_ref: str              # Контрагент
    car_ref: str                 # Автомобиль
    mileage: Optional[int] = None
    comment: Optional[str] = None

class WorkItem(BaseModel):
    work_ref: str                # Авторабота
    quantity: float = 1          # Количество (норма-часы)
    price: Optional[float] = None

class PartItem(BaseModel):
    part_ref: str                # Номенклатура
    quantity: float = 1
    price: Optional[float] = None

class OrderUpdate(BaseModel):
    status_ref: Optional[str] = None
    works: Optional[List[WorkItem]] = None
    parts: Optional[List[PartItem]] = None
    comment: Optional[str] = None

# ============================================================
# FastAPI APP
# ============================================================

app = FastAPI(title="TIPO-STO", version="1.0")

# ============================================================
# API: КЛИЕНТЫ
# ============================================================

@app.get("/api/clients")
async def get_clients(search: str = Query(None, description="Поиск по имени или телефону")):
    """Список клиентов с поиском"""
    params = {
        "select": "Ref_Key,Code,Description,ИНН,Имя,Фамилия,Отчество,КонтактнаяИнформация",
        "filter": "IsFolder eq false",
        "top": "100",
        "orderby": "Description"
    }

    if search:
        # Поиск по имени (Description содержит поисковую строку)
        params["filter"] = f"IsFolder eq false and substringof('{search}',Description)"

    data = await odata_get("Catalog_Контрагенты", params)
    clients = data.get("value", []) if data else []

    # Форматируем ответ
    result = []
    for c in clients:
        phone = ""
        # Извлекаем телефон из контактной информации
        contacts = c.get("КонтактнаяИнформация", [])
        for contact in contacts:
            if contact.get("Тип") == "Телефон":
                phone = contact.get("Представление", "")
                break

        result.append({
            "ref": c.get("Ref_Key"),
            "code": c.get("Code", "").strip(),
            "name": c.get("Description", ""),
            "inn": c.get("ИНН", ""),
            "phone": phone
        })

    return {"clients": result, "count": len(result)}

@app.get("/api/clients/{ref}")
async def get_client(ref: str):
    """Карточка клиента с машинами и заказами"""
    # Получаем клиента
    client_data = await odata_get(f"Catalog_Контрагенты(guid'{ref}')")
    if not client_data:
        raise HTTPException(status_code=404, detail="Клиент не найден")

    # Извлекаем контакты
    phone = ""
    email = ""
    contacts = client_data.get("КонтактнаяИнформация", [])
    for contact in contacts:
        if contact.get("Тип") == "Телефон" and not phone:
            phone = contact.get("Представление", "")
        if contact.get("Тип") == "АдресЭлектроннойПочты" and not email:
            email = contact.get("Представление", "")

    client = {
        "ref": client_data.get("Ref_Key"),
        "code": client_data.get("Code", "").strip(),
        "name": client_data.get("Description", ""),
        "full_name": client_data.get("НаименованиеПолное", ""),
        "inn": client_data.get("ИНН", ""),
        "phone": phone,
        "email": email,
        "first_name": client_data.get("Имя", ""),
        "last_name": client_data.get("Фамилия", ""),
        "middle_name": client_data.get("Отчество", "")
    }

    # Получаем машины клиента (Поставщик_Key = клиент)
    cars_data = await odata_get("Catalog_Автомобили", {
        "filter": f"Поставщик_Key eq guid'{ref}' and IsFolder eq false",
        "select": "Ref_Key,Description,VIN,НомерГаражный,Марка_Key,Модель_Key",
        "top": "50"
    })
    cars = []
    for car in (cars_data.get("value", []) if cars_data else []):
        cars.append({
            "ref": car.get("Ref_Key"),
            "name": car.get("Description", ""),
            "vin": car.get("VIN", ""),
            "plate": car.get("НомерГаражный", "")
        })

    # Получаем заказы клиента
    orders_data = await odata_get("Document_ЗаказНаряд", {
        "filter": f"Контрагент_Key eq guid'{ref}'",
        "select": "Ref_Key,Number,Date,Состояние_Key,СуммаДокумента,Комментарий",
        "orderby": "Date desc",
        "top": "50"
    })
    orders = []
    for order in (orders_data.get("value", []) if orders_data else []):
        orders.append({
            "ref": order.get("Ref_Key"),
            "number": order.get("Number", "").strip(),
            "date": order.get("Date", ""),
            "status_ref": order.get("Состояние_Key"),
            "total": order.get("СуммаДокумента", 0),
            "comment": order.get("Комментарий", "")
        })

    return {
        "client": client,
        "cars": cars,
        "orders": orders
    }

@app.post("/api/clients")
async def create_client(data: ClientCreate):
    """Создать клиента"""
    # Минимальные обязательные поля для создания контрагента
    client_data = {
        "Description": data.name,
    }

    # Опциональные поля
    if data.inn:
        client_data["ИНН"] = data.inn

    # Телефон сохраняем в отдельное поле (не в КонтактнаяИнформация)
    if data.phone:
        client_data["НомерТелефона"] = data.phone

    result = await odata_post("Catalog_Контрагенты", client_data)
    return {"ref": result.get("Ref_Key"), "ok": True}

# ============================================================
# API: АВТОМОБИЛИ
# ============================================================

@app.get("/api/cars")
async def get_cars(
    owner_ref: str = Query(None, description="Фильтр по владельцу"),
    search: str = Query(None, description="Поиск по VIN или номеру")
):
    """Список автомобилей"""
    params = {
        "select": "Ref_Key,Description,VIN,НомерГаражный,Поставщик_Key",
        "filter": "IsFolder eq false",
        "top": "100"
    }

    if owner_ref:
        params["filter"] = f"Поставщик_Key eq guid'{owner_ref}' and IsFolder eq false"
    elif search:
        params["filter"] = f"IsFolder eq false and (substringof('{search}',VIN) or substringof('{search}',НомерГаражный))"

    data = await odata_get("Catalog_Автомобили", params)
    cars = []
    for car in (data.get("value", []) if data else []):
        cars.append({
            "ref": car.get("Ref_Key"),
            "name": car.get("Description", ""),
            "vin": car.get("VIN", ""),
            "plate": car.get("НомерГаражный", ""),
            "owner_ref": car.get("Поставщик_Key")
        })

    return {"cars": cars, "count": len(cars)}

@app.post("/api/cars")
async def create_car(data: CarCreate):
    """Создать автомобиль"""
    description = data.description or ""
    if data.plate:
        description = f"{description} № {data.plate}".strip()
    if data.vin:
        description = f"{description} VIN {data.vin}".strip()

    car_data = {
        "Description": description[:100],
        "НаименованиеПолное": description,
        "Поставщик_Key": data.owner_ref,  # Владелец!
        "VIN": data.vin or "",
        "НомерГаражный": data.plate or "",
        "Автор_Key": CONST["author"],
        "ВалютаУчета_Key": CONST["currency"]
    }

    result = await odata_post("Catalog_Автомобили", car_data)
    return {"ref": result.get("Ref_Key"), "ok": True}

# ============================================================
# API: ЗАКАЗ-НАРЯДЫ
# ============================================================

@app.get("/api/orders")
async def get_orders(
    status: str = Query(None, description="Фильтр по статусу: new, work, done, closed"),
    client_ref: str = Query(None, description="Фильтр по клиенту"),
    limit: int = Query(50, ge=1, le=200)
):
    """Список заказ-нарядов"""
    filters = []

    if status:
        status_map = {
            "new": CONST["status_new"],
            "work": CONST["status_work"],
            "done": CONST["status_done"],
            "closed": CONST["status_closed"]
        }
        if status in status_map:
            filters.append(f"Состояние_Key eq guid'{status_map[status]}'")

    if client_ref:
        filters.append(f"Контрагент_Key eq guid'{client_ref}'")

    params = {
        "select": "Ref_Key,Number,Date,Контрагент_Key,Состояние_Key,СуммаДокумента,Комментарий,Пробег",
        "orderby": "Date desc",
        "top": str(limit)
    }

    if filters:
        params["filter"] = " and ".join(filters)

    data = await odata_get("Document_ЗаказНаряд", params)
    orders = []
    for order in (data.get("value", []) if data else []):
        # Определяем статус
        status_ref = order.get("Состояние_Key", "")
        status_name = "unknown"
        if status_ref == CONST["status_new"]:
            status_name = "new"
        elif status_ref == CONST["status_work"]:
            status_name = "work"
        elif status_ref == CONST["status_done"]:
            status_name = "done"
        elif status_ref == CONST["status_closed"]:
            status_name = "closed"

        orders.append({
            "ref": order.get("Ref_Key"),
            "number": order.get("Number", "").strip(),
            "date": order.get("Date", ""),
            "client_ref": order.get("Контрагент_Key"),
            "status": status_name,
            "status_ref": status_ref,
            "total": order.get("СуммаДокумента", 0),
            "mileage": order.get("Пробег", 0),
            "comment": order.get("Комментарий", "")
        })

    return {"orders": orders, "count": len(orders)}

@app.get("/api/orders/{ref}")
async def get_order(ref: str):
    """Заказ-наряд с деталями (работы, товары)"""
    # Получаем заказ
    order_data = await odata_get(f"Document_ЗаказНаряд(guid'{ref}')")
    if not order_data:
        raise HTTPException(status_code=404, detail="Заказ не найден")

    # Статус
    status_ref = order_data.get("Состояние_Key", "")
    status_name = "unknown"
    if status_ref == CONST["status_new"]:
        status_name = "new"
    elif status_ref == CONST["status_work"]:
        status_name = "work"
    elif status_ref == CONST["status_done"]:
        status_name = "done"
    elif status_ref == CONST["status_closed"]:
        status_name = "closed"

    order = {
        "ref": order_data.get("Ref_Key"),
        "number": order_data.get("Number", "").strip(),
        "date": order_data.get("Date", ""),
        "client_ref": order_data.get("Контрагент_Key"),
        "status": status_name,
        "status_ref": status_ref,
        "total": order_data.get("СуммаДокумента", 0),
        "total_works": order_data.get("СуммаРаботДокумента", 0),
        "total_parts": order_data.get("СуммаНоменклатурыДокумента", 0),
        "mileage": order_data.get("Пробег", 0),
        "comment": order_data.get("Комментарий", ""),
        "recommendations": order_data.get("Рекомендации", "")
    }

    # Работы (из табличной части)
    works = []
    for w in order_data.get("Автоработы", []):
        works.append({
            "work_ref": w.get("Авторабота_Key"),
            "quantity": w.get("Количество", 1),
            "price": w.get("Цена", 0),
            "total": w.get("СуммаВсего", 0),
            "note": w.get("ПримечаниеРаботы", "")
        })

    # Товары (из табличной части)
    parts = []
    for p in order_data.get("Товары", []):
        parts.append({
            "part_ref": p.get("Номенклатура_Key"),
            "quantity": p.get("Количество", 1),
            "price": p.get("Цена", 0),
            "total": p.get("СуммаВсего", 0),
            "note": p.get("ПримечаниеНоменклатура", "")
        })

    # Автомобили
    cars = []
    for c in order_data.get("Автомобили", []):
        cars.append({"car_ref": c.get("Автомобиль_Key")})

    return {
        "order": order,
        "works": works,
        "parts": parts,
        "cars": cars
    }

@app.post("/api/orders")
async def create_order(data: OrderCreate):
    """Создать заказ-наряд"""
    now = datetime.now().isoformat()

    # Проверяем/создаём договор для клиента
    contracts = await odata_get("Catalog_ДоговорыВзаиморасчетов", {
        "filter": f"Owner_Key eq guid'{data.client_ref}' and Основной eq true",
        "select": "Ref_Key",
        "top": "1"
    })

    contract_ref = None
    if contracts and contracts.get("value"):
        contract_ref = contracts["value"][0].get("Ref_Key")
    else:
        # Создаём договор (Продажа = договор с покупателем)
        contract_data = {
            "Owner_Key": data.client_ref,
            "Description": "Основной договор",
            "Организация_Key": CONST["org"],
            "ВалютаВзаиморасчетов_Key": CONST["currency"],
            "ТипЦен_Key": CONST["price_type"],
            "Основной": True,
            "ВидДоговора": "Продажа",
            "ДляАвтосервиса": True
        }
        contract_result = await odata_post("Catalog_ДоговорыВзаиморасчетов", contract_data)
        contract_ref = contract_result.get("Ref_Key")

    # Создаём заказ-наряд (минимальный набор полей)
    order_data = {
        "Date": now,
        "Организация_Key": CONST["org"],
        "Контрагент_Key": data.client_ref,
        "ДоговорВзаиморасчетов_Key": contract_ref,
        "СкладКомпании_Key": CONST["warehouse"],
        "Цех_Key": CONST["workshop"],
        "ВидРемонта_Key": CONST["repair_type"],
        "Состояние_Key": CONST["status_new"],
        "ВалютаДокумента_Key": CONST["currency"],
        "Пробег": data.mileage or 0,
        "Комментарий": data.comment or ""
    }

    # Табличные части - добавляем отдельно если есть автомобиль
    # (OData 1C может не поддерживать создание с табличными частями напрямую)

    result = await odata_post("Document_ЗаказНаряд", order_data)
    return {"ref": result.get("Ref_Key"), "number": result.get("Number", "").strip(), "ok": True}

@app.patch("/api/orders/{ref}")
async def update_order(ref: str, data: OrderUpdate):
    """Обновить заказ-наряд (статус, работы, товары)"""
    update_data = {}

    if data.status_ref:
        update_data["Состояние_Key"] = data.status_ref

    if data.comment is not None:
        update_data["Комментарий"] = data.comment

    # Если нужно добавить работы или товары - получаем текущий заказ
    if data.works or data.parts:
        current = await odata_get(f"Document_ЗаказНаряд(guid'{ref}')")
        if not current:
            raise HTTPException(status_code=404, detail="Заказ не найден")

        if data.works:
            existing_works = current.get("Автоработы", [])
            for w in data.works:
                existing_works.append({
                    "Авторабота_Key": w.work_ref,
                    "Количество": w.quantity,
                    "Цена": w.price or 0,
                    "Сумма": (w.price or 0) * w.quantity,
                    "СуммаВсего": (w.price or 0) * w.quantity,
                    "Нормочас_Key": CONST["normhour"],
                    "СтавкаНДС_Key": CONST["vat"]
                })
            update_data["Автоработы"] = existing_works

        if data.parts:
            existing_parts = current.get("Товары", [])
            for p in data.parts:
                existing_parts.append({
                    "Номенклатура_Key": p.part_ref,
                    "Количество": p.quantity,
                    "Цена": p.price or 0,
                    "Сумма": (p.price or 0) * p.quantity,
                    "СуммаВсего": (p.price or 0) * p.quantity,
                    "СкладКомпании_Key": CONST["warehouse"],
                    "СтавкаНДС_Key": CONST["vat"]
                })
            update_data["Товары"] = existing_parts

    if update_data:
        await odata_patch(f"Document_ЗаказНаряд(guid'{ref}')", update_data)

    return {"ok": True}

# ============================================================
# API: СПРАВОЧНИКИ (для выбора)
# ============================================================

@app.get("/api/catalogs/works")
async def get_works(search: str = Query(None), limit: int = Query(50, ge=1, le=200)):
    """Справочник авторабот"""
    params = {
        "select": "Ref_Key,Code,Description,ВремяВыполнения",
        "filter": "IsFolder eq false",
        "orderby": "Description",
        "top": str(limit)
    }

    if search:
        params["filter"] = f"IsFolder eq false and substringof('{search}',Description)"

    data = await odata_get("Catalog_Автоработы", params)
    works = []
    for w in (data.get("value", []) if data else []):
        works.append({
            "ref": w.get("Ref_Key"),
            "code": w.get("Code", "").strip(),
            "name": w.get("Description", ""),
            "time": w.get("ВремяВыполнения", 0)
        })

    return {"works": works, "count": len(works)}

@app.get("/api/catalogs/parts")
async def get_parts(search: str = Query(None), limit: int = Query(50, ge=1, le=200)):
    """Справочник номенклатуры (запчасти)"""
    params = {
        "select": "Ref_Key,Code,Description,Артикул",
        "filter": "IsFolder eq false",
        "orderby": "Description",
        "top": str(limit)
    }

    if search:
        params["filter"] = f"IsFolder eq false and (substringof('{search}',Description) or substringof('{search}',Артикул))"

    data = await odata_get("Catalog_Номенклатура", params)
    parts = []
    for p in (data.get("value", []) if data else []):
        parts.append({
            "ref": p.get("Ref_Key"),
            "code": p.get("Code", "").strip(),
            "name": p.get("Description", ""),
            "article": p.get("Артикул", "")
        })

    return {"parts": parts, "count": len(parts)}

@app.get("/api/catalogs/statuses")
async def get_statuses():
    """Список статусов заказов"""
    return {
        "statuses": [
            {"ref": CONST["status_new"], "code": "new", "name": "Заявка"},
            {"ref": CONST["status_work"], "code": "work", "name": "В работе"},
            {"ref": CONST["status_done"], "code": "done", "name": "Выполнен"},
            {"ref": CONST["status_closed"], "code": "closed", "name": "Закрыт"}
        ]
    }

# ============================================================
# СТАТИКА
# ============================================================

@app.get("/")
async def root():
    return FileResponse("static/index.html")

# Монтируем статику
import os
if os.path.exists("static"):
    app.mount("/static", StaticFiles(directory="static"), name="static")

# ============================================================
# ЗАПУСК
# ============================================================

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
