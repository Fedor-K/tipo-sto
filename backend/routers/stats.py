"""Stats router - /api/stats endpoints for dashboard statistics"""
from datetime import datetime
from fastapi import APIRouter

from ..odata import fetch_odata

router = APIRouter(prefix="/api/stats", tags=["stats"])


@router.get("/dashboard")
async def get_dashboard_stats():
    """
    Get dashboard statistics

    Returns:
        - orders_today: Number of orders created today
        - sum_today: Total sum of today's orders
        - in_progress: Number of unposted (draft) orders
        - total_orders: Total orders count (limited)
        - total_sum: Total sum of orders
        - clients_count: Total clients
        - cars_count: Total cars
    """
    try:
        # Get recent orders
        orders_data = await fetch_odata(
            "Document_ЗаказНаряд?$top=500&$orderby=Date desc&$format=json"
        )
        orders = orders_data.get("value", [])

        # Today's date
        today = datetime.now().strftime("%Y-%m-%d")

        # Calculate stats
        orders_today = 0
        sum_today = 0.0
        in_progress = 0
        total_sum = 0.0

        for order in orders:
            order_date = str(order.get("Date", ""))[:10]
            sum_parts = float(order.get("СуммаНоменклатурыДокумента", 0) or 0)
            sum_works = float(order.get("СуммаРаботДокумента", 0) or 0)
            order_sum = sum_parts + sum_works
            posted = order.get("Posted", False)

            total_sum += order_sum

            if order_date == today:
                orders_today += 1
                sum_today += order_sum

            if not posted:
                in_progress += 1

        # Count clients and cars (with fallback)
        clients_count = 0
        cars_count = 0

        try:
            clients_resp = await fetch_odata("Catalog_Контрагенты/$count")
            if isinstance(clients_resp, (int, str)):
                clients_count = int(clients_resp)
        except:
            # Fallback: count from limited query
            clients_data = await fetch_odata("Catalog_Контрагенты?$top=1000&$select=Ref_Key&$format=json")
            clients_count = len(clients_data.get("value", []))

        try:
            cars_resp = await fetch_odata("Catalog_Автомобили/$count")
            if isinstance(cars_resp, (int, str)):
                cars_count = int(cars_resp)
        except:
            # Fallback: count from limited query
            cars_data = await fetch_odata("Catalog_Автомобили?$top=1000&$select=Ref_Key&$format=json")
            cars_count = len(cars_data.get("value", []))

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
        return {
            "error": str(e),
            "orders_today": 0,
            "sum_today": 0,
            "in_progress": 0,
            "total_orders": 0,
            "total_sum": 0,
            "clients_count": 0,
            "cars_count": 0
        }
