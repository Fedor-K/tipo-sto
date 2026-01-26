# -*- coding: utf-8 -*-
"""
TIPO-STO Demo - полностью на Rent1C
Клиенты, авто, заказы - всё из облачной 1С
"""
from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from typing import Optional
from datetime import datetime
import base64
import httpx
import os
import json

# Rent1C OData
ODATA_URL = "https://aclient.1c-hosting.com/1R96614/1R96614_AA61AS_e771ys34or/odata/standard.odata"
ODATA_USER = "Администратор"
ODATA_PASS = ""

# Default GUIDs
DEFAULTS = {
    "org": "39b4c1f1-fa7c-11e5-9841-6cf049a63e1b",
    "division": "39b4c1f0-fa7c-11e5-9841-6cf049a63e1b",
    "price_type": "65ce4042-fa7c-11e5-9841-6cf049a63e1b",
    "repair_type": "7d9f8931-1a7f-11e6-bee5-20689d8f1e0d",
    "status": "6bd193fc-fa7c-11e5-9841-6cf049a63e1b",
    "workshop": "65ce404a-fa7c-11e5-9841-6cf049a63e1b",
    "master": "eca30c81-f82d-11f0-9fbb-b02628ea963d",  # Григорец Александр Анатольевич
    "manager": "eca30c81-f82d-11f0-9fbb-b02628ea963d",
    "author": "39b4c1f2-fa7c-11e5-9841-6cf049a63e1b",  # Системный автор
    "currency": "6bd1932d-fa7c-11e5-9841-6cf049a63e1b",
    "operation": "530d99ea-fa7c-11e5-9841-6cf049a63e1b",
    "warehouse": "65ce4049-fa7c-11e5-9841-6cf049a63e1b",
    "repair_order": "c7194270-d152-11e8-87a5-f46d0425712d",
    "unit": "6ceca65d-18f4-11e6-a20f-6cf049a63e1b",  # Единица измерения по умолчанию (шт)
}

# Маппинг клиент -> авто (из импорта 185.222)
CLIENT_CARS_MAPPING = {}
mapping_path = os.path.join(os.path.dirname(__file__), "client_cars_mapping.json")
if os.path.exists(mapping_path):
    with open(mapping_path, 'r', encoding='utf-8') as f:
        CLIENT_CARS_MAPPING = json.load(f)
    print(f"[TIPO-STO] Loaded client-car mapping: {len(CLIENT_CARS_MAPPING)} clients")

# История заказов из 185.222 (по коду клиента)
ORDER_HISTORY = {}
history_path = os.path.join(os.path.dirname(__file__), "order_history.json")
if os.path.exists(history_path):
    with open(history_path, 'r', encoding='utf-8') as f:
        history_data = json.load(f)
        ORDER_HISTORY = {c['client_code']: c['orders'] for c in history_data}
    total_orders = sum(len(orders) for orders in ORDER_HISTORY.values())
    print(f"[TIPO-STO] Loaded order history: {len(ORDER_HISTORY)} clients, {total_orders} orders")

# Детали заказов из 185.222 (работы + товары по номеру заказа)
ORDER_DETAILS = {}
details_path = os.path.join(os.path.dirname(__file__), "order_details.json")
if os.path.exists(details_path):
    with open(details_path, 'r', encoding='utf-8') as f:
        ORDER_DETAILS = json.load(f)
    total_works = sum(len(d.get('works', [])) for d in ORDER_DETAILS.values())
    total_goods = sum(len(d.get('goods', [])) for d in ORDER_DETAILS.values())
    print(f"[TIPO-STO] Loaded order details: {len(ORDER_DETAILS)} orders, {total_works} works, {total_goods} goods")

app = FastAPI(title="TIPO-STO", version="2.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


def get_headers():
    credentials = f"{ODATA_USER}:{ODATA_PASS}"
    encoded = base64.b64encode(credentials.encode()).decode()
    return {"Authorization": f"Basic {encoded}", "Accept": "application/json", "Content-Type": "application/json; charset=utf-8"}


async def odata_get(endpoint: str):
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(f"{ODATA_URL}/{endpoint}", headers=get_headers())
        return r.json()


async def odata_post(endpoint: str, data: dict):
    import json
    async with httpx.AsyncClient(timeout=30) as client:
        content = json.dumps(data, ensure_ascii=False)
        print(f"=== ODATA POST ===\n{content}\n==================")
        r = await client.post(f"{ODATA_URL}/{endpoint}", headers=get_headers(),
                              content=content.encode('utf-8'))
        result = r.json()
        print(f"=== ODATA RESPONSE ===\n{json.dumps(result, ensure_ascii=False, indent=2)}\n==================")
        return result


# ==================== UI ====================

@app.get("/", response_class=HTMLResponse)
async def root():
    html_path = os.path.join(os.path.dirname(__file__), "demo_rent1c.html")
    if os.path.exists(html_path):
        with open(html_path, encoding='utf-8') as f:
            return f.read()
    return "<h1>TIPO-STO</h1>"


# ==================== CLIENTS ====================

@app.get("/api/clients")
async def get_clients(search: str = None, limit: int = 50):
    """Клиенты из Rent1C"""
    filter_str = ""
    if search:
        # Capitalize first letter of each word for OData search
        search_cap = ' '.join(word.capitalize() for word in search.split())
        filter_str = f"$filter=substringof('{search_cap}', Description)&"

    data = await odata_get(f"Catalog_Контрагенты?{filter_str}$top={limit}&$orderby=Description&$format=json")

    clients = []
    for item in data.get("value", []):
        phone = ""
        # Попробуем получить телефон из контактной информации
        clients.append({
            "ref": item.get("Ref_Key", ""),
            "code": item.get("Code", "").strip(),
            "name": item.get("Description", ""),
            "inn": item.get("ИНН", "") or "",
            "phone": phone
        })

    return {"clients": clients, "count": len(clients)}


@app.get("/api/clients/{ref}")
async def get_client(ref: str):
    """Клиент с его автомобилями и заказами"""
    # Клиент
    client_data = await odata_get(f"Catalog_Контрагенты(guid'{ref}')?$format=json")

    client = {
        "ref": client_data.get("Ref_Key", ""),
        "code": client_data.get("Code", "").strip(),
        "name": client_data.get("Description", ""),
        "inn": client_data.get("ИНН", "") or "",
    }

    # Договор клиента
    contracts = await odata_get(f"Catalog_ДоговорыВзаиморасчетов?$filter=Owner_Key eq guid'{ref}'&$top=1&$format=json")
    contract_key = contracts.get("value", [{}])[0].get("Ref_Key") if contracts.get("value") else None
    client["contract_key"] = contract_key

    # Заказы клиента
    orders_data = await odata_get(f"Document_ЗаказНаряд?$filter=Контрагент_Key eq guid'{ref}'&$top=10&$orderby=Date desc&$format=json")

    orders = []
    car_keys = set()
    for o in orders_data.get("value", []):
        orders.append({
            "number": o.get("Number", "").strip(),
            "date": str(o.get("Date", ""))[:10],
            "sum": float(o.get("СуммаНоменклатурыДокумента", 0) or 0) + float(o.get("СуммаРаботДокумента", 0) or 0),
            "status": "Проведен" if o.get("Posted") else "Заявка",
            "ref": o.get("Ref_Key", "")
        })
        # Получаем автомобили из заказов
        cars_tab = await odata_get(f"Document_ЗаказНаряд(guid'{o.get('Ref_Key')}')/Автомобили?$format=json")
        for c in cars_tab.get("value", []):
            car_key = c.get("Автомобиль_Key")
            if car_key and car_key != "00000000-0000-0000-0000-000000000000":
                car_keys.add(car_key)

    # Авто клиента: сначала из маппинга, потом из заказов
    if ref in CLIENT_CARS_MAPPING:
        car_keys = set(CLIENT_CARS_MAPPING[ref])

    # Загружаем данные автомобилей клиента
    cars = []
    for car_key in list(car_keys)[:10]:
        car_data = await odata_get(f"Catalog_Автомобили(guid'{car_key}')?$format=json")
        if car_data.get("Ref_Key"):
            cars.append({
                "ref": car_data.get("Ref_Key", ""),
                "name": car_data.get("Description", ""),
                "vin": car_data.get("VIN", "") or "",
                "plate": car_data.get("ГосНомер", "") or ""
            })

    # Добавляем историю из 185.222
    client_code = client["code"]
    history_orders = ORDER_HISTORY.get(client_code, [])

    # Объединяем: сначала новые заказы из Rent1C, потом история из 185.222
    # Убираем дубли по номеру заказа
    existing_numbers = {o["number"] for o in orders}
    for ho in history_orders:
        if ho["number"] not in existing_numbers:
            orders.append({
                "ref": ho["number"],  # Для исторических заказов ref = number
                "number": ho["number"],
                "date": ho["date"],
                "sum": ho["sum"],
                "status": "История",
                "car_name": ho.get("car_name", ""),
                "source": "185.222"
            })

    # Сортируем по дате (новые сверху)
    orders.sort(key=lambda x: x.get("date", ""), reverse=True)

    # Если нет авто из Rent1C, берём из истории заказов
    if not cars and history_orders:
        seen_cars = set()
        for ho in history_orders:
            car_name = ho.get("car_name", "")
            car_vin = ho.get("car_vin", "")
            if car_name and car_name not in seen_cars:
                seen_cars.add(car_name)
                # Извлекаем гос номер из названия (формат: "МАРКА МОДЕЛЬ ЦВЕТ № X000XX000 VIN ...")
                plate = ""
                if "№" in car_name and "VIN" in car_name:
                    try:
                        plate = car_name.split("№")[1].split("VIN")[0].strip()
                    except:
                        pass
                cars.append({
                    "ref": "",  # Нет ref для исторических авто
                    "name": car_name.split(" VIN")[0].strip() if " VIN" in car_name else car_name,
                    "vin": car_vin,
                    "plate": plate,
                    "source": "185.222"
                })

    client["orders"] = orders
    client["cars"] = cars

    return client


# ==================== CARS ====================

@app.get("/api/cars")
async def get_cars(search: str = None, limit: int = 50):
    """Автомобили из Rent1C"""
    filter_str = ""
    if search:
        search_upper = search.upper()
        filter_str = f"$filter=substringof('{search_upper}', VIN) or substringof('{search}', Description) or substringof('{search_upper}', ГосНомер)&"

    data = await odata_get(f"Catalog_Автомобили?{filter_str}$top={limit}&$orderby=Description&$format=json")

    cars = []
    for item in data.get("value", []):
        cars.append({
            "ref": item.get("Ref_Key", ""),
            "code": item.get("Code", "").strip(),
            "name": item.get("Description", ""),
            "vin": item.get("VIN", "") or "",
            "plate": item.get("ГосНомер", "") or ""
        })

    return {"cars": cars, "count": len(cars)}


# ==================== ORDERS ====================

@app.get("/api/orders")
async def get_orders(limit: int = 50):
    """Заказы из Rent1C"""
    data = await odata_get(f"Document_ЗаказНаряд?$top={limit}&$orderby=Date desc&$expand=Контрагент&$format=json")

    orders = []
    for item in data.get("value", []):
        client_name = item.get("Контрагент", {}).get("Description", "") if item.get("Контрагент") else ""
        orders.append({
            "ref": item.get("Ref_Key", ""),
            "number": item.get("Number", "").strip(),
            "date": str(item.get("Date", ""))[:10],
            "client": client_name,
            "client_key": item.get("Контрагент_Key", ""),
            "sum": float(item.get("СуммаНоменклатурыДокумента", 0) or 0) + float(item.get("СуммаРаботДокумента", 0) or 0),
            "status": "Проведен" if item.get("Posted") else "Заявка",
            "comment": item.get("ОписаниеПричиныОбращения", "") or ""
        })

    return {"orders": orders, "count": len(orders)}


# ==================== ORDER DETAILS ====================

@app.get("/api/orders/{ref}")
async def get_order(ref: str):
    """Детали заказ-наряда"""
    # Основные данные заказа
    order_data = await odata_get(f"Document_ЗаказНаряд(guid'{ref}')?$format=json")

    if not order_data.get("Ref_Key"):
        return {"error": "Order not found"}

    # Получаем имя клиента
    client_name = ""
    client_key = order_data.get("Контрагент_Key")
    if client_key and client_key != "00000000-0000-0000-0000-000000000000":
        client_data = await odata_get(f"Catalog_Контрагенты(guid'{client_key}')?$format=json")
        client_name = client_data.get("Description", "")

    # Получаем статус
    status_name = ""
    status_key = order_data.get("Состояние_Key")
    if status_key and status_key != "00000000-0000-0000-0000-000000000000":
        status_data = await odata_get(f"Catalog_ВидыСостоянийЗаказНарядов(guid'{status_key}')?$format=json")
        status_name = status_data.get("Description", "")

    # Табличные части
    cars_data = await odata_get(f"Document_ЗаказНаряд(guid'{ref}')/Автомобили?$format=json")
    works_data = await odata_get(f"Document_ЗаказНаряд(guid'{ref}')/Автоработы?$format=json")
    goods_data = await odata_get(f"Document_ЗаказНаряд(guid'{ref}')/Товары?$format=json")
    aux_works_data = await odata_get(f"Document_ЗаказНаряд(guid'{ref}')/ВспомогательныеАвтоработы?$format=json")
    customer_materials_data = await odata_get(f"Document_ЗаказНаряд(guid'{ref}')/МатериалыЗаказчика?$format=json")
    executors_data = await odata_get(f"Document_ЗаказНаряд(guid'{ref}')/Исполнители?$format=json")
    materials_data = await odata_get(f"Document_ЗаказНаряд(guid'{ref}')/Материалы?$format=json")
    advances_data = await odata_get(f"Document_ЗаказНаряд(guid'{ref}')/ЗачетАвансов?$format=json")

    # Собираем авто
    cars = []
    for c in cars_data.get("value", []):
        car_key = c.get("Автомобиль_Key")
        if car_key and car_key != "00000000-0000-0000-0000-000000000000":
            car_info = await odata_get(f"Catalog_Автомобили(guid'{car_key}')?$format=json")
            cars.append({
                "name": car_info.get("Description", ""),
                "vin": car_info.get("VIN", "") or "",
                "plate": car_info.get("ГосНомер", "") or "",
                "mileage": c.get("Пробег", "")
            })

    # Собираем работы
    works = []
    for w in works_data.get("value", []):
        work_key = w.get("Авторабота_Key")
        work_name = ""
        if work_key and work_key != "00000000-0000-0000-0000-000000000000":
            work_info = await odata_get(f"Catalog_Автоработы(guid'{work_key}')?$format=json")
            work_name = work_info.get("Description", "")
        works.append({
            "name": work_name or w.get("Содержание", "Работа"),
            "quantity": float(w.get("Количество", 1) or 1),
            "price": float(w.get("Цена", 0) or 0),
            "sum": float(w.get("Сумма", 0) or 0)
        })

    # Собираем товары
    goods = []
    for g in goods_data.get("value", []):
        nom_key = g.get("Номенклатура_Key")
        nom_name = ""
        if nom_key and nom_key != "00000000-0000-0000-0000-000000000000":
            nom_info = await odata_get(f"Catalog_Номенклатура(guid'{nom_key}')?$format=json")
            nom_name = nom_info.get("Description", "")
        goods.append({
            "name": nom_name or "Товар",
            "quantity": float(g.get("Количество", 1) or 1),
            "price": float(g.get("Цена", 0) or 0),
            "sum": float(g.get("Сумма", 0) or 0)
        })

    # Вспомогательные автоработы
    aux_works = []
    for w in aux_works_data.get("value", []):
        work_key = w.get("Авторабота_Key")
        work_name = ""
        if work_key and work_key != "00000000-0000-0000-0000-000000000000":
            work_info = await odata_get(f"Catalog_Автоработы(guid'{work_key}')?$format=json")
            work_name = work_info.get("Description", "")
        aux_works.append({
            "name": work_name or w.get("Содержание", "Работа"),
            "quantity": float(w.get("Количество", 1) or 1),
            "price": float(w.get("Цена", 0) or 0),
            "sum": float(w.get("Сумма", 0) or 0)
        })

    # Материалы заказчика
    customer_materials = []
    for m in customer_materials_data.get("value", []):
        nom_key = m.get("Номенклатура_Key")
        nom_name = ""
        if nom_key and nom_key != "00000000-0000-0000-0000-000000000000":
            nom_info = await odata_get(f"Catalog_Номенклатура(guid'{nom_key}')?$format=json")
            nom_name = nom_info.get("Description", "")
        customer_materials.append({
            "name": nom_name or "Материал",
            "quantity": float(m.get("Количество", 1) or 1)
        })

    # Исполнители
    executors = []
    for e in executors_data.get("value", []):
        emp_key = e.get("Сотрудник_Key")
        emp_name = ""
        if emp_key and emp_key != "00000000-0000-0000-0000-000000000000":
            emp_info = await odata_get(f"Catalog_Сотрудники(guid'{emp_key}')?$format=json")
            emp_name = emp_info.get("Description", "")
        executors.append({
            "name": emp_name or "Сотрудник",
            "percent": float(e.get("ПроцентВыполнения", 100) or 100)
        })

    # Материалы (со склада)
    materials = []
    for m in materials_data.get("value", []):
        nom_key = m.get("Номенклатура_Key")
        nom_name = ""
        if nom_key and nom_key != "00000000-0000-0000-0000-000000000000":
            nom_info = await odata_get(f"Catalog_Номенклатура(guid'{nom_key}')?$format=json")
            nom_name = nom_info.get("Description", "")
        materials.append({
            "name": nom_name or "Материал",
            "quantity": float(m.get("Количество", 1) or 1),
            "price": float(m.get("Цена", 0) or 0),
            "sum": float(m.get("Сумма", 0) or 0)
        })

    # Зачет авансов
    advances = []
    for a in advances_data.get("value", []):
        doc_key = a.get("ДокументАванса")
        advances.append({
            "sum": float(a.get("СуммаЗачета", 0) or 0)
        })

    # Считаем суммы из табличных частей (не из шапки - там 0 до проведения)
    sum_works = sum(w["sum"] for w in works) + sum(w["sum"] for w in aux_works)
    sum_goods = sum(g["sum"] for g in goods) + sum(m["sum"] for m in materials)
    sum_advances = sum(a["sum"] for a in advances)

    return {
        "ref": order_data.get("Ref_Key", ""),
        "number": order_data.get("Number", "").strip(),
        "date": str(order_data.get("Date", ""))[:10],
        "client": client_name,
        "status": status_name or ("Проведен" if order_data.get("Posted") else "Заявка"),
        "comment": order_data.get("ОписаниеПричиныОбращения", "") or "",
        "mileage": order_data.get("Пробег", "") or "",
        "sum_works": sum_works,
        "sum_goods": sum_goods,
        "sum_advances": sum_advances,
        "sum_total": sum_works + sum_goods - sum_advances,
        "cars": cars,
        "works": works,
        "goods": goods,
        "aux_works": aux_works,
        "customer_materials": customer_materials,
        "executors": executors,
        "materials": materials,
        "advances": advances
    }


@app.get("/api/orders/history/{number}")
async def get_history_order(number: str):
    """Детали исторического заказа из 185.222"""
    details = ORDER_DETAILS.get(number)
    if not details:
        return {"error": "Order not found in history", "number": number}

    sum_works = sum(w.get("sum", 0) for w in details.get("works", []))
    sum_goods = sum(g.get("sum", 0) for g in details.get("goods", []))
    return {
        "number": number,
        "works": details.get("works", []),
        "goods": details.get("goods", []),
        "sum_works": sum_works,
        "sum_goods": sum_goods,
        "sum_total": sum_works + sum_goods,
        "source": "185.222"
    }


# ==================== CREATE ORDER ====================

class WorkItem(BaseModel):
    ref: str
    qty: float = 1
    price: float = 0
    executor: Optional[str] = None  # Исполнитель_Key


class GoodsItem(BaseModel):
    ref: str  # Номенклатура_Key
    qty: float = 1
    price: float = 0


class MaterialItem(BaseModel):
    ref: str  # Номенклатура_Key
    qty: float = 1
    price: float = 0


class CustomerMaterialItem(BaseModel):
    ref: str  # Номенклатура_Key
    qty: float = 1


class OrderCreate(BaseModel):
    client_key: str
    client_name: str
    car_key: Optional[str] = None
    car_name: Optional[str] = None
    car_plate: Optional[str] = None  # Гос. номер (вводится вручную)
    comment: Optional[str] = None
    mileage: Optional[str] = None
    # Дополнительные поля
    status_key: Optional[str] = None
    repair_type_key: Optional[str] = None
    workshop_key: Optional[str] = None
    master_key: Optional[str] = None
    dispatcher_key: Optional[str] = None
    next_to: Optional[str] = None  # Следующее ТО
    date_start: Optional[str] = None  # Дата начала
    date_end: Optional[str] = None  # Дата окончания
    date_issue: Optional[str] = None  # Дата выдачи (план)
    date_close: Optional[str] = None  # Дата закрытия
    # Табличные части
    works: Optional[list[WorkItem]] = None  # Автоработы (с исполнителем)
    aux_works: Optional[list[WorkItem]] = None  # Вспомогательные автоработы (с исполнителем)
    goods: Optional[list[GoodsItem]] = None  # Товары
    materials: Optional[list[MaterialItem]] = None  # Материалы
    customer_materials: Optional[list[CustomerMaterialItem]] = None  # Материалы заказчика


@app.post("/api/orders/create")
async def create_order(order: OrderCreate):
    """Создать заявку на ремонт в Rent1C"""
    try:
        # Получаем договор клиента
        contracts = await odata_get(f"Catalog_ДоговорыВзаиморасчетов?$filter=Owner_Key eq guid'{order.client_key}'&$top=1&$format=json")
        contract_key = contracts.get("value", [{}])[0].get("Ref_Key") if contracts.get("value") else None

        # Получаем данные клиента (телефон, email)
        client_data = await odata_get(f"Catalog_Контрагенты(guid'{order.client_key}')?$format=json")
        client_phone = ""
        client_email = ""
        # Пробуем получить контактную информацию
        try:
            contacts = await odata_get(f"Catalog_Контрагенты(guid'{order.client_key}')/КонтактнаяИнформация?$format=json")
            for c in contacts.get("value", []):
                if "телефон" in c.get("Тип", "").lower() or "phone" in c.get("Тип", "").lower():
                    client_phone = c.get("Представление", "") or c.get("НомерТелефона", "")
                if "почт" in c.get("Тип", "").lower() or "mail" in c.get("Тип", "").lower():
                    client_email = c.get("Представление", "") or c.get("АдресЭП", "")
        except Exception:
            pass

        # Получаем данные автомобиля (VIN, модель, год выпуска и др.) из справочника
        car_vin = ""
        car_model_key = "00000000-0000-0000-0000-000000000000"
        car_year = ""
        if order.car_key:
            car_data = await odata_get(f"Catalog_Автомобили(guid'{order.car_key}')?$format=json")
            car_vin = car_data.get("VIN", "") or ""
            car_model_key = car_data.get("Модель_Key", "00000000-0000-0000-0000-000000000000")
            # ГодВыпуска - передаём как есть (DateTime)
            car_year = car_data.get("ГодВыпуска", "") or ""

        # Гос.номер передаётся из запроса (не хранится в справочнике!)
        # 1C OData не принимает кириллицу в ГосНомер - конвертируем в латиницу
        # 12 букв по ГОСТ + fallback для частых ошибок (Б→B, И→I, Г→G)
        cyr_to_lat = {
            'А': 'A', 'В': 'B', 'Е': 'E', 'К': 'K', 'М': 'M', 'Н': 'H',
            'О': 'O', 'Р': 'P', 'С': 'C', 'Т': 'T', 'У': 'Y', 'Х': 'X',
            'а': 'A', 'в': 'B', 'е': 'E', 'к': 'K', 'м': 'M', 'н': 'H',
            'о': 'O', 'р': 'P', 'с': 'C', 'т': 'T', 'у': 'Y', 'х': 'X',
            # Fallback для нестандартных букв
            'Б': 'B', 'б': 'B', 'И': 'I', 'и': 'I', 'Г': 'G', 'г': 'G',
            'Л': 'L', 'л': 'L', 'Д': 'D', 'д': 'D', 'Ж': 'J', 'ж': 'J',
        }
        raw_plate = order.car_plate or ""
        car_plate = ''.join(cyr_to_lat.get(c, c) for c in raw_plate).upper()

        now = datetime.now()

        # Создаём заявку на ремонт (основной документ!)
        # Максимально заполняем все доступные поля
        request_doc = {
            "Date": now.strftime("%Y-%m-%dT%H:%M:%S"),
            "Posted": True,
            "Организация_Key": DEFAULTS["org"],
            "ПодразделениеКомпании_Key": DEFAULTS["division"],
            # Заказчик и автомобиль - ключевые поля
            "Заказчик_Key": order.client_key,
            "Автомобиль_Key": order.car_key or "00000000-0000-0000-0000-000000000000",
            # Плательщик = Заказчик (по умолчанию)
            "Контрагент_Key": order.client_key,
            # Данные автомобиля (для отображения)
            "VIN": car_vin,
            "ГосНомер": car_plate,
            # Параметры работы
            "ВидРемонта_Key": order.repair_type_key or DEFAULTS["repair_type"],
            "Цех_Key": order.workshop_key or DEFAULTS["workshop"],
            "ТипЦен_Key": DEFAULTS["price_type"],
            "ТипЦенРабот_Key": DEFAULTS["price_type"],
            "ВалютаДокумента_Key": DEFAULTS["currency"],
            "КурсДокумента": 1,
            "Автор_Key": DEFAULTS["author"],
            # Мастер по умолчанию (если не указан)
            "Мастер_Key": order.master_key or DEFAULTS["master"],
            # Причина обращения
            "ОписаниеПричиныОбращения": order.comment or "Заявка из TIPO-STO",
            "Состояние": "НеУказано",
        }

        # Пробег
        if order.mileage:
            request_doc["Пробег"] = str(order.mileage)

        # Модель автомобиля (если есть)
        if car_model_key and car_model_key != "00000000-0000-0000-0000-000000000000":
            request_doc["Модель_Key"] = car_model_key

        # Год выпуска (передаём как DateTime)
        if car_year:
            request_doc["ГодВыпуска"] = car_year

        # Договор клиента
        if contract_key:
            request_doc["ДоговорВзаиморасчетов_Key"] = contract_key

        # Контактная информация (если есть)
        if client_phone:
            request_doc["ПредставлениеТелефона"] = client_phone
            request_doc["ПредставлениеТелефонаСтрокой"] = client_phone
        if client_email:
            request_doc["АдресЭлектроннойПочты"] = client_email
            request_doc["АдресЭлектроннойПочтыСтрокой"] = client_email

        # Диспетчер (опционально)
        if order.dispatcher_key:
            request_doc["Диспетчер_Key"] = order.dispatcher_key

        # Даты начала/окончания работ (по умолчанию = сегодня)
        today = now.strftime("%Y-%m-%d")
        date_start = order.date_start or today
        date_end = order.date_end or today
        request_doc["ДатаНачала"] = date_start + "T09:00:00"
        request_doc["ДатаОкончания"] = date_end + "T18:00:00"

        # Табличная часть ПричиныОбращения (связь работ с причиной)
        # Используем "Ремонт" как причину по умолчанию
        reason_id = "1"
        reasons_list = [{
            "LineNumber": "1",
            "ИдентификаторПричиныОбращения": reason_id,
            "ПричинаОбращения_Key": "7d9f8933-1a7f-11e6-bee5-20689d8f1e0d",  # Ремонт
            "ПричинаОбращенияСодержание": order.comment or "Ремонт",
            "ВидРемонтаПричиныОбращения_Key": order.repair_type_key or DEFAULTS["repair_type"],
        }]
        request_doc["ПричиныОбращения"] = reasons_list

        # Табличная часть Автоработы
        executors_list = []
        sum_works = 0
        if order.works:
            works_list = []
            for i, w in enumerate(order.works):
                line_num = i + 1
                work_id = str(line_num)
                work_sum = w.qty * w.price
                sum_works += work_sum

                works_list.append({
                    "LineNumber": str(line_num),
                    "Авторабота_Key": w.ref,
                    "ИдентификаторРаботы": work_id,
                    "ИдентификаторПричиныОбращения": reason_id,  # Связь с причиной
                    "Количество": int(w.qty),
                    "Коэффициент": 0,
                    "Цена": int(w.price),
                    "Сумма": int(work_sum),
                    "СуммаВсего": int(work_sum),  # Итоговая сумма
                    "СпособРасчетаСтоимостиРаботы": "ФиксированнойСуммой"
                })

                # Если указан исполнитель
                if w.executor:
                    executors_list.append({
                        "LineNumber": str(len(executors_list) + 1),
                        "ИдентификаторРаботы": work_id,
                        "Исполнитель_Key": w.executor,
                        "Цех_Key": DEFAULTS["workshop"],
                        "Процент": 100
                    })

            request_doc["Автоработы"] = works_list

        # Табличная часть ВспомогательныеАвтоработы
        # ВАЖНО: Не все работы подходят для вспомогательных - только определённого типа
        # Пример рабочего GUID: c7194262-d152-11e8-87a5-f46d0425712d (Регулировка)
        if order.aux_works:
            aux_works_list = []
            for i, w in enumerate(order.aux_works):
                line_num = i + 1
                work_id = str(1000 + line_num)

                aux_works_list.append({
                    "LineNumber": str(line_num),
                    "Авторабота_Key": w.ref,
                    "ИдентификаторРаботы": work_id,
                    "НормаВремени": float(w.qty) if w.qty else 1.0
                })

            request_doc["ВспомогательныеАвтоработы"] = aux_works_list

        # Исполнители
        if executors_list:
            request_doc["Исполнители"] = executors_list

        # Табличная часть Товары
        sum_goods = 0
        if order.goods:
            goods_list = []
            for i, g in enumerate(order.goods):
                goods_sum = g.qty * g.price
                sum_goods += goods_sum
                goods_list.append({
                    "LineNumber": str(i + 1),
                    "Номенклатура_Key": g.ref,
                    "ЕдиницаИзмерения_Key": DEFAULTS["unit"],  # Обязательно!
                    "ИдентификаторПричиныОбращения": reason_id,  # Связь с причиной
                    "Количество": int(g.qty),
                    "Коэффициент": 1,
                    "Цена": int(g.price),
                    "Сумма": int(goods_sum),
                    "СуммаВсего": int(goods_sum),
                    "СкладКомпании_Key": DEFAULTS["warehouse"]
                })
            request_doc["Товары"] = goods_list

        # Общая сумма документа
        total = sum_works + sum_goods

        # Создаём ЗаявкаНаРемонт
        request_result = await odata_post("Document_ЗаявкаНаРемонт?$format=json", request_doc)

        if "odata.error" in request_result:
            return {"success": False, "error": request_result["odata.error"]["message"]["value"], "type": "ЗаявкаНаРемонт"}

        # Возвращаем данные созданной ЗаявкаНаРемонт
        return {
            "success": True,
            "type": "ЗаявкаНаРемонт",
            "number": request_result.get("Number", "").strip(),
            "ref": request_result.get("Ref_Key", ""),
            "date": str(request_result.get("Date", ""))[:10],
            "client": order.client_name,
            "car": order.car_name,
            "sum": total
        }

    except Exception as e:
        return {"success": False, "error": str(e)}


# ==================== СПРАВОЧНИКИ ====================

@app.get("/api/ref/statuses")
async def get_statuses():
    """Состояния заказ-нарядов (только для заказ-нарядов)"""
    data = await odata_get("Catalog_ВидыСостоянийЗаказНарядов?$filter=ИспользоватьВЗаказНаряде eq true&$orderby=РеквизитДопУпорядочивания&$format=json")
    return [{"ref": i.get("Ref_Key"), "name": i.get("Description", "")} for i in data.get("value", [])]


@app.get("/api/ref/repair_types")
async def get_repair_types():
    """Виды ремонта"""
    data = await odata_get("Catalog_ВидыРемонта?$format=json")
    return [{"ref": i.get("Ref_Key"), "name": i.get("Description", "")} for i in data.get("value", [])]


@app.get("/api/ref/workshops")
async def get_workshops():
    """Цеха"""
    data = await odata_get("Catalog_Цеха?$format=json")
    return [{"ref": i.get("Ref_Key"), "name": i.get("Description", "")} for i in data.get("value", [])]


@app.get("/api/ref/employees")
async def get_employees():
    """Сотрудники (мастера, диспетчеры)"""
    data = await odata_get("Catalog_Сотрудники?$top=100&$format=json")
    return [{"ref": i.get("Ref_Key"), "name": i.get("Description", "")} for i in data.get("value", [])]


@app.get("/api/ref/executors")
async def get_executors():
    """Исполнители (механики) - только сотрудники с флагом Исполнитель=true"""
    data = await odata_get(
        "Catalog_Сотрудники?"
        "$filter=Исполнитель eq true&"
        "$select=Ref_Key,Description,Цех_Key,ТипРесурса_Key,УчаствуетВПланировании&"
        "$format=json"
    )

    # Получаем названия цехов
    workshops_data = await odata_get("Catalog_Цеха?$select=Ref_Key,Description&$format=json")
    workshops_map = {w.get("Ref_Key"): w.get("Description", "") for w in workshops_data.get("value", [])}

    executors = []
    for i in data.get("value", []):
        workshop_key = i.get("Цех_Key", "")
        # Пропускаем исполнителей без цеха или без планирования
        if workshop_key == "00000000-0000-0000-0000-000000000000":
            continue
        if i.get("УчаствуетВПланировании") == "НеУчаствуетВПланировании":
            continue

        executors.append({
            "ref": i.get("Ref_Key"),
            "name": i.get("Description", ""),
            "workshop_key": workshop_key,
            "workshop_name": workshops_map.get(workshop_key, ""),
        })

    return {"executors": executors, "count": len(executors)}


@app.get("/api/ref/works")
async def get_works(search: str = None, limit: int = 50):
    """Автоработы для добавления в заказ с ценами из регистра"""
    filter_str = ""
    if search:
        filter_str = f"$filter=substringof('{search}', Description)&"
    data = await odata_get(f"Catalog_Автоработы?{filter_str}$top={limit}&$orderby=Description&$format=json")

    # Получаем цены из регистра ЦеныАвторабот
    # Берём базовые цены (без привязки к модели, цеху и т.д.)
    prices_data = await odata_get(
        f"InformationRegister_ЦеныАвторабот_RecordType?"
        f"$filter=ТипЦен_Key eq guid'{DEFAULTS['price_type']}' and "
        f"Модель_Key eq guid'00000000-0000-0000-0000-000000000000'&"
        f"$format=json"
    )

    # Создаём словарь цен по Авторабота_Key
    prices_map = {}
    for p in prices_data.get("value", []):
        work_key = p.get("Авторабота_Key")
        if work_key:
            prices_map[work_key] = float(p.get("Цена", 0) or 0)

    works = []
    for i in data.get("value", []):
        ref = i.get("Ref_Key")
        time_mins = float(i.get("ВремяВыполнения", 0) or 0)
        works.append({
            "ref": ref,
            "code": i.get("Code", "").strip(),
            "name": i.get("Description", ""),
            "price": prices_map.get(ref, 0),  # Цена из регистра
            "norm_hours": float(i.get("НормаВремени", 0) or 0),
            "time_minutes": time_mins,  # Норма времени в минутах
            "time_hours": round(time_mins / 60, 2) if time_mins else 0  # В часах
        })
    return {"works": works, "count": len(works)}


@app.get("/api/ref/goods")
async def get_goods(search: str = None, limit: int = 50):
    """Номенклатура (запчасти) для добавления в заказ"""
    filter_str = ""
    if search:
        filter_str = f"$filter=substringof('{search}', Description)&"
    data = await odata_get(f"Catalog_Номенклатура?{filter_str}$top={limit}&$orderby=Description&$format=json")
    goods = []
    for i in data.get("value", []):
        goods.append({
            "ref": i.get("Ref_Key"),
            "code": i.get("Code", "").strip(),
            "name": i.get("Description", ""),
            "article": i.get("Артикул", "") or "",
            "price": 0  # Цена вводится вручную
        })
    return {"goods": goods, "count": len(goods)}


# ==================== STATS ====================

@app.get("/api/stats")
async def get_stats():
    """Статистика"""
    clients = await odata_get("Catalog_Контрагенты/$count")
    cars = await odata_get("Catalog_Автомобили/$count")
    orders = await odata_get("Document_ЗаказНаряд/$count")

    return {
        "clients": clients if isinstance(clients, int) else 100,
        "cars": cars if isinstance(cars, int) else 100,
        "orders": orders if isinstance(orders, int) else 10
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
