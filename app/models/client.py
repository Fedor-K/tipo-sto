# -*- coding: utf-8 -*-
"""
Client Pydantic Models
"""
from typing import Optional, List
from pydantic import BaseModel, Field


class ClientBase(BaseModel):
    """Base client model"""
    name: str = Field(..., description="Client name (Description in 1C)")
    inn: Optional[str] = Field(None, description="INN (tax ID)")
    comment: Optional[str] = Field(None, description="Comment")


class ClientCreate(ClientBase):
    """Model for creating a new client"""
    phone: Optional[str] = Field(None, description="Phone number")
    email: Optional[str] = Field(None, description="Email address")


class Client(ClientBase):
    """Client model from 1C"""
    ref: str = Field(..., description="Ref_Key in 1C")
    code: Optional[str] = Field(None, description="Code in 1C")
    phone: Optional[str] = Field(None, description="Phone number")
    email: Optional[str] = Field(None, description="Email address")
    is_folder: bool = Field(False, description="Is folder in hierarchy")

    class Config:
        from_attributes = True


class ClientDetail(Client):
    """Detailed client model with cars and orders"""
    cars: List["CarSummary"] = Field(default_factory=list, description="Client's cars")
    orders: List["OrderSummary"] = Field(default_factory=list, description="Client's orders")
    total_orders: int = Field(0, description="Total orders count")
    total_sum: float = Field(0.0, description="Total sum of all orders")


# Forward references for circular imports
class CarSummary(BaseModel):
    """Summary car info for client detail"""
    ref: str
    plate: Optional[str] = None
    vin: Optional[str] = None
    model_name: Optional[str] = None
    year: Optional[str] = None


class OrderSummary(BaseModel):
    """Summary order info for client detail"""
    ref: Optional[str] = None
    number: str
    date: str
    sum: float = 0.0
    status: Optional[str] = None
    car_name: Optional[str] = None
    is_legacy: bool = False


# Update forward references
ClientDetail.model_rebuild()
