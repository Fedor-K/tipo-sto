# -*- coding: utf-8 -*-
"""
Clients API Router
"""
from typing import Optional, List
from fastapi import APIRouter, HTTPException, Query

from app.models import Client, ClientCreate, ClientDetail, CarSummary, OrderSummary
from app.services import get_odata_service, get_legacy_service

router = APIRouter(prefix="/clients", tags=["clients"])


def _parse_client(raw: dict) -> Client:
    """Parse raw OData client to Client model"""
    # Extract phone from contact info
    contact_info = raw.get("КонтактнаяИнформация", "")
    phone = None
    email = None
    if contact_info:
        # Try to extract phone
        import re
        phone_match = re.search(r'[\d\s\-\+\(\)]{10,}', contact_info)
        if phone_match:
            phone = phone_match.group().strip()
        # Try to extract email
        email_match = re.search(r'[\w\.-]+@[\w\.-]+\.\w+', contact_info)
        if email_match:
            email = email_match.group()

    return Client(
        ref=raw.get("Ref_Key", ""),
        code=raw.get("Code", ""),
        name=raw.get("Description", ""),
        inn=raw.get("ИНН", ""),
        comment=raw.get("Комментарий", ""),
        phone=phone,
        email=email,
        is_folder=raw.get("IsFolder", False),
    )


def _parse_car_summary(raw: dict) -> CarSummary:
    """Parse raw OData car to CarSummary"""
    return CarSummary(
        ref=raw.get("Ref_Key", ""),
        plate=raw.get("ГосНомер", ""),
        vin=raw.get("VIN", ""),
        model_name=raw.get("Description", ""),
        year=raw.get("ГодВыпуска", "")[:4] if raw.get("ГодВыпуска") else None,
    )


def _parse_legacy_car_name(car_name: str) -> Optional[CarSummary]:
    """
    Parse legacy car_name string to CarSummary.
    Example: "MERCEDES-BENZ S450 ЧЕРНЫЙ № В777ОЕ161 VIN WDD2211861A216643"
    """
    import re

    if not car_name:
        return None

    plate = None
    vin = None
    model_name = car_name

    # Extract plate: № XXXXX or №XXXXX
    plate_match = re.search(r'№\s*([А-ЯA-Z0-9]+)', car_name, re.IGNORECASE)
    if plate_match:
        plate = plate_match.group(1)

    # Extract VIN: VIN XXXXXXXXX
    vin_match = re.search(r'VIN\s+([A-Z0-9]{17})', car_name, re.IGNORECASE)
    if vin_match:
        vin = vin_match.group(1)

    # Extract model: everything before № or VIN
    model_match = re.match(r'^([^№]+?)(?:\s+(?:№|VIN)|\s*$)', car_name)
    if model_match:
        model_name = model_match.group(1).strip()

    return CarSummary(
        ref="legacy",  # Mark as legacy car
        plate=plate,
        vin=vin,
        model_name=model_name,
        year=None,
    )


@router.get("", response_model=List[Client])
async def get_clients(
    search: Optional[str] = Query(None, description="Search by name"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    """
    Get list of clients.

    - **search**: Optional search string for client name
    - **limit**: Max number of results (1-200)
    - **offset**: Skip first N results
    """
    odata = get_odata_service()
    raw_clients = await odata.get_clients(search=search, limit=limit, offset=offset)
    return [_parse_client(c) for c in raw_clients if not c.get("IsFolder", False)]


@router.get("/{ref}", response_model=ClientDetail)
async def get_client(ref: str):
    """
    Get client details including cars and orders.

    - **ref**: Client Ref_Key
    """
    odata = get_odata_service()
    legacy = get_legacy_service()

    # Get client
    raw_client = await odata.get_client(ref)
    if not raw_client:
        raise HTTPException(status_code=404, detail="Client not found")

    client = _parse_client(raw_client)
    client_code = (client.code or "").strip()  # Strip trailing spaces for legacy lookup

    # Get client's cars from legacy mapping (by ref)
    car_refs = legacy.get_client_cars(ref)
    cars = []
    seen_cars = set()  # Track unique cars

    for car_ref in car_refs:
        raw_car = await odata.get_car(car_ref)
        if raw_car:
            cars.append(_parse_car_summary(raw_car))
            seen_cars.add(car_ref)

    # Get orders from 1C
    raw_orders = await odata.get_orders(client_ref=ref, limit=100)
    orders = []
    total_sum = 0.0

    for o in raw_orders:
        order_sum = float(o.get("СуммаДокумента", 0) or 0)
        total_sum += order_sum
        orders.append(OrderSummary(
            ref=o.get("Ref_Key"),
            number=o.get("Number", ""),
            date=o.get("Date", "")[:10] if o.get("Date") else "",
            sum=order_sum,
            status=o.get("Состояние_Key"),
            is_legacy=False,
        ))

    # Add legacy orders and extract cars from them
    legacy_orders = legacy.get_client_order_history(client_code)
    legacy_cars_seen = set()  # Track unique cars from legacy by car_name

    for lo in legacy_orders:
        formatted = legacy.format_legacy_order(lo, client_code)
        order_sum = formatted.get("sum", 0)
        total_sum += order_sum

        car_name = formatted.get("car_name", "")
        orders.append(OrderSummary(
            ref=None,
            number=formatted.get("number", ""),
            date=formatted.get("date", ""),
            sum=order_sum,
            status="История",
            car_name=car_name,
            is_legacy=True,
        ))

        # Extract car from legacy order if not seen
        if car_name and car_name not in legacy_cars_seen:
            legacy_cars_seen.add(car_name)
            # Parse car_name: "MERCEDES-BENZ S450 ЧЕРНЫЙ № В777ОЕ161 VIN WDD2211861A216643"
            car_info = _parse_legacy_car_name(car_name)
            if car_info:
                cars.append(car_info)

    # Sort by date descending
    orders.sort(key=lambda x: x.date or "", reverse=True)

    return ClientDetail(
        ref=client.ref,
        code=client.code,
        name=client.name,
        inn=client.inn,
        comment=client.comment,
        phone=client.phone,
        email=client.email,
        is_folder=client.is_folder,
        cars=cars,
        orders=orders,
        total_orders=len(orders),
        total_sum=total_sum,
    )


@router.get("/search/phone/{phone}", response_model=Optional[Client])
async def find_client_by_phone(phone: str):
    """
    Find client by phone number.

    - **phone**: Phone number to search
    """
    odata = get_odata_service()
    raw_client = await odata.find_client_by_phone(phone)
    if not raw_client:
        return None
    return _parse_client(raw_client)


@router.post("", response_model=Client)
async def create_client(data: ClientCreate):
    """
    Create a new client.

    - **data**: Client data
    """
    odata = get_odata_service()
    result = await odata.create_client(data.model_dump())
    return _parse_client(result)
