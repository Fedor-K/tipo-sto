# -*- coding: utf-8 -*-
"""
API Gateway v3 - Data Export for TIPO-STO Sync (Simplified for Альфа-Авто)
"""
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from typing import Optional
import win32com.client
import pythoncom

app = FastAPI(title="1C API Gateway", version="3.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

def get_1c_connection():
    """Connect to 1C database via COM"""
    pythoncom.CoInitialize()
    try:
        conn = win32com.client.Dispatch('V83.COMConnector')
        return conn.Connect('File="D:\\Base";Usr="Администратор";Pwd="12345678";')
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"1C connection error: {str(e)}")

def safe_str(val):
    """Safely convert value to string"""
    if val is None:
        return ""
    try:
        return str(val)
    except:
        return ""

def safe_int(val):
    """Safely convert value to int"""
    if val is None:
        return 0
    try:
        return int(val)
    except:
        return 0

def safe_float(val):
    """Safely convert value to float"""
    if val is None:
        return 0.0
    try:
        return float(val)
    except:
        return 0.0

def format_date(dt):
    """Format 1C date to ISO string"""
    if dt:
        try:
            s = str(dt)
            if len(s) >= 10:
                return s[:10]
            return s
        except:
            return ""
    return ""

@app.get("/")
def root():
    return {"status": "ok", "message": "1C API Gateway running", "mode": "live", "version": "3.0"}

# ==================== CLIENTS ====================

@app.get("/api/clients")
def get_clients(limit: int = Query(100, ge=1, le=1000)):
    """Get clients list"""
    try:
        base = get_1c_connection()
        query = base.NewObject("Query")
        query.Text = f"""
            SELECT TOP {limit}
                К.Code AS Code,
                К.Description AS Name,
                К.ИНН AS INN,
                К.Комментарий AS Comment
            FROM
                Catalog.Контрагенты AS К
            WHERE
                К.ЭтоГруппа = FALSE
            ORDER BY
                К.Code DESC
        """
        result = query.Execute().Select()
        clients = []
        while result.Next():
            clients.append({
                "code": safe_str(result.Code),
                "name": safe_str(result.Name),
                "inn": safe_str(result.INN),
                "comment": safe_str(result.Comment)
            })
        return {"clients": clients, "count": len(clients)}
    except Exception as e:
        return {"clients": [], "count": 0, "error": str(e)}

@app.get("/api/clients/{client_code}/full")
def get_client_full(client_code: str):
    """Get client with cars, contracts, and orders"""
    try:
        base = get_1c_connection()

        # 1. Get client
        query = base.NewObject("Query")
        query.Text = """
            SELECT
                К.Ref AS Ref,
                К.Code AS Code,
                К.Description AS Name,
                К.ИНН AS INN,
                К.Комментарий AS Comment
            FROM
                Catalog.Контрагенты AS К
            WHERE
                К.Code = &Code
        """
        query.SetParameter("Code", client_code)
        result = query.Execute().Select()

        if not result.Next():
            raise HTTPException(status_code=404, detail=f"Client {client_code} not found")

        client_ref = result.Ref
        client = {
            "code": safe_str(result.Code),
            "name": safe_str(result.Name),
            "inn": safe_str(result.INN),
            "comment": safe_str(result.Comment)
        }

        # 2. Get client's cars from orders (Альфа-Авто stores car-client relation in orders)
        car_query = base.NewObject("Query")
        car_query.Text = """
            SELECT DISTINCT
                З.Автомобиль.Code AS Code,
                З.Автомобиль.Description AS Name,
                З.Автомобиль.VIN AS VIN
            FROM
                Document.ЗаказНаряд AS З
            WHERE
                З.Контрагент = &ClientRef
                AND З.Автомобиль <> VALUE(Catalog.Автомобили.EmptyRef)
        """
        car_query.SetParameter("ClientRef", client_ref)
        car_result = car_query.Execute().Select()

        cars = []
        seen_codes = set()
        while car_result.Next():
            code = safe_str(car_result.Code)
            if code and code not in seen_codes:
                seen_codes.add(code)
                cars.append({
                    "code": code,
                    "name": safe_str(car_result.Name),
                    "vin": safe_str(car_result.VIN)
                })

        # 3. Get client's contracts
        contract_query = base.NewObject("Query")
        contract_query.Text = """
            SELECT
                Д.Code AS Code,
                Д.Description AS Name
            FROM
                Catalog.ДоговорыВзаиморасчетов AS Д
            WHERE
                Д.Owner = &ClientRef
        """
        contract_query.SetParameter("ClientRef", client_ref)
        contract_result = contract_query.Execute().Select()

        contracts = []
        while contract_result.Next():
            contracts.append({
                "code": safe_str(contract_result.Code),
                "name": safe_str(contract_result.Name)
            })

        # 4. Get client's orders
        order_query = base.NewObject("Query")
        order_query.Text = """
            SELECT TOP 50
                З.Number AS Number,
                З.Date AS Date,
                З.Posted AS Posted,
                З.Автомобиль.Description AS CarName,
                З.СуммаДокумента AS DocSum,
                З.Комментарий AS Comment
            FROM
                Document.ЗаказНаряд AS З
            WHERE
                З.Контрагент = &ClientRef
            ORDER BY
                З.Date DESC
        """
        order_query.SetParameter("ClientRef", client_ref)
        order_result = order_query.Execute().Select()

        orders = []
        while order_result.Next():
            orders.append({
                "number": safe_str(order_result.Number),
                "date": format_date(order_result.Date),
                "posted": bool(order_result.Posted) if order_result.Posted else False,
                "car_name": safe_str(order_result.CarName),
                "sum": safe_float(order_result.DocSum),
                "comment": safe_str(order_result.Comment)
            })

        return {
            "client": client,
            "cars": cars,
            "contracts": contracts,
            "orders": orders
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")

# ==================== CARS ====================

@app.get("/api/cars")
def get_cars(limit: int = Query(100, ge=1, le=5000)):
    """Get all cars"""
    try:
        base = get_1c_connection()
        query = base.NewObject("Query")
        query.Text = f"""
            SELECT TOP {limit}
                А.Code AS Code,
                А.Description AS Name,
                А.VIN AS VIN,
                А.Поставщик.Code AS OwnerCode,
                А.Поставщик.Description AS OwnerName
            FROM
                Catalog.Автомобили AS А
            ORDER BY
                А.Code DESC
        """
        result = query.Execute().Select()
        cars = []
        while result.Next():
            cars.append({
                "code": safe_str(result.Code),
                "name": safe_str(result.Name),
                "vin": safe_str(result.VIN),
                "owner_code": safe_str(result.OwnerCode),
                "owner_name": safe_str(result.OwnerName)
            })
        return {"cars": cars, "count": len(cars)}
    except Exception as e:
        return {"cars": [], "count": 0, "error": str(e)}

# ==================== ORDERS ====================

@app.get("/api/orders")
def get_orders(limit: int = Query(100, ge=1, le=50000)):
    """Get orders"""
    try:
        base = get_1c_connection()
        query = base.NewObject("Query")
        query.Text = f"""
            SELECT TOP {limit}
                З.Number AS Number,
                З.Date AS Date,
                З.Posted AS Posted,
                З.Контрагент.Code AS ClientCode,
                З.Контрагент.Description AS ClientName,
                З.Автомобиль.Description AS CarName,
                З.Автомобиль.VIN AS CarVIN,
                З.СуммаДокумента AS DocSum,
                З.Комментарий AS Comment
            FROM
                Document.ЗаказНаряд AS З
            ORDER BY
                З.Date DESC
        """
        result = query.Execute().Select()
        orders = []
        while result.Next():
            orders.append({
                "number": safe_str(result.Number),
                "date": format_date(result.Date),
                "posted": bool(result.Posted) if result.Posted else False,
                "client_code": safe_str(result.ClientCode),
                "client_name": safe_str(result.ClientName),
                "car_name": safe_str(result.CarName),
                "car_vin": safe_str(result.CarVIN),
                "sum": safe_float(result.DocSum),
                "comment": safe_str(result.Comment)
            })
        return {"orders": orders, "count": len(orders)}
    except Exception as e:
        return {"orders": [], "count": 0, "error": str(e)}

# ==================== CATALOGS ====================

@app.get("/api/catalogs/{name}")
def get_catalog(name: str, limit: int = Query(100, ge=1, le=5000)):
    """Get any catalog by name"""
    try:
        base = get_1c_connection()
        query = base.NewObject("Query")
        query.Text = f"""
            SELECT TOP {limit}
                К.Code AS Code,
                К.Description AS Name
            FROM
                Catalog.{name} AS К
            ORDER BY
                К.Code
        """
        result = query.Execute().Select()
        items = []
        while result.Next():
            items.append({
                "code": safe_str(result.Code),
                "name": safe_str(result.Name)
            })
        return {"catalog": name, "items": items, "count": len(items)}
    except Exception as e:
        return {"catalog": name, "items": [], "count": 0, "error": str(e)}

# ==================== EXPORT ====================

@app.get("/api/export/clients")
def export_clients(limit: int = Query(10, ge=1, le=100)):
    """Export clients with all their data"""
    try:
        base = get_1c_connection()

        # Get client codes
        query = base.NewObject("Query")
        query.Text = f"""
            SELECT TOP {limit}
                К.Code AS Code
            FROM
                Catalog.Контрагенты AS К
            WHERE
                К.ЭтоГруппа = FALSE
            ORDER BY
                К.Code DESC
        """
        result = query.Execute().Select()

        codes = []
        while result.Next():
            codes.append(safe_str(result.Code))

        # Get full data for each client
        clients_data = []
        for code in codes:
            try:
                data = get_client_full(code)
                clients_data.append(data)
            except:
                pass

        return {
            "clients": clients_data,
            "count": len(clients_data)
        }
    except Exception as e:
        return {"clients": [], "count": 0, "error": str(e)}

@app.get("/api/debug/car/{car_code}")
def debug_car(car_code: str):
    """Get all available fields from car record - try multiple owner fields"""
    try:
        base = get_1c_connection()

        # First get the car reference
        query = base.NewObject("Query")
        query.Text = """
            SELECT
                А.Ref AS Ref,
                А.Code AS Code,
                А.Description AS Name,
                А.VIN AS VIN
            FROM
                Catalog.Автомобили AS А
            WHERE
                А.Code = &Code
        """
        query.SetParameter("Code", car_code)
        result = query.Execute().Select()

        if not result.Next():
            return {"error": "car not found"}

        car_ref = result.Ref
        car_data = {
            "code": safe_str(result.Code),
            "name": safe_str(result.Name),
            "vin": safe_str(result.VIN)
        }

        # Try to get attributes directly from catalog item
        try:
            car_obj = base.Catalogs.Автомобили.FindByCode(car_code)
            if car_obj:
                # Try different owner field names
                for field in ['Поставщик', 'Владелец', 'Собственник', 'Клиент', 'Контрагент']:
                    try:
                        owner = getattr(car_obj, field, None)
                        if owner and not owner.IsEmpty():
                            car_data[f'{field}_код'] = safe_str(owner.Code)
                            car_data[f'{field}_имя'] = safe_str(owner.Description)
                        else:
                            car_data[f'{field}'] = "пусто"
                    except:
                        car_data[f'{field}'] = "нет поля"
        except Exception as e:
            car_data['attr_error'] = str(e)

        return car_data
    except Exception as e:
        return {"error": str(e)}

@app.get("/api/debug/order/{order_num}")
def debug_order(order_num: str):
    """Check order fields"""
    try:
        base = get_1c_connection()
        query = base.NewObject("Query")
        query.Text = """
            SELECT TOP 5
                З.Ref AS Ref,
                З.Number AS Number,
                З.Date AS Date,
                З.Контрагент.Description AS Client
            FROM
                Document.ЗаказНаряд AS З
            ORDER BY
                З.Date DESC
        """
        result = query.Execute().Select()
        orders = []
        while result.Next():
            # Try to get the actual document object
            ref = result.Ref
            try:
                doc = base.Documents.ЗаказНаряд.FindByNumber(safe_str(result.Number))
                real_num = safe_str(doc.Number) if doc else "not found"
            except:
                real_num = "error"

            orders.append({
                "number_from_query": safe_str(result.Number),
                "real_number": real_num,
                "date": format_date(result.Date),
                "client": safe_str(result.Client),
                "ref": safe_str(ref)
            })
        return {"orders": orders}
    except Exception as e:
        return {"error": str(e)}

@app.get("/api/debug/car-by-vin/{vin}")
def debug_car_by_vin(vin: str):
    """Find car by VIN and show owner"""
    try:
        base = get_1c_connection()
        query = base.NewObject("Query")
        query.Text = """
            SELECT
                А.Code AS Code,
                А.Description AS Name,
                А.VIN AS VIN,
                А.Поставщик.Code AS ПоставщикКод,
                А.Поставщик.Description AS ПоставщикИмя
            FROM
                Catalog.Автомобили AS А
            WHERE
                А.VIN LIKE &VIN
        """
        query.SetParameter("VIN", f"%{vin}%")
        result = query.Execute().Select()
        cars = []
        while result.Next():
            cars.append({
                "code": safe_str(result.Code),
                "name": safe_str(result.Name),
                "vin": safe_str(result.VIN),
                "owner_code": safe_str(result.ПоставщикКод),
                "owner_name": safe_str(result.ПоставщикИмя)
            })
        return {"cars": cars, "count": len(cars)}
    except Exception as e:
        return {"error": str(e)}

# ==================== METADATA ====================

@app.get("/api/metadata/catalogs")
def get_catalogs_list():
    """Get list of all catalogs in 1C"""
    try:
        base = get_1c_connection()
        catalogs = []
        for i in range(base.Metadata.Catalogs.Count()):
            cat = base.Metadata.Catalogs.Get(i)
            catalogs.append({
                "name": safe_str(cat.Name),
                "synonym": safe_str(cat.Synonym)
            })
        return {"catalogs": catalogs, "count": len(catalogs)}
    except Exception as e:
        return {"error": str(e)}

@app.get("/api/metadata/documents")
def get_documents_list():
    """Get list of all documents in 1C"""
    try:
        base = get_1c_connection()
        docs = []
        for i in range(base.Metadata.Documents.Count()):
            doc = base.Metadata.Documents.Get(i)
            docs.append({
                "name": safe_str(doc.Name),
                "synonym": safe_str(doc.Synonym)
            })
        return {"documents": docs, "count": len(docs)}
    except Exception as e:
        return {"error": str(e)}

@app.get("/api/metadata/catalog/{name}/fields")
def get_catalog_fields(name: str):
    """Get fields of a catalog"""
    try:
        base = get_1c_connection()
        cat = base.Metadata.Catalogs.Find(name)
        if not cat:
            return {"error": f"Catalog {name} not found"}

        fields = []
        for i in range(cat.Attributes.Count()):
            attr = cat.Attributes.Get(i)
            fields.append({
                "name": safe_str(attr.Name),
                "synonym": safe_str(attr.Synonym)
            })
        return {"catalog": name, "fields": fields, "count": len(fields)}
    except Exception as e:
        return {"error": str(e)}

@app.get("/api/metadata/document/{name}/fields")
def get_document_fields(name: str):
    """Get fields of a document"""
    try:
        base = get_1c_connection()
        doc = base.Metadata.Documents.Find(name)
        if not doc:
            return {"error": f"Document {name} not found"}

        fields = []
        for i in range(doc.Attributes.Count()):
            attr = doc.Attributes.Get(i)
            fields.append({
                "name": safe_str(attr.Name),
                "synonym": safe_str(attr.Synonym)
            })
        return {"document": name, "fields": fields, "count": len(fields)}
    except Exception as e:
        return {"error": str(e)}

@app.get("/api/metadata/document/{name}/tabular")
def get_document_tabular(name: str):
    """Get tabular parts of a document"""
    try:
        base = get_1c_connection()
        doc = base.Metadata.Documents.Find(name)
        if not doc:
            return {"error": f"Document {name} not found"}

        tabular = []
        for i in range(doc.TabularSections.Count()):
            ts = doc.TabularSections.Get(i)
            attrs = []
            for j in range(ts.Attributes.Count()):
                attr = ts.Attributes.Get(j)
                attrs.append({
                    "name": safe_str(attr.Name),
                    "synonym": safe_str(attr.Synonym)
                })
            tabular.append({
                "name": safe_str(ts.Name),
                "synonym": safe_str(ts.Synonym),
                "attributes": attrs
            })
        return {"document": name, "tabular_parts": tabular, "count": len(tabular)}
    except Exception as e:
        return {"error": str(e)}

@app.get("/api/stats/catalog/{name}")
def get_catalog_stats(name: str):
    """Get record count for a catalog"""
    try:
        base = get_1c_connection()
        query = base.NewObject("Query")
        query.Text = f"SELECT COUNT(*) AS Cnt FROM Catalog.{name}"
        result = query.Execute().Select()
        if result.Next():
            return {"catalog": name, "count": safe_int(result.Cnt)}
        return {"catalog": name, "count": 0}
    except Exception as e:
        return {"catalog": name, "count": 0, "error": str(e)}

@app.get("/api/stats/document/{name}")
def get_document_stats(name: str):
    """Get record count for a document"""
    try:
        base = get_1c_connection()
        query = base.NewObject("Query")
        query.Text = f"SELECT COUNT(*) AS Cnt FROM Document.{name}"
        result = query.Execute().Select()
        if result.Next():
            return {"document": name, "count": safe_int(result.Cnt)}
        return {"document": name, "count": 0}
    except Exception as e:
        return {"document": name, "count": 0, "error": str(e)}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)
