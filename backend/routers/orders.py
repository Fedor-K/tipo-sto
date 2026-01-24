"""Orders router - /api/orders endpoints"""
from datetime import datetime, timedelta
from fastapi import APIRouter, Query

from ..config import settings
from ..odata import fetch_odata, get_cache, set_cache, clear_cache

router = APIRouter(prefix="/api/orders", tags=["orders"])


@router.get("")
async def get_orders(
    status: str = Query(None, description="Filter: draft, done"),
    period: str = Query(None, description="Period: today, week, month, quarter, year, all"),
    date_from: str = Query(None, description="Start date YYYY-MM-DD"),
    date_to: str = Query(None, description="End date YYYY-MM-DD"),
    limit: int = Query(100, ge=1, le=500)
):
    """
    Get orders list with optional filters

    - **status**: draft (unposted), done (posted)
    - **period**: today, week, month, quarter, year, all
    - **date_from/date_to**: Custom date range
    - **limit**: Max results (default 100)
    """
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

        # Period or specific dates
        if date_from:
            filters.append(f"Date ge datetime'{date_from}T00:00:00'")
        elif period and period != "all":
            now = datetime.now()
            period_days = {
                "today": 0,
                "week": 7,
                "month": 30,
                "quarter": 90,
                "year": 365
            }
            days = period_days.get(period)
            if days is not None:
                if days == 0:
                    df = now.replace(hour=0, minute=0, second=0, microsecond=0)
                else:
                    df = now - timedelta(days=days)
                filters.append(f"Date ge datetime'{df.strftime('%Y-%m-%dT%H:%M:%S')}'")

        if date_to:
            filters.append(f"Date le datetime'{date_to}T23:59:59'")

        filter_str = " and ".join(filters) if filters else ""
        filter_param = f"$filter={filter_str}&" if filter_str else ""

        # Get orders with expanded Контрагент
        data = await fetch_odata(
            f"Document_ЗаказНаряд?{filter_param}$top={limit}&$orderby=Date desc&$expand=Контрагент&$format=json"
        )

        if "error" in data:
            return {"orders": [], "count": 0, "error": data["error"]}

        items = data.get("value", [])
        orders = []

        for item in items:
            posted = item.get("Posted", False)
            order_status = "Проведен" if posted else "Черновик"
            date_str = str(item.get("Date", ""))[:10] if item.get("Date") else ""

            # Get client name from expanded Контрагент
            client_name = ""
            if item.get("Контрагент"):
                client_name = str(item["Контрагент"].get("Description", ""))

            # Calculate sum
            sum_parts = float(item.get("СуммаНоменклатурыДокумента", 0) or 0)
            sum_works = float(item.get("СуммаРаботДокумента", 0) or 0)
            total_sum = sum_parts + sum_works

            orders.append({
                "number": str(item.get("Number", "")).strip(),
                "date": date_str,
                "client": client_name,
                "client_key": str(item.get("Контрагент_Key", "")),
                "car": "",  # Loaded separately if needed
                "status": order_status,
                "sum": total_sum,
                "comment": str(item.get("ОписаниеПричиныОбращения", "") or ""),
                "ref": str(item.get("Ref_Key", ""))
            })

        result = {
            "orders": orders,
            "count": len(orders),
            "filters": {"status": status, "period": period}
        }
        set_cache(cache_key, result)
        return result

    except Exception as e:
        return {"orders": [], "count": 0, "error": str(e)}


@router.get("/{ref}")
async def get_order(ref: str):
    """
    Get order details by Ref_Key

    Returns full order info with works and parts
    """
    try:
        # Get order by ref (GUID)
        data = await fetch_odata(f"Document_ЗаказНаряд(guid'{ref}')?$expand=Контрагент&$format=json")

        if "error" in data:
            return {"error": data["error"]}

        item = data

        # Get client name
        client_name = ""
        if item.get("Контрагент"):
            client_name = str(item["Контрагент"].get("Description", ""))

        # Calculate sum
        sum_parts = float(item.get("СуммаНоменклатурыДокумента", 0) or 0)
        sum_works = float(item.get("СуммаРаботДокумента", 0) or 0)
        total_sum = sum_parts + sum_works

        order = {
            "number": str(item.get("Number", "")).strip(),
            "date": str(item.get("Date", ""))[:10] if item.get("Date") else "",
            "client": client_name,
            "client_key": str(item.get("Контрагент_Key", "")),
            "status": "Проведен" if item.get("Posted", False) else "Черновик",
            "sum": total_sum,
            "sum_parts": sum_parts,
            "sum_works": sum_works,
            "comment": str(item.get("ОписаниеПричиныОбращения", "") or ""),
            "mileage": str(item.get("Пробег", "") or ""),
            "ref": str(item.get("Ref_Key", ""))
        }

        # Get works (Автоработы tabular part)
        works = []
        works_data = await fetch_odata(
            f"Document_ЗаказНаряд(guid'{ref}')/Автоработы?$format=json"
        )
        for w in works_data.get("value", []):
            works.append({
                "name": str(w.get("Авторабота", "") or w.get("Description", "")),
                "work_key": str(w.get("Авторабота_Key", "")),
                "qty": float(w.get("Количество", 0) or 0),
                "price": float(w.get("Цена", 0) or 0),
                "sum": float(w.get("Сумма", 0) or 0)
            })

        # Get parts (Товары tabular part)
        parts = []
        parts_data = await fetch_odata(
            f"Document_ЗаказНаряд(guid'{ref}')/Товары?$format=json"
        )
        for p in parts_data.get("value", []):
            parts.append({
                "name": str(p.get("Номенклатура", "") or p.get("Description", "")),
                "part_key": str(p.get("Номенклатура_Key", "")),
                "qty": float(p.get("Количество", 0) or 0),
                "price": float(p.get("Цена", 0) or 0),
                "discount": float(p.get("ПроцентСкидки", 0) or 0),
                "sum": float(p.get("Сумма", 0) or 0)
            })

        # Get cars (Автомобили tabular part)
        cars = []
        cars_data = await fetch_odata(
            f"Document_ЗаказНаряд(guid'{ref}')/Автомобили?$format=json"
        )
        for c in cars_data.get("value", []):
            car_key = c.get("Автомобиль_Key")
            if car_key and car_key != "00000000-0000-0000-0000-000000000000":
                # Load car details
                car_info = await fetch_odata(f"Catalog_Автомобили(guid'{car_key}')?$format=json")
                cars.append({
                    "name": str(car_info.get("Description", "")),
                    "vin": str(car_info.get("VIN", "") or ""),
                    "ref": car_key
                })

        order["works"] = works
        order["parts"] = parts
        order["cars"] = cars

        return order

    except Exception as e:
        return {"error": str(e)}


@router.post("")
async def create_order(order: dict):
    """Create a new order in 1C"""
    try:
        # Prepare OData document with required fields
        doc_data = {
            "Date": datetime.now().strftime("%Y-%m-%dT%H:%M:%S"),
            "Posted": False,
            "Организация_Key": settings.DEFAULT_ORG,
            "ПодразделениеКомпании_Key": settings.DEFAULT_DIVISION,
            "ТипЦен_Key": settings.DEFAULT_PRICE_TYPE,
            "ТипЦенРабот_Key": settings.DEFAULT_PRICE_TYPE,
            "ВидРемонта_Key": order.get("repair_type_key") or settings.DEFAULT_REPAIR_TYPE,
            "Состояние_Key": settings.DEFAULT_STATUS,
            "Цех_Key": order.get("workshop_key") or settings.DEFAULT_WORKSHOP,
            "Мастер_Key": order.get("master_key") or settings.DEFAULT_MASTER,
            "Менеджер_Key": settings.DEFAULT_MANAGER,
            "Автор_Key": settings.DEFAULT_AUTHOR,
            "ВалютаДокумента_Key": settings.DEFAULT_CURRENCY,
            "ХозОперация_Key": settings.DEFAULT_OPERATION,
            "СкладКомпании_Key": settings.DEFAULT_WAREHOUSE,
            "СводныйРемонтныйЗаказ_Key": settings.DEFAULT_REPAIR_ORDER,
            "КурсДокумента": 1,
            "КурсВалютыВзаиморасчетов": 1,
            "РегламентированныйУчет": True,
            "ЗакрыватьЗаказыТолькоПоДанномуЗаказНаряду": True,
            "СпособЗачетаАвансов": "Автоматически",
        }

        # Set client
        if order.get("client_key"):
            doc_data["Контрагент_Key"] = order["client_key"]

            # Try to get client's contract
            contract_data = await fetch_odata(
                f"Catalog_ДоговорыВзаиморасчетов?$filter=Owner_Key eq guid'{order['client_key']}'&$top=1&$format=json"
            )
            if contract_data.get("value"):
                doc_data["ДоговорВзаиморасчетов_Key"] = contract_data["value"][0].get("Ref_Key")

        # Set comment/reason
        if order.get("comment"):
            doc_data["ОписаниеПричиныОбращения"] = order["comment"]

        # Set mileage
        if order.get("mileage"):
            doc_data["Пробег"] = str(order["mileage"])

        # Add car to tabular part
        if order.get("car_key"):
            doc_data["Автомобили"] = [{"Автомобиль_Key": order["car_key"]}]

        # Add works to tabular part
        if order.get("works"):
            doc_data["Автоработы"] = [
                {
                    "Авторабота_Key": w.get("work_key"),
                    "Количество": w.get("qty", 1),
                    "Цена": w.get("price", 0),
                    "Сумма": w.get("sum", w.get("qty", 1) * w.get("price", 0))
                }
                for w in order["works"]
            ]

        # Add parts to tabular part
        if order.get("parts"):
            doc_data["Товары"] = [
                {
                    "Номенклатура_Key": p.get("part_key"),
                    "Количество": p.get("qty", 1),
                    "Цена": p.get("price", 0),
                    "ПроцентСкидки": p.get("discount", 0),
                    "Сумма": p.get("sum", p.get("qty", 1) * p.get("price", 0))
                }
                for p in order["parts"]
            ]

        # Create document
        result = await fetch_odata("Document_ЗаказНаряд?$format=json", method="POST", data=doc_data)

        if "error" in result:
            return {"success": False, "error": result["error"]}
        if "odata.error" in result:
            return {
                "success": False,
                "error": result.get("odata.error", {}).get("message", {}).get("value", "OData error")
            }

        clear_cache("orders")

        return {
            "success": True,
            "number": result.get("Number", "").strip(),
            "ref": result.get("Ref_Key", ""),
            "message": "Заказ создан"
        }

    except Exception as e:
        return {"success": False, "error": str(e)}


@router.patch("/{ref}")
async def update_order(ref: str, order: dict):
    """Update order status or comment"""
    try:
        update_data = {}

        if order.get("status_key"):
            update_data["Состояние_Key"] = order["status_key"]

        if order.get("comment") is not None:
            update_data["ОписаниеПричиныОбращения"] = order["comment"]

        if not update_data:
            return {"success": False, "error": "No fields to update"}

        result = await fetch_odata(
            f"Document_ЗаказНаряд(guid'{ref}')?$format=json",
            method="PATCH",
            data=update_data
        )

        if "error" in result:
            return {"success": False, "error": result["error"]}

        clear_cache("orders")

        return {"success": True, "message": "Заказ обновлен"}

    except Exception as e:
        return {"success": False, "error": str(e)}
