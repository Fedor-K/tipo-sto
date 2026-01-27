# TIPO-STO API Routers
from .clients import router as clients_router
from .orders import router as orders_router
from .inspections import router as inspections_router
from .assistant import router as assistant_router

__all__ = ["clients_router", "orders_router", "inspections_router", "assistant_router"]
