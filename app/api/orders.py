# -*- coding: utf-8 -*-
"""
Orders API Router
"""
from typing import Optional, List
from fastapi import APIRouter, HTTPException, Query

from app.models import Order, OrderCreate, OrderDetail, WorkItem, GoodsItem
from app.services import get_odata_service, get_legacy_service

router = APIRouter(prefix="/orders", tags=["orders"])


def _parse_order(raw: dict) -> Order:
    """Parse raw OData order to Order model"""
    return Order(
        ref=raw.get("Ref_Key"),
        number=raw.get("Number", ""),
        date=raw.get("Date", "")[:10] if raw.get("Date") else "",
        sum=float(raw.get("СуммаДокумента", 0) or 0),
        status=raw.get("Состояние"),
        status_ref=raw.get("Состояние_Key"),
        client_ref=raw.get("Контрагент_Key"),
        client_name=raw.get("Контрагент", {}).get("Description") if isinstance(raw.get("Контрагент"), dict) else None,
        is_legacy=False,
        document_type="ЗаказНаряд",
    )


def _parse_work_item(raw: dict) -> WorkItem:
    """Parse raw OData work to WorkItem"""
    return WorkItem(
        work_ref=raw.get("Работа_Key") or raw.get("Авторабота_Key"),
        name=raw.get("Работа", {}).get("Description", "") if isinstance(raw.get("Работа"), dict) else str(raw.get("Работа", "")),
        quantity=float(raw.get("Количество", 1) or 1),
        price=float(raw.get("Цена", 0) or 0),
        sum=float(raw.get("Сумма", 0) or 0),
        executor_ref=raw.get("Исполнитель_Key"),
    )


def _parse_goods_item(raw: dict) -> GoodsItem:
    """Parse raw OData goods to GoodsItem"""
    return GoodsItem(
        goods_ref=raw.get("Номенклатура_Key"),
        name=raw.get("Номенклатура", {}).get("Description", "") if isinstance(raw.get("Номенклатура"), dict) else str(raw.get("Номенклатура", "")),
        quantity=float(raw.get("Количество", 1) or 1),
        price=float(raw.get("Цена", 0) or 0),
        sum=float(raw.get("Сумма", 0) or 0),
    )


@router.get("", response_model=List[Order])
async def get_orders(
    client_ref: Optional[str] = Query(None, description="Filter by client"),
    status_ref: Optional[str] = Query(None, description="Filter by status"),
    date_from: Optional[str] = Query(None, description="Filter from date (YYYY-MM-DD)"),
    date_to: Optional[str] = Query(None, description="Filter to date (YYYY-MM-DD)"),
    limit: int = Query(50, ge=1, le=200),
):
    """
    Get list of orders.

    - **client_ref**: Optional client Ref_Key filter
    - **status_ref**: Optional status Ref_Key filter
    - **date_from**: Optional start date filter
    - **date_to**: Optional end date filter
    - **limit**: Max number of results (1-200)
    """
    odata = get_odata_service()
    raw_orders = await odata.get_orders(
        client_ref=client_ref,
        status_ref=status_ref,
        date_from=date_from,
        date_to=date_to,
        limit=limit,
    )
    return [_parse_order(o) for o in raw_orders]


@router.get("/{ref}", response_model=OrderDetail)
async def get_order(ref: str):
    """
    Get order details including works and goods.

    - **ref**: Order Ref_Key
    """
    odata = get_odata_service()
    raw_order = await odata.get_order(ref)

    if not raw_order:
        raise HTTPException(status_code=404, detail="Order not found")

    # Parse works
    works = []
    works_sum = 0.0
    for w in raw_order.get("_works", []):
        work = _parse_work_item(w)
        works.append(work)
        works_sum += work.sum

    # Parse goods
    goods = []
    goods_sum = 0.0
    for g in raw_order.get("_parts", []):
        item = _parse_goods_item(g)
        goods.append(item)
        goods_sum += item.sum

    # Get car info from tabular part
    car_ref = None
    car_name = None
    for car in raw_order.get("_cars", []):
        car_ref = car.get("Автомобиль_Key")
        break

    if car_ref:
        car_data = await odata.get_car(car_ref)
        if car_data:
            car_name = car_data.get("Description", "")

    return OrderDetail(
        ref=raw_order.get("Ref_Key"),
        number=raw_order.get("Number", ""),
        date=raw_order.get("Date", "")[:10] if raw_order.get("Date") else "",
        sum=float(raw_order.get("СуммаДокумента", 0) or 0),
        status=raw_order.get("Состояние"),
        status_ref=raw_order.get("Состояние_Key"),
        client_ref=raw_order.get("Контрагент_Key"),
        car_ref=car_ref,
        car_name=car_name,
        car_plate=raw_order.get("ГосНомер"),
        car_vin=raw_order.get("VIN"),
        org_ref=raw_order.get("Организация_Key"),
        division_ref=raw_order.get("ПодразделениеКомпании_Key"),
        workshop_ref=raw_order.get("Цех_Key"),
        repair_type=raw_order.get("ВидРемонта"),
        master_name=raw_order.get("Мастер"),
        mileage=raw_order.get("Пробег"),
        start_date=raw_order.get("ДатаНачала", "")[:10] if raw_order.get("ДатаНачала") else None,
        end_date=raw_order.get("ДатаОкончания", "")[:10] if raw_order.get("ДатаОкончания") else None,
        works=works,
        goods=goods,
        works_sum=works_sum,
        goods_sum=goods_sum,
        is_legacy=False,
        document_type="ЗаказНаряд",
    )


@router.get("/history/{number}", response_model=OrderDetail)
async def get_legacy_order(number: str, client_code: Optional[str] = Query(None, description="Client code for duplicate handling")):
    """
    Get legacy order details from 185.222 data.

    - **number**: Order number
    - **client_code**: Optional client code (for handling duplicate order numbers)
    """
    legacy = get_legacy_service()

    # Get order header info (date, car, sum)
    order_info = legacy.find_order_by_number(number, client_code)
    details = legacy.get_order_details(number)

    if not order_info and not details:
        raise HTTPException(status_code=404, detail="Legacy order not found")

    # Parse works
    works = []
    works_sum = 0.0
    if details:
        for w in details.get("works", []):
            work = WorkItem(
                name=w.get("name", ""),
                quantity=float(w.get("qty", 1) or 1),
                price=float(w.get("price", 0) or 0),
                sum=float(w.get("sum", 0) or 0),
            )
            works.append(work)
            works_sum += work.sum

    # Parse goods
    goods = []
    goods_sum = 0.0
    if details:
        for g in details.get("goods", []):
            item = GoodsItem(
                name=g.get("name", ""),
                quantity=float(g.get("qty", 1) or 1),
                price=float(g.get("price", 0) or 0),
                sum=float(g.get("sum", 0) or 0),
            )
            goods.append(item)
            goods_sum += item.sum

    # Get date and car from order_info
    order_date = order_info.get("date", "") if order_info else ""
    car_name = order_info.get("car_name", "") if order_info else ""
    order_sum = float(order_info.get("sum", 0) or 0) if order_info else (works_sum + goods_sum)

    return OrderDetail(
        ref=None,
        number=number,
        date=order_date,
        sum=order_sum,
        status="История",
        car_name=car_name,
        works=works,
        goods=goods,
        works_sum=works_sum,
        goods_sum=goods_sum,
        is_legacy=True,
        source="185.222",
    )


@router.post("", response_model=Order)
async def create_order(data: OrderCreate):
    """
    Create a new repair request (ЗаявкаНаРемонт).

    - **data**: Order data with client, car, works, goods
    """
    odata = get_odata_service()

    payload = {
        "client_ref": data.client_ref,
        "car_ref": data.car_ref,
        "comment": data.comment or "",
        "repair_type": data.repair_type_ref,
    }

    if data.works:
        payload["works"] = [
            {
                "work_ref": w.work_ref,
                "quantity": w.quantity,
            }
            for w in data.works if w.work_ref
        ]

    result = await odata.create_repair_request(payload)
    return _parse_order(result)


# Status mapping for Kanban columns
KANBAN_STATUS_MAP = {
    "new": "6bd193fc-fa7c-11e5-9841-6cf049a63e1b",       # Заявка
    "progress": "6bd193f9-fa7c-11e5-9841-6cf049a63e1b",  # В работе
    "ready": "6bd193fa-fa7c-11e5-9841-6cf049a63e1b",     # Выполнен
    "done": "6bd193fb-fa7c-11e5-9841-6cf049a63e1b",      # Закрыт
}


@router.patch("/{ref}/status")
async def update_order_status(ref: str, column: str = Query(..., description="Kanban column: new, progress, ready, done")):
    """
    Update order status for Kanban board.

    - **ref**: Order Ref_Key
    - **column**: Target Kanban column (new, progress, ready, done)
    """
    if column not in KANBAN_STATUS_MAP:
        raise HTTPException(status_code=400, detail=f"Invalid column: {column}. Must be one of: {list(KANBAN_STATUS_MAP.keys())}")

    status_ref = KANBAN_STATUS_MAP[column]
    odata = get_odata_service()

    try:
        result = await odata.patch(
            f"Document_ЗаказНаряд(guid'{ref}')",
            {"Состояние_Key": status_ref}
        )
        return {"success": True, "ref": ref, "new_status": column, "status_ref": status_ref}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to update status: {str(e)}")


@router.get("/search/history", response_model=List[Order])
async def search_legacy_orders(
    client_code: Optional[str] = Query(None, description="Client code"),
    date_from: Optional[str] = Query(None, description="From date (YYYY-MM-DD)"),
    date_to: Optional[str] = Query(None, description="To date (YYYY-MM-DD)"),
    limit: int = Query(50, ge=1, le=200),
):
    """
    Search legacy orders from 185.222 data.

    - **client_code**: Optional client code filter
    - **date_from**: Optional start date filter
    - **date_to**: Optional end date filter
    - **limit**: Max results
    """
    legacy = get_legacy_service()
    results = legacy.search_order_history(
        client_code=client_code,
        date_from=date_from,
        date_to=date_to,
        limit=limit,
    )

    orders = []
    for r in results:
        formatted = legacy.format_legacy_order(r, r.get("client_code"))
        orders.append(Order(
            ref=None,
            number=formatted.get("number", ""),
            date=formatted.get("date", ""),
            sum=formatted.get("sum", 0),
            status="История",
            client_code=r.get("client_code"),
            car_name=formatted.get("car_name"),
            is_legacy=True,
            source="185.222",
        ))

    return orders
