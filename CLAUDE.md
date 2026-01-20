# TIPO-STO - CRM для автосервиса

## Текущая архитектура

### Серверы
- **147.45.98.69** - TIPO-STO (FastAPI приложение)
  - SSH: Administrator / kFop??zSpU4QK-
  - Python 3.12 установлен
  - TIPO-STO работает на порту 8000
  - UI: http://147.45.98.69:8000/ui
  - Есть VPN подключение к Rent1C (адаптер 1CAAS, IP 172.22.138.80)

- **185.222.161.252** - Сервер 1С (API Gateway)
  - RDP: порт 6677 (mstsc /v:185.222.161.252:6677)
  - SSH: порт 22 (ЗАБЛОКИРОВАН хостером для внешнего доступа!)
  - Логин: 22Linia1
  - Пароль: RhK312Sz1$
  - Python 32-bit: C:\Python312-32\python.exe
  - 1С база: D:\Base (Администратор / 12345678)
  - API Gateway: C:\temp\api_gateway.py (порт 8080)

### Rent1C (облачная 1С) - резервный вариант
- Аккаунт: 1R96614U1 / X7gDhIChmV
- Сервер: rca-farm-01.1c-hosting.com
- База: 1R96614_AVTOSERV30_4pgnl9opb4
- Пользователь 1С: Администратор (без пароля)
- Конфигурация: Альфа-Авто (автосервис)
- OData не включен - нужно запросить у поддержки

## Текущий статус

### Работает:
- GET /api/orders - список заказ-нарядов из 1С
- GET /api/clients - список контрагентов из 1С
- UI на http://147.45.98.69:8000/ui

### Обновлено (OData):
- TIPO-STO теперь использует OData вместо API Gateway
- OData URL: http://172.22.0.89/1R96614/1R96614_AVTOSERV30_4pgnl9opb4/odata/standard.odata
- Пользователь: Администратор (без пароля)
- Нужно задеплоить обновленный main.py на 147.45.98.69

## Структура документа ЗаказНаряд в 1С

Обязательные поля для создания:
- Организация (Catalog.Организации)
- Контрагент (Catalog.Контрагенты)

Доступные организации:
- 00001 - ООО "ПСА"
- ЦБ000001 - ИП Сазонов Н.Н.
- ЦБ000003 - ООО "Инновация"
- ЦБ000002 - ИП Устименко А.В.

Все реквизиты документа:
Автор, Менеджер, Организация, ПодразделениеКомпании, Проект, Комментарий,
ДокументОснование, ХозОперация, ВалютаДокумента, ТипЦен, ВидРемонта, Состояние,
Заказчик, Автомобиль, Пробег, Контрагент, ДоговорВзаиморасчетов, ВидОплаты,
Карточка, Цех, Мастер, Диспетчер, СкидкаНаценка, СуммаДокумента, ДатаНачала,
ДатаОкончания, ДатаЗакрытия, ПлановаяДатаВыдачи, Рекомендации, Гарантии и др.

## Команды для управления

### Запуск API Gateway на 185.222.161.252
```powershell
# Через RDP подключиться к 185.222.161.252:6677
# Логин: 22Linia1, Пароль: RhK312Sz1$

# Запустить API Gateway
C:\Python312-32\python.exe C:\temp\api_gateway.py

# Остановить
Ctrl+C или taskkill /F /IM python.exe (от админа)
```

### Запуск TIPO-STO на 147.45.98.69
```bash
ssh Administrator@147.45.98.69
cd C:\tipoSTO
"C:\Program Files\Python312\python.exe" -m uvicorn main:app --host 0.0.0.0 --port 8000
```

## Текущий код API Gateway (C:\temp\api_gateway.py)

```python
# -*- coding: utf-8 -*-
from fastapi import FastAPI
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware
import win32com.client
import pythoncom

app = FastAPI(title="1C API Gateway")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

class OrderCreate(BaseModel):
    client_code: str
    comment: str = ''

def get_1c_connection():
    pythoncom.CoInitialize()
    conn = win32com.client.Dispatch('V83.COMConnector')
    return conn.Connect('File="D:\\Base";Usr="Администратор";Pwd="12345678";')

@app.get("/")
def root():
    return {"status": "ok", "message": "1C API Gateway running"}

@app.get("/api/clients")
def get_clients():
    try:
        db = get_1c_connection()
        query = db.NewObject('Query')
        query.Text = 'SELECT TOP 100 Code AS code, Description AS name FROM Catalog.Контрагенты WHERE NOT DeletionMark ORDER BY Code DESC'
        result = query.Execute()
        sel = result.Choose()
        clients = []
        while sel.Next():
            clients.append({"code": str(sel.code), "name": str(sel.name)})
        return {"clients": clients, "count": len(clients)}
    except Exception as e:
        return {"error": str(e), "clients": [], "count": 0}

@app.get("/api/orders")
def get_orders():
    try:
        db = get_1c_connection()
        query = db.NewObject('Query')
        query.Text = 'SELECT TOP 100 Number, Date, Контрагент.Description AS client, СуммаДокумента AS sum FROM Document.ЗаказНаряд WHERE NOT DeletionMark ORDER BY Date DESC'
        result = query.Execute()
        sel = result.Choose()
        orders = []
        while sel.Next():
            orders.append({"number": str(sel.Number), "date": str(sel.Date)[:10], "client": str(sel.client) if sel.client else "", "status": "В работе", "sum": float(sel.sum) if sel.sum else 0})
        return {"orders": orders, "count": len(orders)}
    except Exception as e:
        return {"error": str(e), "orders": [], "count": 0}

@app.post('/api/orders')
def create_order(order: OrderCreate):
    try:
        db = get_1c_connection()
        # Получить организацию
        q = db.NewObject('Query')
        q.Text = 'SELECT TOP 1 Ref FROM Catalog.Организации'
        r = q.Execute().Choose()
        r.Next()
        org_ref = r.Ref
        # Создать документ
        doc = db.Documents.ЗаказНаряд.CreateDocument()
        doc.Организация = org_ref
        doc.Write()
        return {'success': True, 'number': str(doc.Number)}
    except Exception as e:
        return {'error': str(e)}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)
```

## Следующие шаги

1. Обновить POST endpoint - добавить Организацию
2. Протестировать создание заказ-наряда
3. Добавить контрагента в POST запрос
4. Добавить PUT endpoint для редактирования

## Автозапуск

### TIPO-STO (147.45.98.69)
Настроен через Task Scheduler: задача "TIPO-STO"

### API Gateway (185.222.161.252)
Нужно настроить автозапуск через Task Scheduler
