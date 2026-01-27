# -*- coding: utf-8 -*-
"""
DVI (Digital Vehicle Inspection) Models
"""
from typing import Optional, List
from datetime import datetime
from pydantic import BaseModel, Field
from enum import Enum


class InspectionItemStatus(str, Enum):
    """Status of inspection item"""
    OK = "ok"           # Всё в порядке
    ATTENTION = "attention"  # Требует внимания (скоро)
    URGENT = "urgent"   # Требует срочного ремонта


class InspectionItemCreate(BaseModel):
    """Create inspection item"""
    category: str = Field(..., description="Категория: engine, brakes, suspension, body, interior, lights, tires, fluids, other")
    name: str = Field(..., description="Название пункта проверки")
    status: InspectionItemStatus = Field(..., description="Статус: ok, attention, urgent")
    notes: Optional[str] = Field(None, description="Комментарий механика")
    photo_ids: List[str] = Field(default_factory=list, description="ID загруженных фото")
    recommended_work: Optional[str] = Field(None, description="Рекомендуемая работа")
    estimated_cost: Optional[float] = Field(None, description="Примерная стоимость")


class InspectionItem(InspectionItemCreate):
    """Inspection item with full data"""
    id: str
    photo_urls: List[str] = Field(default_factory=list)
    approved: Optional[bool] = Field(None, description="Одобрено клиентом")
    approved_at: Optional[str] = None


class InspectionCreate(BaseModel):
    """Create new inspection"""
    order_ref: Optional[str] = Field(None, description="Связанный заказ-наряд")
    car_ref: Optional[str] = Field(None, description="Автомобиль")
    car_plate: Optional[str] = Field(None, description="Гос. номер")
    car_vin: Optional[str] = Field(None, description="VIN")
    client_ref: Optional[str] = Field(None, description="Клиент")
    client_phone: Optional[str] = Field(None, description="Телефон клиента для отправки")
    mileage: Optional[int] = Field(None, description="Пробег")
    mechanic_name: Optional[str] = Field(None, description="Механик")


class Inspection(BaseModel):
    """Full inspection"""
    id: str
    order_ref: Optional[str] = None
    car_ref: Optional[str] = None
    car_plate: Optional[str] = None
    car_vin: Optional[str] = None
    car_name: Optional[str] = None
    client_ref: Optional[str] = None
    client_name: Optional[str] = None
    client_phone: Optional[str] = None
    mileage: Optional[int] = None
    mechanic_name: Optional[str] = None

    items: List[InspectionItem] = Field(default_factory=list)

    created_at: str
    updated_at: Optional[str] = None
    sent_to_client: bool = False
    sent_at: Optional[str] = None

    # Summary
    total_items: int = 0
    ok_count: int = 0
    attention_count: int = 0
    urgent_count: int = 0
    approved_count: int = 0
    total_estimated: float = 0.0

    # Client access
    public_token: Optional[str] = Field(None, description="Токен для клиентского доступа")
    public_url: Optional[str] = None


class InspectionSummary(BaseModel):
    """Short inspection info for lists"""
    id: str
    car_plate: Optional[str] = None
    car_name: Optional[str] = None
    client_name: Optional[str] = None
    created_at: str
    mechanic_name: Optional[str] = None
    ok_count: int = 0
    attention_count: int = 0
    urgent_count: int = 0
    sent_to_client: bool = False


# Стандартные категории проверки
INSPECTION_CATEGORIES = {
    "engine": {
        "name": "Двигатель",
        "icon": "🔧",
        "items": [
            "Уровень масла",
            "Состояние масла",
            "Утечки масла",
            "Ремень ГРМ",
            "Ремень генератора",
            "Свечи зажигания",
            "Воздушный фильтр",
            "Топливный фильтр",
        ]
    },
    "brakes": {
        "name": "Тормозная система",
        "icon": "🛑",
        "items": [
            "Передние колодки",
            "Задние колодки",
            "Передние диски",
            "Задние диски",
            "Тормозная жидкость",
            "Тормозные шланги",
            "Ручной тормоз",
        ]
    },
    "suspension": {
        "name": "Подвеска",
        "icon": "🔩",
        "items": [
            "Амортизаторы передние",
            "Амортизаторы задние",
            "Сайлентблоки",
            "Шаровые опоры",
            "Рулевые наконечники",
            "Рулевая рейка",
            "Стойки стабилизатора",
        ]
    },
    "tires": {
        "name": "Шины и диски",
        "icon": "🛞",
        "items": [
            "Глубина протектора ПЛ",
            "Глубина протектора ПП",
            "Глубина протектора ЗЛ",
            "Глубина протектора ЗП",
            "Давление в шинах",
            "Состояние дисков",
            "Износ шин",
        ]
    },
    "fluids": {
        "name": "Жидкости",
        "icon": "💧",
        "items": [
            "Антифриз",
            "Жидкость ГУР",
            "Тормозная жидкость",
            "Жидкость омывателя",
            "Масло АКПП/МКПП",
        ]
    },
    "lights": {
        "name": "Освещение",
        "icon": "💡",
        "items": [
            "Фары ближний свет",
            "Фары дальний свет",
            "Габариты",
            "Поворотники",
            "Стоп-сигналы",
            "Задний ход",
            "Противотуманки",
        ]
    },
    "body": {
        "name": "Кузов",
        "icon": "🚗",
        "items": [
            "Лакокрасочное покрытие",
            "Стёкла",
            "Дворники",
            "Зеркала",
            "Двери",
            "Замки",
            "Днище",
        ]
    },
    "interior": {
        "name": "Салон",
        "icon": "🪑",
        "items": [
            "Кондиционер",
            "Печка",
            "Панель приборов",
            "Ремни безопасности",
            "Сиденья",
            "Руль",
        ]
    },
}
