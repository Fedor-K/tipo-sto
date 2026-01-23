#!/usr/bin/env python3
"""
Привязка авто к владельцам v3

Логика: для каждого авто без владельца находим самый старый заказ → это оригинальный владелец
"""
import httpx
import json
import base64
import sys

SOURCE_API = "http://185.222.161.252:8080"
RENT1C = "https://aclient.1c-hosting.com/1R96614/1R96614_AA61AS_e771ys34or/odata/standard.odata"

def headers():
    creds = "Администратор:".encode('utf-8')
    return {
        "Authorization": f"Basic {base64.b64encode(creds).decode()}",
        "Content-Type": "application/json",
        "Accept": "application/json"
    }

def log(msg):
    print(msg, flush=True)

# 1. Получить авто без владельца из Rent1C
log("1. Получаю авто без владельца из Rent1C...")
with httpx.Client(timeout=60, verify=False) as client:
    r = client.get(
        f"{RENT1C}/Catalog_Автомобили?$filter=Поставщик_Key eq guid'00000000-0000-0000-0000-000000000000'&$select=Ref_Key,Code,Description,VIN&$top=100&$format=json",
        headers=headers()
    )
    cars_data = r.json().get("value", [])

# Фильтруем только с VIN
cars = []
for c in cars_data:
    vin = (c.get("VIN") or "").strip()
    if vin and len(vin) >= 10:
        cars.append({
            "ref": c.get("Ref_Key"),
            "code": c.get("Code"),
            "name": c.get("Description"),
            "vin": vin
        })

log(f"   Найдено авто без владельца с VIN: {len(cars)}")

# 2. Получить ВСЕ заказы из 185.222 (для поиска по VIN)
log("2. Получаю заказы из 185.222...")
orders = []
r = httpx.get(SOURCE_API + "/api/orders?limit=30000", timeout=300)
if r.status_code == 200:
    orders = r.json().get("orders", [])
log(f"   Заказов: {len(orders)}")

# Построить индекс VIN -> заказы (отсортированные по дате)
vin_orders = {}
for o in orders:
    vin = (o.get("car_vin") or "").strip().upper()
    if not vin:
        continue
    if vin not in vin_orders:
        vin_orders[vin] = []
    vin_orders[vin].append({
        "date": o.get("date", ""),
        "client_code": o.get("client_code", ""),
        "client_name": o.get("client_name", "")
    })

# Сортируем заказы по дате (старые первые)
for vin in vin_orders:
    vin_orders[vin].sort(key=lambda x: x["date"])

log(f"   Уникальных VIN в заказах: {len(vin_orders)}")

# 3. Получить клиентов из Rent1C (code -> ref)
log("3. Получаю клиентов из Rent1C...")
with httpx.Client(timeout=60, verify=False) as client:
    r = client.get(
        f"{RENT1C}/Catalog_Контрагенты?$select=Ref_Key,Code&$top=50000&$format=json",
        headers=headers()
    )
    clients_data = r.json().get("value", [])

clients = {}
for c in clients_data:
    code = (c.get("Code") or "").strip()
    if code:
        clients[code] = c.get("Ref_Key")
log(f"   Клиентов: {len(clients)}")

# 4. Привязываем авто к владельцам
log("\n4. Привязка авто к владельцам:")
log("-" * 60)

success = 0
no_orders = 0
no_client = 0
errors = 0

with httpx.Client(timeout=30, verify=False) as client:
    for i, car in enumerate(cars):
        vin = car["vin"].upper()

        # Найти заказы с этим VIN
        car_orders = vin_orders.get(vin, [])

        if not car_orders:
            no_orders += 1
            continue

        # Взять клиента из самого старого заказа
        oldest = car_orders[0]
        client_code = oldest["client_code"]
        client_name = oldest["client_name"]

        # Найти ref клиента в Rent1C
        client_ref = clients.get(client_code)
        if not client_ref:
            no_client += 1
            continue

        # Обновить владельца
        try:
            r = client.patch(
                f"{RENT1C}/Catalog_Автомобили(guid'{car['ref']}')?$format=json",
                headers=headers(),
                content=json.dumps({"Поставщик_Key": client_ref}).encode()
            )
            if r.status_code in (200, 204):
                success += 1
                log(f"  OK: {car['name'][:40]}")
                log(f"      → {client_name} (заказ от {oldest['date']})")
            else:
                errors += 1
        except Exception as e:
            errors += 1

        # Прогресс
        if (i + 1) % 20 == 0:
            log(f"\n  --- Прогресс: {i+1}/{len(cars)} ---\n")

log("-" * 60)
log(f"\nГотово!")
log(f"  Привязано: {success}")
log(f"  Нет заказов: {no_orders}")
log(f"  Клиент не найден: {no_client}")
log(f"  Ошибок: {errors}")
