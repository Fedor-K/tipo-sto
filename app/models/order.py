# -*- coding: utf-8 -*-
"""
Order (ЗаказНаряд / ЗаявкаНаРемонт) Pydantic Models
"""
from typing import Optional, List
from datetime import datetime
from pydantic import BaseModel, Field


class WorkItem(BaseModel):
    """Work item in order"""
    work_ref: Optional[str] = Field(None, description="Work Ref_Key")
    name: str = Field(..., description="Work name")
    quantity: float = Field(1.0, description="Quantity")
    price: float = Field(0.0, description="Price per unit")
    sum: float = Field(0.0, description="Total sum")
    executor_ref: Optional[str] = Field(None, description="Executor Ref_Key")
    executor_name: Optional[str] = Field(None, description="Executor name")


class GoodsItem(BaseModel):
    """Goods/parts item in order"""
    goods_ref: Optional[str] = Field(None, description="Nomenclature Ref_Key")
    name: str = Field(..., description="Goods name")
    quantity: float = Field(1.0, description="Quantity")
    price: float = Field(0.0, description="Price per unit")
    sum: float = Field(0.0, description="Total sum")
    unit: Optional[str] = Field(None, description="Unit of measurement")


class OrderBase(BaseModel):
    """Base order model"""
    client_ref: str = Field(..., description="Client Ref_Key")
    car_ref: Optional[str] = Field(None, description="Car Ref_Key")
    comment: Optional[str] = Field(None, description="Comment / reason")


class OrderCreate(OrderBase):
    """Model for creating a new order"""
    repair_type_ref: Optional[str] = Field(None, description="Repair type Ref_Key")
    workshop_ref: Optional[str] = Field(None, description="Workshop Ref_Key")
    master_ref: Optional[str] = Field(None, description="Master Ref_Key")
    start_date: Optional[datetime] = Field(None, description="Planned start date")
    end_date: Optional[datetime] = Field(None, description="Planned end date")
    mileage: Optional[str] = Field(None, description="Current mileage")
    works: List[WorkItem] = Field(default_factory=list, description="Works to perform")
    goods: List[GoodsItem] = Field(default_factory=list, description="Parts/goods")


class Order(BaseModel):
    """Order model from 1C"""
    ref: Optional[str] = Field(None, description="Ref_Key in 1C (None for legacy)")
    number: str = Field(..., description="Order number")
    date: str = Field(..., description="Order date")
    sum: float = Field(0.0, description="Total sum")
    status: Optional[str] = Field(None, description="Status name")
    status_ref: Optional[str] = Field(None, description="Status Ref_Key")

    # Client info
    client_ref: Optional[str] = Field(None, description="Client Ref_Key")
    client_name: Optional[str] = Field(None, description="Client name")
    client_code: Optional[str] = Field(None, description="Client code")

    # Car info
    car_ref: Optional[str] = Field(None, description="Car Ref_Key")
    car_name: Optional[str] = Field(None, description="Car description")
    car_plate: Optional[str] = Field(None, description="Car license plate")
    car_vin: Optional[str] = Field(None, description="Car VIN")

    # Metadata
    is_legacy: bool = Field(False, description="Is from legacy 185.222 system")
    source: Optional[str] = Field(None, description="Data source")
    document_type: Optional[str] = Field(None, description="Document type (ЗаказНаряд/ЗаявкаНаРемонт)")

    class Config:
        from_attributes = True


class OrderDetail(Order):
    """Detailed order with works and goods"""
    # Organization info
    org_ref: Optional[str] = Field(None, description="Organization Ref_Key")
    division_ref: Optional[str] = Field(None, description="Division Ref_Key")
    workshop_ref: Optional[str] = Field(None, description="Workshop Ref_Key")

    # Additional info
    repair_type: Optional[str] = Field(None, description="Repair type name")
    master_name: Optional[str] = Field(None, description="Master name")
    mileage: Optional[str] = Field(None, description="Mileage at service")

    # Dates
    start_date: Optional[str] = Field(None, description="Planned start")
    end_date: Optional[str] = Field(None, description="Planned end")

    # Tabular parts
    works: List[WorkItem] = Field(default_factory=list, description="Works performed")
    goods: List[GoodsItem] = Field(default_factory=list, description="Parts/goods used")

    # Totals
    works_sum: float = Field(0.0, description="Sum of works")
    goods_sum: float = Field(0.0, description="Sum of goods")


class OrderStatusUpdate(BaseModel):
    """Model for updating order status"""
    status_ref: str = Field(..., description="New status Ref_Key")
    comment: Optional[str] = Field(None, description="Status change comment")
