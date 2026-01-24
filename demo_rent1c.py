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
    "master": "eca30c61-f82d-11f0-9fbb-b02628ea963d",
    "manager": "eca30c81-f82d-11f0-9fbb-b02628ea963d",
    "author": "39b4c1f2-fa7c-11e5-9841-6cf049a63e1b",
    "currency": "6bd1932d-fa7c-11e5-9841-6cf049a63e1b",
    "operation": "530d99ea-fa7c-11e5-9841-6cf049a63e1b",
    "warehouse": "65ce4049-fa7c-11e5-9841-6cf049a63e1b",
    "repair_order": "c7194270-d152-11e8-87a5-f46d0425712d",
}

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
        # startswith ищет по началу имени (фамилии)
        filter_str = f"$filter=startswith(Description, '{search}')&"

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

    # Загружаем данные автомобилей клиента (только из его заказов)
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
    """Создать заказ-наряд в Rent1C"""
    try:
        # Получаем договор клиента
        contracts = await odata_get(f"Catalog_ДоговорыВзаиморасчетов?$filter=Owner_Key eq guid'{order.client_key}'&$top=1&$format=json")
        contract_key = contracts.get("value", [{}])[0].get("Ref_Key") if contracts.get("value") else None

        # Формируем документ
        doc = {
            "Date": datetime.now().strftime("%Y-%m-%dT%H:%M:%S"),
            "Posted": False,
            "Организация_Key": DEFAULTS["org"],
            "ПодразделениеКомпании_Key": DEFAULTS["division"],
            "ТипЦен_Key": DEFAULTS["price_type"],
            "ТипЦенРабот_Key": DEFAULTS["price_type"],
            "ВидРемонта_Key": order.repair_type_key or DEFAULTS["repair_type"],
            "Состояние_Key": order.status_key or DEFAULTS["status"],
            "Цех_Key": order.workshop_key or DEFAULTS["workshop"],
            "Мастер_Key": order.master_key or DEFAULTS["master"],
            "Менеджер_Key": DEFAULTS["manager"],
            "Автор_Key": DEFAULTS["author"],
            "ВалютаДокумента_Key": DEFAULTS["currency"],
            "ХозОперация_Key": DEFAULTS["operation"],
            "СкладКомпании_Key": DEFAULTS["warehouse"],
            "СводныйРемонтныйЗаказ_Key": DEFAULTS["repair_order"],
            "Контрагент_Key": order.client_key,
            "КурсДокумента": 1,
            "КурсВалютыВзаиморасчетов": 1,
            "РегламентированныйУчет": True,
            "ЗакрыватьЗаказыТолькоПоДанномуЗаказНаряду": True,
            "СпособЗачетаАвансов": "Автоматически",
        }

        # Диспетчер
        if order.dispatcher_key:
            doc["Диспетчер_Key"] = order.dispatcher_key

        if contract_key:
            doc["ДоговорВзаиморасчетов_Key"] = contract_key

        if order.comment:
            doc["ОписаниеПричиныОбращения"] = order.comment

        if order.mileage:
            doc["Пробег"] = order.mileage

        # Следующее ТО
        if order.next_to:
            doc["СледующееТО"] = int(order.next_to)

        # Даты
        if order.date_start:
            doc["ДатаНачала"] = order.date_start + "T00:00:00"
        if order.date_end:
            doc["ДатаОкончания"] = order.date_end + "T00:00:00"
        if order.date_issue:
            doc["ДатаВыдачиПлан"] = order.date_issue + "T00:00:00"
        if order.date_close:
            doc["ДатаЗакрытия"] = order.date_close + "T00:00:00"

        # Добавляем автомобиль в табличную часть
        if order.car_key:
            doc["Автомобили"] = [{"LineNumber": "1", "Автомобиль_Key": order.car_key}]

        # Добавляем работы в табличную часть Автоработы
        # и собираем исполнителей для отдельной табличной части
        executors_list = []
        if order.works:
            works_list = []
            for i, w in enumerate(order.works):
                line_num = i + 1
                work_id = str(line_num)  # ИдентификаторРаботы для связи с исполнителем

                work_item = {
                    "LineNumber": str(line_num),
                    "Авторабота_Key": w.ref,
                    "ИдентификаторРаботы": work_id,
                    "Количество": w.qty,
                    "Цена": w.price,
                    "Сумма": w.qty * w.price,
                    "СпособРасчетаСтоимостиРаботы": "ФиксированнойСуммой"
                }
                works_list.append(work_item)

                # Если указан исполнитель - добавляем в табличную часть Исполнители
                if w.executor:
                    executors_list.append({
                        "LineNumber": str(len(executors_list) + 1),
                        "ИдентификаторРаботы": work_id,
                        "Исполнитель_Key": w.executor,
                        "Цех_Key": order.workshop_key or DEFAULTS["workshop"],
                        "Процент": 100.0
                    })
            doc["Автоработы"] = works_list

        # Вспомогательные автоработы
        if order.aux_works:
            aux_list = []
            for i, w in enumerate(order.aux_works):
                aux_item = {
                    "LineNumber": str(i + 1),
                    "Авторабота_Key": w.ref,
                    "Количество": w.qty,
                    "Цена": w.price,
                    "Сумма": w.qty * w.price,
                    "СпособРасчетаСтоимостиРаботы": "ФиксированнойСуммой"
                }
                aux_list.append(aux_item)
            doc["ВспомогательныеАвтоработы"] = aux_list

        # Товары
        if order.goods:
            goods_list = []
            for i, g in enumerate(order.goods):
                goods_list.append({
                    "LineNumber": str(i + 1),
                    "Номенклатура_Key": g.ref,
                    "Количество": g.qty,
                    "Цена": g.price,
                    "Сумма": g.qty * g.price
                })
            doc["Товары"] = goods_list

        # Материалы (со склада)
        if order.materials:
            mat_list = []
            for i, m in enumerate(order.materials):
                mat_list.append({
                    "LineNumber": str(i + 1),
                    "Номенклатура_Key": m.ref,
                    "Количество": m.qty,
                    "Цена": m.price,
                    "Сумма": m.qty * m.price
                })
            doc["Материалы"] = mat_list

        # Материалы заказчика
        if order.customer_materials:
            cust_mat_list = []
            for i, m in enumerate(order.customer_materials):
                cust_mat_list.append({
                    "LineNumber": str(i + 1),
                    "Номенклатура_Key": m.ref,
                    "Количество": m.qty
                })
            doc["МатериалыЗаказчика"] = cust_mat_list

        # Добавляем исполнителей (собранных из работ)
        if executors_list:
            doc["Исполнители"] = executors_list

        # Создаём
        result = await odata_post("Document_ЗаказНаряд?$format=json", doc)

        if "odata.error" in result:
            return {"success": False, "error": result["odata.error"]["message"]["value"]}

        return {
            "success": True,
            "number": result.get("Number", "").strip(),
            "ref": result.get("Ref_Key", ""),
            "date": str(result.get("Date", ""))[:10]
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
        works.append({
            "ref": ref,
            "code": i.get("Code", "").strip(),
            "name": i.get("Description", ""),
            "price": prices_map.get(ref, 0),  # Цена из регистра
            "norm_hours": float(i.get("НормаВремени", 0) or 0)
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
