# -*- coding: utf-8 -*-
"""
DVI (Digital Vehicle Inspection) Service
"""
import json
import uuid
import secrets
import logging
from pathlib import Path
from datetime import datetime
from typing import Optional, List, Dict, Any

from app.config import get_settings
from app.models.inspection import (
    Inspection, InspectionCreate, InspectionItem, InspectionItemCreate,
    InspectionSummary, InspectionItemStatus, INSPECTION_CATEGORIES
)

logger = logging.getLogger(__name__)


class InspectionService:
    """Service for managing DVI inspections"""

    def __init__(self):
        self.settings = get_settings()
        self._inspections: Dict[str, dict] = {}
        self._photos_dir = self.settings.DATA_DIR / "dvi_photos"
        self._data_file = self.settings.DATA_DIR / "inspections.json"
        self._loaded = False

    def _ensure_dirs(self):
        """Ensure required directories exist"""
        self._photos_dir.mkdir(parents=True, exist_ok=True)

    def _load_data(self):
        """Load inspections from file"""
        if self._loaded:
            return
        self._ensure_dirs()
        if self._data_file.exists():
            with open(self._data_file, "r", encoding="utf-8") as f:
                self._inspections = json.load(f)
            logger.info(f"Loaded {len(self._inspections)} inspections")
        self._loaded = True

    def _save_data(self):
        """Save inspections to file"""
        self._ensure_dirs()
        with open(self._data_file, "w", encoding="utf-8") as f:
            json.dump(self._inspections, f, ensure_ascii=False, indent=2)

    def _generate_id(self) -> str:
        """Generate unique inspection ID"""
        return f"DVI-{datetime.now().strftime('%Y%m%d')}-{secrets.token_hex(4).upper()}"

    def _generate_token(self) -> str:
        """Generate public access token"""
        return secrets.token_urlsafe(32)

    def _to_model(self, data: dict) -> Inspection:
        """Convert dict to Inspection model"""
        items = [InspectionItem(**item) for item in data.get("items", [])]

        # Calculate summary
        ok_count = sum(1 for i in items if i.status == InspectionItemStatus.OK)
        attention_count = sum(1 for i in items if i.status == InspectionItemStatus.ATTENTION)
        urgent_count = sum(1 for i in items if i.status == InspectionItemStatus.URGENT)
        approved_count = sum(1 for i in items if i.approved is True)
        total_estimated = sum(i.estimated_cost or 0 for i in items if i.status != InspectionItemStatus.OK)

        return Inspection(
            id=data["id"],
            order_ref=data.get("order_ref"),
            car_ref=data.get("car_ref"),
            car_plate=data.get("car_plate"),
            car_vin=data.get("car_vin"),
            car_name=data.get("car_name"),
            client_ref=data.get("client_ref"),
            client_name=data.get("client_name"),
            client_phone=data.get("client_phone"),
            mileage=data.get("mileage"),
            mechanic_name=data.get("mechanic_name"),
            items=items,
            created_at=data["created_at"],
            updated_at=data.get("updated_at"),
            sent_to_client=data.get("sent_to_client", False),
            sent_at=data.get("sent_at"),
            total_items=len(items),
            ok_count=ok_count,
            attention_count=attention_count,
            urgent_count=urgent_count,
            approved_count=approved_count,
            total_estimated=total_estimated,
            public_token=data.get("public_token"),
            public_url=f"/dvi/{data['id']}?token={data.get('public_token')}" if data.get("public_token") else None,
        )

    def _to_summary(self, data: dict) -> InspectionSummary:
        """Convert dict to InspectionSummary"""
        items = data.get("items", [])
        return InspectionSummary(
            id=data["id"],
            car_plate=data.get("car_plate"),
            car_name=data.get("car_name"),
            client_name=data.get("client_name"),
            created_at=data["created_at"],
            mechanic_name=data.get("mechanic_name"),
            ok_count=sum(1 for i in items if i.get("status") == "ok"),
            attention_count=sum(1 for i in items if i.get("status") == "attention"),
            urgent_count=sum(1 for i in items if i.get("status") == "urgent"),
            sent_to_client=data.get("sent_to_client", False),
        )

    # ==================== CRUD Operations ====================

    def create_inspection(self, data: InspectionCreate) -> Inspection:
        """Create new inspection"""
        self._load_data()

        inspection_id = self._generate_id()
        now = datetime.now().isoformat()

        inspection_data = {
            "id": inspection_id,
            "order_ref": data.order_ref,
            "car_ref": data.car_ref,
            "car_plate": data.car_plate,
            "car_vin": data.car_vin,
            "client_ref": data.client_ref,
            "client_phone": data.client_phone,
            "mileage": data.mileage,
            "mechanic_name": data.mechanic_name,
            "items": [],
            "created_at": now,
            "public_token": self._generate_token(),
        }

        self._inspections[inspection_id] = inspection_data
        self._save_data()

        logger.info(f"Created inspection {inspection_id}")
        return self._to_model(inspection_data)

    def get_inspection(self, inspection_id: str) -> Optional[Inspection]:
        """Get inspection by ID"""
        self._load_data()
        data = self._inspections.get(inspection_id)
        if not data:
            return None
        return self._to_model(data)

    def get_inspection_by_token(self, inspection_id: str, token: str) -> Optional[Inspection]:
        """Get inspection by ID and public token (for client access)"""
        self._load_data()
        data = self._inspections.get(inspection_id)
        if not data:
            return None
        if data.get("public_token") != token:
            return None
        return self._to_model(data)

    def list_inspections(
        self,
        order_ref: str = None,
        car_ref: str = None,
        client_ref: str = None,
        date_from: str = None,
        date_to: str = None,
        limit: int = 50,
    ) -> List[InspectionSummary]:
        """List inspections with filters"""
        self._load_data()

        results = []
        for data in self._inspections.values():
            # Apply filters
            if order_ref and data.get("order_ref") != order_ref:
                continue
            if car_ref and data.get("car_ref") != car_ref:
                continue
            if client_ref and data.get("client_ref") != client_ref:
                continue
            if date_from and data.get("created_at", "")[:10] < date_from:
                continue
            if date_to and data.get("created_at", "")[:10] > date_to:
                continue
            results.append(data)

        # Sort by date descending
        results.sort(key=lambda x: x.get("created_at", ""), reverse=True)

        return [self._to_summary(d) for d in results[:limit]]

    def update_inspection(self, inspection_id: str, updates: dict) -> Optional[Inspection]:
        """Update inspection fields"""
        self._load_data()
        if inspection_id not in self._inspections:
            return None

        data = self._inspections[inspection_id]
        allowed_fields = ["car_plate", "car_vin", "car_name", "client_name", "client_phone", "mileage", "mechanic_name", "order_ref", "order_number"]

        for field in allowed_fields:
            if field in updates:
                data[field] = updates[field]

        data["updated_at"] = datetime.now().isoformat()
        self._save_data()

        return self._to_model(data)

    def delete_inspection(self, inspection_id: str) -> bool:
        """Delete inspection"""
        self._load_data()
        if inspection_id not in self._inspections:
            return False

        # Delete photos
        data = self._inspections[inspection_id]
        for item in data.get("items", []):
            for photo_id in item.get("photo_ids", []):
                self._delete_photo_file(photo_id)

        del self._inspections[inspection_id]
        self._save_data()
        return True

    # ==================== Inspection Items ====================

    def add_item(self, inspection_id: str, item: InspectionItemCreate) -> Optional[InspectionItem]:
        """Add item to inspection"""
        self._load_data()
        if inspection_id not in self._inspections:
            return None

        item_id = str(uuid.uuid4())[:8]
        item_data = {
            "id": item_id,
            "category": item.category,
            "name": item.name,
            "status": item.status.value,
            "notes": item.notes,
            "photo_ids": item.photo_ids,
            "photo_urls": [f"/api/dvi/photos/{pid}" for pid in item.photo_ids],
            "recommended_work": item.recommended_work,
            "estimated_cost": item.estimated_cost,
            "approved": None,
        }

        self._inspections[inspection_id]["items"].append(item_data)
        self._inspections[inspection_id]["updated_at"] = datetime.now().isoformat()
        self._save_data()

        return InspectionItem(**item_data)

    def update_item(self, inspection_id: str, item_id: str, updates: dict) -> Optional[InspectionItem]:
        """Update inspection item"""
        self._load_data()
        if inspection_id not in self._inspections:
            return None

        data = self._inspections[inspection_id]
        for item in data.get("items", []):
            if item["id"] == item_id:
                allowed_fields = ["status", "notes", "recommended_work", "estimated_cost"]
                for field in allowed_fields:
                    if field in updates:
                        item[field] = updates[field]
                data["updated_at"] = datetime.now().isoformat()
                self._save_data()
                return InspectionItem(**item)

        return None

    def delete_item(self, inspection_id: str, item_id: str) -> bool:
        """Delete item from inspection"""
        self._load_data()
        if inspection_id not in self._inspections:
            return False

        data = self._inspections[inspection_id]
        items = data.get("items", [])

        for i, item in enumerate(items):
            if item["id"] == item_id:
                # Delete photos
                for photo_id in item.get("photo_ids", []):
                    self._delete_photo_file(photo_id)
                items.pop(i)
                data["updated_at"] = datetime.now().isoformat()
                self._save_data()
                return True

        return False

    # ==================== Photos ====================

    def save_photo(self, photo_data: bytes, filename: str) -> str:
        """Save photo and return photo ID"""
        self._ensure_dirs()

        photo_id = f"{secrets.token_hex(8)}_{filename}"
        photo_path = self._photos_dir / photo_id

        with open(photo_path, "wb") as f:
            f.write(photo_data)

        logger.info(f"Saved photo {photo_id}")
        return photo_id

    def get_photo_path(self, photo_id: str) -> Optional[Path]:
        """Get photo file path"""
        self._ensure_dirs()
        photo_path = self._photos_dir / photo_id
        if photo_path.exists():
            return photo_path
        return None

    def _delete_photo_file(self, photo_id: str):
        """Delete photo file"""
        photo_path = self._photos_dir / photo_id
        if photo_path.exists():
            photo_path.unlink()

    def add_photo_to_item(self, inspection_id: str, item_id: str, photo_id: str) -> bool:
        """Add photo to inspection item"""
        self._load_data()
        if inspection_id not in self._inspections:
            return False

        data = self._inspections[inspection_id]
        for item in data.get("items", []):
            if item["id"] == item_id:
                if "photo_ids" not in item:
                    item["photo_ids"] = []
                if "photo_urls" not in item:
                    item["photo_urls"] = []
                item["photo_ids"].append(photo_id)
                item["photo_urls"].append(f"/api/dvi/photos/{photo_id}")
                data["updated_at"] = datetime.now().isoformat()
                self._save_data()
                return True

        return False

    # ==================== Client Actions ====================

    def mark_sent_to_client(self, inspection_id: str) -> bool:
        """Mark inspection as sent to client"""
        self._load_data()
        if inspection_id not in self._inspections:
            return False

        data = self._inspections[inspection_id]
        data["sent_to_client"] = True
        data["sent_at"] = datetime.now().isoformat()
        self._save_data()
        return True

    def approve_item(self, inspection_id: str, item_id: str, token: str, approved: bool) -> bool:
        """Client approves/declines item"""
        self._load_data()
        if inspection_id not in self._inspections:
            return False

        data = self._inspections[inspection_id]
        if data.get("public_token") != token:
            return False

        for item in data.get("items", []):
            if item["id"] == item_id:
                item["approved"] = approved
                item["approved_at"] = datetime.now().isoformat()
                data["updated_at"] = datetime.now().isoformat()
                self._save_data()
                return True

        return False

    def approve_all(self, inspection_id: str, token: str, item_ids: List[str]) -> int:
        """Client approves multiple items"""
        self._load_data()
        if inspection_id not in self._inspections:
            return 0

        data = self._inspections[inspection_id]
        if data.get("public_token") != token:
            return 0

        count = 0
        now = datetime.now().isoformat()

        for item in data.get("items", []):
            if item["id"] in item_ids:
                item["approved"] = True
                item["approved_at"] = now
                count += 1

        if count > 0:
            data["updated_at"] = now
            self._save_data()

        return count

    # ==================== Templates ====================

    def get_categories(self) -> dict:
        """Get inspection categories template"""
        return INSPECTION_CATEGORIES


# Singleton
_inspection_service: Optional[InspectionService] = None


def get_inspection_service() -> InspectionService:
    """Get inspection service singleton"""
    global _inspection_service
    if _inspection_service is None:
        _inspection_service = InspectionService()
    return _inspection_service
