# TIPO-STO Pydantic Models
from .client import Client, ClientCreate, ClientDetail, CarSummary, OrderSummary
from .car import Car, CarCreate, CarDetail
from .order import Order, OrderCreate, OrderDetail, WorkItem, GoodsItem, OrderStatusUpdate
from .inspection import (
    Inspection, InspectionCreate, InspectionItem, InspectionItemCreate,
    InspectionSummary, InspectionItemStatus, INSPECTION_CATEGORIES
)

__all__ = [
    # Client
    "Client",
    "ClientCreate",
    "ClientDetail",
    "CarSummary",
    "OrderSummary",
    # Car
    "Car",
    "CarCreate",
    "CarDetail",
    # Order
    "Order",
    "OrderCreate",
    "OrderDetail",
    "WorkItem",
    "GoodsItem",
    "OrderStatusUpdate",
    # DVI Inspection
    "Inspection",
    "InspectionCreate",
    "InspectionItem",
    "InspectionItemCreate",
    "InspectionSummary",
    "InspectionItemStatus",
    "INSPECTION_CATEGORIES",
]
