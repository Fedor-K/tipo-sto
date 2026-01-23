"""Pydantic models for request/response validation"""
from typing import Optional, List
from pydantic import BaseModel


# ===== Client Models =====

class ClientBase(BaseModel):
    name: str
    phone: Optional[str] = ""
    inn: Optional[str] = ""
    comment: Optional[str] = ""


class ClientCreate(ClientBase):
    pass


class ClientResponse(BaseModel):
    code: str
    name: str
    phone: str = ""
    address: str = ""
    ref: str
    inn: str = ""


class ClientDetailResponse(BaseModel):
    client: ClientResponse
    cars: List["CarResponse"] = []
    orders: List["OrderResponse"] = []
    cars_count: int = 0
    orders_count: int = 0
    total_sum: float = 0


# ===== Car Models =====

class CarBase(BaseModel):
    name: str
    vin: Optional[str] = ""
    plate: Optional[str] = ""


class CarCreate(CarBase):
    owner_key: Optional[str] = None


class CarResponse(BaseModel):
    code: str
    name: str
    vin: str = ""
    plate: str = ""
    ref: str
    owner_key: Optional[str] = None


# ===== Order Models =====

class OrderWorkItem(BaseModel):
    work_key: str
    name: str
    qty: float = 1
    price: float = 0
    sum: float = 0


class OrderPartItem(BaseModel):
    part_key: str
    name: str
    qty: float = 1
    price: float = 0
    discount: float = 0
    sum: float = 0


class OrderCreate(BaseModel):
    client_key: str
    car_key: Optional[str] = None
    repair_type_key: Optional[str] = None
    workshop_key: Optional[str] = None
    master_key: Optional[str] = None
    mileage: Optional[str] = "0"
    comment: Optional[str] = ""
    works: List[OrderWorkItem] = []
    parts: List[OrderPartItem] = []


class OrderUpdate(BaseModel):
    status_key: Optional[str] = None
    comment: Optional[str] = None


class OrderResponse(BaseModel):
    number: str
    date: str
    client: str = ""
    client_key: str = ""
    car: str = ""
    status: str = ""
    sum: float = 0
    comment: str = ""
    ref: str = ""


class OrderDetailResponse(OrderResponse):
    works: List[dict] = []
    parts: List[dict] = []


# ===== Catalog Models =====

class CatalogItem(BaseModel):
    code: str
    name: str
    ref: str


class CatalogResponse(BaseModel):
    items: List[CatalogItem]
    count: int
    source: str = "odata"


# ===== Stats Models =====

class DashboardStats(BaseModel):
    orders_today: int = 0
    sum_today: float = 0
    in_progress: int = 0
    total_orders: int = 0
    total_sum: float = 0
    clients_count: int = 0
    cars_count: int = 0


# ===== Search Models =====

class SearchResult(BaseModel):
    type: str  # "client", "car", "order"
    code: str = ""
    name: str = ""
    ref: str = ""
    # For cars
    vin: Optional[str] = None
    plate: Optional[str] = None
    # For orders
    number: Optional[str] = None
    date: Optional[str] = None
    sum: Optional[float] = None
    status: Optional[str] = None


class SearchResponse(BaseModel):
    results: List[SearchResult]
    query: str
    total: int


# Update forward references
ClientDetailResponse.model_rebuild()
