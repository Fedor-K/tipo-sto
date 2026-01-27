# -*- coding: utf-8 -*-
"""
Car (Automobile) Pydantic Models
"""
from typing import Optional
from pydantic import BaseModel, Field


class CarBase(BaseModel):
    """Base car model"""
    plate: Optional[str] = Field(None, description="License plate (ГосНомер)")
    vin: Optional[str] = Field(None, description="VIN code")
    model_name: Optional[str] = Field(None, description="Model name")


class CarCreate(CarBase):
    """Model for creating a new car"""
    owner_ref: Optional[str] = Field(None, description="Owner client Ref_Key")
    model_ref: Optional[str] = Field(None, description="Model Ref_Key")
    year: Optional[str] = Field(None, description="Year of manufacture")
    color_ref: Optional[str] = Field(None, description="Color Ref_Key")
    body_type_ref: Optional[str] = Field(None, description="Body type Ref_Key")
    engine_type_ref: Optional[str] = Field(None, description="Engine type Ref_Key")
    transmission_ref: Optional[str] = Field(None, description="Transmission type Ref_Key")


class Car(CarBase):
    """Car model from 1C"""
    ref: str = Field(..., description="Ref_Key in 1C")
    code: Optional[str] = Field(None, description="Code in 1C")
    description: Optional[str] = Field(None, description="Full description")
    year: Optional[str] = Field(None, description="Year of manufacture")
    color: Optional[str] = Field(None, description="Color name")
    owner_ref: Optional[str] = Field(None, description="Owner Ref_Key")
    owner_name: Optional[str] = Field(None, description="Owner name")
    model_ref: Optional[str] = Field(None, description="Model Ref_Key")
    mileage: Optional[str] = Field(None, description="Last known mileage")

    class Config:
        from_attributes = True


class CarDetail(Car):
    """Detailed car model with service history"""
    orders_count: int = Field(0, description="Number of orders for this car")
    last_visit: Optional[str] = Field(None, description="Last service date")
    total_spent: float = Field(0.0, description="Total amount spent on this car")
