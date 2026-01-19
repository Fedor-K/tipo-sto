# -*- coding: utf-8 -*-
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional
import win32com.client
import pythoncom
import json

app = FastAPI(title="1C API Gateway")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Models for request/response
class OrderCreate(BaseModel):
    client_code: str
    car: str = ""
    comment: str = ""

class OrderUpdate(BaseModel):
    number: str
    status: Optional[str] = None
    comment: Optional[str] = None

def get_1c_connection():
    """Connect to 1C database via COM"""
    pythoncom.CoInitialize()
    try:
        conn = win32com.client.Dispatch('V83.COMConnector')
        return conn.Connect('File="D:\\Base";Usr="Администратор";Pwd="12345678";')
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"1C connection error: {str(e)}")

@app.get("/")
def root():
    return {"status": "ok", "service": "1C API Gateway", "version": "2.0"}

@app.get("/api/clients")
def get_clients():
    """Get list of clients from 1C"""
    try:
        base = get_1c_connection()
        query = base.NewObject("Query")
        query.Text = """
            SELECT TOP 100
                Counterparty.Code AS Code,
                Counterparty.Description AS Name,
                Counterparty.Phone AS Phone
            FROM
                Catalog.Counterparties AS Counterparty
            ORDER BY
                Counterparty.Code DESC
        """
        result = query.Execute().Select()
        clients = []
        while result.Next():
            clients.append({
                "code": str(result.Code),
                "name": str(result.Name),
                "phone": str(result.Phone) if result.Phone else "",
                "car": ""
            })
        return {"clients": clients, "count": len(clients)}
    except Exception as e:
        return {"clients": [], "count": 0, "error": str(e)}

@app.get("/api/orders")
def get_orders():
    """Get list of work orders from 1C"""
    try:
        base = get_1c_connection()
        query = base.NewObject("Query")
        query.Text = """
            SELECT TOP 100
                Doc.Number AS Number,
                Doc.Date AS Date,
                Doc.Counterparty.Description AS Client,
                Doc.Comment AS Comment,
                Doc.DocumentSum AS Sum,
                Doc.Posted AS Posted,
                Doc.Ref AS Ref
            FROM
                Document.WorkOrder AS Doc
            ORDER BY
                Doc.Date DESC
        """
        result = query.Execute().Select()
        orders = []
        while result.Next():
            status = "Проведен" if result.Posted else "Черновик"
            orders.append({
                "number": str(result.Number),
                "date": str(result.Date)[:10] if result.Date else "",
                "client": str(result.Client) if result.Client else "",
                "car": "",
                "status": status,
                "sum": float(result.Sum) if result.Sum else 0,
                "comment": str(result.Comment) if result.Comment else ""
            })
        return {"orders": orders, "count": len(orders)}
    except Exception as e:
        return {"orders": [], "count": 0, "error": str(e)}

@app.post("/api/orders")
def create_order(order: OrderCreate):
    """Create new work order in 1C"""
    try:
        base = get_1c_connection()

        # Find client by code
        query = base.NewObject("Query")
        query.Text = f"""
            SELECT Counterparty.Ref AS Ref
            FROM Catalog.Counterparties AS Counterparty
            WHERE Counterparty.Code = "{order.client_code}"
        """
        result = query.Execute().Select()

        client_ref = None
        if result.Next():
            client_ref = result.Ref

        if not client_ref:
            raise HTTPException(status_code=404, detail=f"Client with code {order.client_code} not found")

        # Create new document
        doc = base.Documents.WorkOrder.CreateDocument()
        doc.Date = base.NewObject("Date")  # Current date
        doc.Counterparty = client_ref
        doc.Comment = order.comment

        # Write document
        doc.Write()

        return {
            "success": True,
            "number": str(doc.Number),
            "message": "Order created successfully"
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error creating order: {str(e)}")

@app.put("/api/orders/{order_number}")
def update_order(order_number: str, order: OrderUpdate):
    """Update existing work order in 1C"""
    try:
        base = get_1c_connection()

        # Find order by number
        query = base.NewObject("Query")
        query.Text = f"""
            SELECT Doc.Ref AS Ref
            FROM Document.WorkOrder AS Doc
            WHERE Doc.Number = "{order_number}"
        """
        result = query.Execute().Select()

        if not result.Next():
            raise HTTPException(status_code=404, detail=f"Order {order_number} not found")

        # Get document object for editing
        doc_ref = result.Ref
        doc = doc_ref.GetObject()

        # Update fields
        if order.comment is not None:
            doc.Comment = order.comment

        # Write changes
        doc.Write()

        # If status change requested to "Posted", try to post
        if order.status == "Проведен":
            try:
                doc.Write(base.DocumentWriteMode.Posting)
            except:
                pass  # Posting may require additional data

        return {
            "success": True,
            "number": order_number,
            "message": "Order updated successfully"
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error updating order: {str(e)}")

@app.get("/api/orders/{order_number}")
def get_order(order_number: str):
    """Get single order details from 1C"""
    try:
        base = get_1c_connection()
        query = base.NewObject("Query")
        query.Text = f"""
            SELECT
                Doc.Number AS Number,
                Doc.Date AS Date,
                Doc.Counterparty.Code AS ClientCode,
                Doc.Counterparty.Description AS Client,
                Doc.Comment AS Comment,
                Doc.DocumentSum AS Sum,
                Doc.Posted AS Posted
            FROM
                Document.WorkOrder AS Doc
            WHERE
                Doc.Number = "{order_number}"
        """
        result = query.Execute().Select()

        if not result.Next():
            raise HTTPException(status_code=404, detail=f"Order {order_number} not found")

        return {
            "number": str(result.Number),
            "date": str(result.Date)[:10] if result.Date else "",
            "client_code": str(result.ClientCode) if result.ClientCode else "",
            "client": str(result.Client) if result.Client else "",
            "comment": str(result.Comment) if result.Comment else "",
            "sum": float(result.Sum) if result.Sum else 0,
            "status": "Проведен" if result.Posted else "Черновик"
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error getting order: {str(e)}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)
