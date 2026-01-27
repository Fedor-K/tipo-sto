# -*- coding: utf-8 -*-
"""
DVI (Digital Vehicle Inspection) API Router
"""
from typing import Optional, List
from fastapi import APIRouter, HTTPException, Query, UploadFile, File, Form
from fastapi.responses import FileResponse

from app.models.inspection import (
    Inspection, InspectionCreate, InspectionItem, InspectionItemCreate,
    InspectionSummary, InspectionItemStatus
)
from app.services.inspection import get_inspection_service

router = APIRouter(prefix="/dvi", tags=["dvi"])


# ==================== Inspections CRUD ====================

@router.get("/categories")
async def get_categories():
    """Get inspection categories template"""
    service = get_inspection_service()
    return service.get_categories()


@router.post("", response_model=Inspection)
async def create_inspection(data: InspectionCreate):
    """
    Create new DVI inspection.

    - **order_ref**: Optional linked order
    - **car_ref**: Car Ref_Key
    - **car_plate**: License plate
    - **client_phone**: Client phone for sending link
    - **mechanic_name**: Mechanic performing inspection
    """
    service = get_inspection_service()
    return service.create_inspection(data)


@router.get("", response_model=List[InspectionSummary])
async def list_inspections(
    order_ref: Optional[str] = Query(None),
    car_ref: Optional[str] = Query(None),
    client_ref: Optional[str] = Query(None),
    date_from: Optional[str] = Query(None),
    date_to: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200),
):
    """List inspections with filters"""
    service = get_inspection_service()
    return service.list_inspections(
        order_ref=order_ref,
        car_ref=car_ref,
        client_ref=client_ref,
        date_from=date_from,
        date_to=date_to,
        limit=limit,
    )


@router.get("/{inspection_id}", response_model=Inspection)
async def get_inspection(inspection_id: str, token: Optional[str] = Query(None)):
    """
    Get inspection by ID.

    - **token**: Public token for client access (optional for internal use)
    """
    service = get_inspection_service()

    if token:
        # Client access with token
        inspection = service.get_inspection_by_token(inspection_id, token)
    else:
        # Internal access
        inspection = service.get_inspection(inspection_id)

    if not inspection:
        raise HTTPException(status_code=404, detail="Inspection not found")

    return inspection


@router.patch("/{inspection_id}", response_model=Inspection)
async def update_inspection(inspection_id: str, updates: dict):
    """Update inspection fields"""
    service = get_inspection_service()
    result = service.update_inspection(inspection_id, updates)
    if not result:
        raise HTTPException(status_code=404, detail="Inspection not found")
    return result


@router.delete("/{inspection_id}")
async def delete_inspection(inspection_id: str):
    """Delete inspection"""
    service = get_inspection_service()
    if not service.delete_inspection(inspection_id):
        raise HTTPException(status_code=404, detail="Inspection not found")
    return {"success": True}


# ==================== Inspection Items ====================

@router.post("/{inspection_id}/items", response_model=InspectionItem)
async def add_inspection_item(inspection_id: str, item: InspectionItemCreate):
    """
    Add item to inspection.

    - **category**: engine, brakes, suspension, tires, fluids, lights, body, interior
    - **name**: Item name
    - **status**: ok, attention, urgent
    - **notes**: Mechanic notes
    - **photo_ids**: List of uploaded photo IDs
    - **recommended_work**: Recommended repair
    - **estimated_cost**: Estimated cost
    """
    service = get_inspection_service()
    result = service.add_item(inspection_id, item)
    if not result:
        raise HTTPException(status_code=404, detail="Inspection not found")
    return result


@router.patch("/{inspection_id}/items/{item_id}", response_model=InspectionItem)
async def update_inspection_item(inspection_id: str, item_id: str, updates: dict):
    """Update inspection item"""
    service = get_inspection_service()
    result = service.update_item(inspection_id, item_id, updates)
    if not result:
        raise HTTPException(status_code=404, detail="Item not found")
    return result


@router.delete("/{inspection_id}/items/{item_id}")
async def delete_inspection_item(inspection_id: str, item_id: str):
    """Delete inspection item"""
    service = get_inspection_service()
    if not service.delete_item(inspection_id, item_id):
        raise HTTPException(status_code=404, detail="Item not found")
    return {"success": True}


# ==================== Photos ====================

@router.post("/photos/upload")
async def upload_photo(file: UploadFile = File(...)):
    """
    Upload photo for inspection.

    Returns photo_id to use when adding items.
    """
    service = get_inspection_service()

    # Validate file type
    if not file.content_type or not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="File must be an image")

    # Read file
    content = await file.read()

    # Limit size (10MB)
    if len(content) > 10 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="File too large (max 10MB)")

    # Save photo
    photo_id = service.save_photo(content, file.filename or "photo.jpg")

    return {
        "photo_id": photo_id,
        "url": f"/api/dvi/photos/{photo_id}",
    }


@router.get("/photos/{photo_id}")
async def get_photo(photo_id: str):
    """Get photo by ID"""
    service = get_inspection_service()
    path = service.get_photo_path(photo_id)

    if not path:
        raise HTTPException(status_code=404, detail="Photo not found")

    # Determine media type
    suffix = path.suffix.lower()
    media_types = {
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".png": "image/png",
        ".gif": "image/gif",
        ".webp": "image/webp",
    }
    media_type = media_types.get(suffix, "image/jpeg")

    return FileResponse(path, media_type=media_type)


@router.post("/{inspection_id}/items/{item_id}/photos")
async def add_photo_to_item(
    inspection_id: str,
    item_id: str,
    file: UploadFile = File(...),
):
    """Upload and add photo directly to item"""
    service = get_inspection_service()

    # Validate
    if not file.content_type or not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="File must be an image")

    content = await file.read()
    if len(content) > 10 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="File too large (max 10MB)")

    # Save photo
    photo_id = service.save_photo(content, file.filename or "photo.jpg")

    # Add to item
    if not service.add_photo_to_item(inspection_id, item_id, photo_id):
        raise HTTPException(status_code=404, detail="Item not found")

    return {
        "photo_id": photo_id,
        "url": f"/api/dvi/photos/{photo_id}",
    }


# ==================== Client Actions ====================

@router.post("/{inspection_id}/send")
async def send_to_client(inspection_id: str):
    """
    Mark inspection as sent to client.

    In production, this would also send SMS/email with link.
    """
    service = get_inspection_service()

    inspection = service.get_inspection(inspection_id)
    if not inspection:
        raise HTTPException(status_code=404, detail="Inspection not found")

    service.mark_sent_to_client(inspection_id)

    return {
        "success": True,
        "public_url": inspection.public_url,
        "message": f"Inspection link ready for client: {inspection.public_url}",
    }


@router.post("/{inspection_id}/items/{item_id}/approve")
async def approve_item(
    inspection_id: str,
    item_id: str,
    token: str = Query(..., description="Public access token"),
    approved: bool = Query(..., description="Approve or decline"),
):
    """
    Client approves/declines inspection item.

    - **token**: Public access token (from URL)
    - **approved**: true to approve, false to decline
    """
    service = get_inspection_service()

    if not service.approve_item(inspection_id, item_id, token, approved):
        raise HTTPException(status_code=404, detail="Item not found or invalid token")

    return {"success": True, "approved": approved}


@router.post("/{inspection_id}/approve-all")
async def approve_all_items(
    inspection_id: str,
    token: str = Query(..., description="Public access token"),
    item_ids: List[str] = Query(..., description="List of item IDs to approve"),
):
    """
    Client approves multiple items at once.
    """
    service = get_inspection_service()

    count = service.approve_all(inspection_id, token, item_ids)
    if count == 0:
        raise HTTPException(status_code=404, detail="No items approved or invalid token")

    return {"success": True, "approved_count": count}


# ==================== Create Order from DVI ====================

from pydantic import BaseModel
from app.services import get_odata_service


class WorkMapping(BaseModel):
    """Map DVI item to 1C work"""
    dvi_item_id: str
    work_ref: str  # Ref_Key from Catalog_Автоработы
    price: float = 0
    quantity: float = 1


class CreateOrderFromDVI(BaseModel):
    """Create order from DVI inspection"""
    client_ref: str  # Ref_Key from Catalog_Контрагенты
    car_ref: Optional[str] = None  # Ref_Key from Catalog_Автомобили (optional)
    works: List[WorkMapping]
    comment: Optional[str] = None


@router.post("/{inspection_id}/create-order")
async def create_order_from_dvi(inspection_id: str, data: CreateOrderFromDVI):
    """
    Create 1C order (ЗаявкаНаРемонт) from DVI inspection.

    - **client_ref**: Client Ref_Key
    - **car_ref**: Optional car Ref_Key (if found by plate)
    - **works**: List of work mappings (DVI item → 1C work)
    """
    dvi_service = get_inspection_service()
    odata = get_odata_service()

    # Get DVI inspection
    inspection = dvi_service.get_inspection(inspection_id)
    if not inspection:
        raise HTTPException(status_code=404, detail="Inspection not found")

    # Build works list for 1C
    works_for_1c = []
    total_sum = 0

    for mapping in data.works:
        works_for_1c.append({
            "work_ref": mapping.work_ref,
            "quantity": mapping.quantity,
            "price": mapping.price,
        })
        total_sum += mapping.price * mapping.quantity

    # Build comment from DVI
    comment_parts = [f"Создано из DVI осмотра {inspection_id}"]
    if inspection.car_plate:
        comment_parts.append(f"Авто: {inspection.car_plate}")
    if inspection.mileage:
        comment_parts.append(f"Пробег: {inspection.mileage} км")
    if data.comment:
        comment_parts.append(data.comment)

    # Create order in 1C
    try:
        order_data = {
            "client_ref": data.client_ref,
            "car_ref": data.car_ref,
            "comment": " | ".join(comment_parts),
            "works": works_for_1c,
        }

        result = await odata.create_repair_request(order_data)

        # Update DVI with order reference
        dvi_service.update_inspection(inspection_id, {
            "order_ref": result.get("Ref_Key"),
            "order_number": result.get("Number"),
        })

        return {
            "success": True,
            "order_ref": result.get("Ref_Key"),
            "order_number": result.get("Number"),
            "total_sum": total_sum,
            "works_count": len(works_for_1c),
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create order: {str(e)}")


@router.get("/{inspection_id}/suggested-works")
async def get_suggested_works(inspection_id: str):
    """
    Get suggested 1C works for DVI items (by searching work names).
    """
    dvi_service = get_inspection_service()
    odata = get_odata_service()

    inspection = dvi_service.get_inspection(inspection_id)
    if not inspection:
        raise HTTPException(status_code=404, detail="Inspection not found")

    suggestions = []

    for item in inspection.items:
        # Skip OK items
        if item.status == "ok":
            continue

        # Search for matching works in 1C
        # Try individual keywords (longer words first, skip common short words)
        # Truncate Russian word endings for better morphology matching
        def truncate_russian(word: str) -> str:
            """Truncate Russian word to root (remove endings)"""
            if len(word) > 6:
                return word[:len(word)-2]  # Remove last 2 chars (endings)
            elif len(word) > 4:
                return word[:len(word)-1]  # Remove last 1 char
            return word

        words = [truncate_russian(w) for w in item.name.split() if len(w) > 4]
        words.sort(key=len, reverse=True)  # Longest words first

        works = []
        for word in words[:3]:  # Try up to 3 keywords
            try:
                found = await odata.get_works_catalog(search=word, limit=5)
                if found:
                    # Add only unique works
                    existing_refs = {w.get("Ref_Key") for w in works}
                    for w in found:
                        if w.get("Ref_Key") not in existing_refs:
                            works.append(w)
                            existing_refs.add(w.get("Ref_Key"))
                    if len(works) >= 5:
                        break
            except Exception:
                continue

        suggestions.append({
            "dvi_item_id": item.id,
            "dvi_item_name": item.name,
            "dvi_item_status": item.status,
            "recommended_work": item.recommended_work,
            "estimated_cost": item.estimated_cost,
            "suggested_works": [
                {
                    "ref": w.get("Ref_Key"),
                    "name": w.get("Description"),
                    "price": w.get("Цена", 0),
                }
                for w in works[:5]
            ],
        })

    return {"inspection_id": inspection_id, "suggestions": suggestions}
