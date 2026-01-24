#!/usr/bin/env python3
"""
Перенос Цеха и Сотрудники из 185.222 в Rent1C
"""
import httpx
import json
import base64

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

# 1. Получить данные из 185.222
log("1. Получаю данные из 185.222...")

workshops = httpx.get(f"{SOURCE_API}/api/catalogs/Цеха", timeout=60).json().get("items", [])
employees = httpx.get(f"{SOURCE_API}/api/catalogs/Сотрудники", timeout=60).json().get("items", [])

log(f"   Цехов: {len(workshops)}")
log(f"   Сотрудников: {len(employees)}")

# 2. Получить существующие данные из Rent1C
log("\n2. Проверяю существующие данные в Rent1C...")

with httpx.Client(timeout=60, verify=False) as client:
    r = client.get(f"{RENT1C}/Catalog_Цеха?$select=Code,Description&$format=json", headers=headers())
    existing_workshops = {w.get("Code", "").strip(): w for w in r.json().get("value", [])}

    r = client.get(f"{RENT1C}/Catalog_Сотрудники?$select=Code,Description&$format=json", headers=headers())
    existing_employees = {e.get("Code", "").strip(): e for e in r.json().get("value", [])}

log(f"   В Rent1C цехов: {len(existing_workshops)}")
log(f"   В Rent1C сотрудников: {len(existing_employees)}")

# 3. Создаём цеха
log("\n3. Создаю цеха...")
workshops_created = 0
workshops_skipped = 0

with httpx.Client(timeout=30, verify=False) as client:
    for w in workshops:
        code = w.get("code", "").strip()
        name = w.get("name", "").strip()

        if code in existing_workshops:
            workshops_skipped += 1
            continue

        data = {
            "Code": code,
            "Description": name
        }

        try:
            r = client.post(
                f"{RENT1C}/Catalog_Цеха?$format=json",
                headers=headers(),
                content=json.dumps(data).encode()
            )
            if r.status_code in (200, 201):
                workshops_created += 1
                log(f"   + {name}")
            else:
                log(f"   ! Ошибка {name}: {r.status_code}")
        except Exception as e:
            log(f"   ! Ошибка {name}: {e}")

log(f"   Создано: {workshops_created}, пропущено: {workshops_skipped}")

# 4. Создаём сотрудников
log("\n4. Создаю сотрудников...")
employees_created = 0
employees_skipped = 0
employees_errors = 0

# Убираем дубликаты по коду
unique_employees = {}
for e in employees:
    code = e.get("code", "").strip()
    if code and code not in unique_employees:
        unique_employees[code] = e

log(f"   Уникальных сотрудников: {len(unique_employees)}")

with httpx.Client(timeout=30, verify=False) as client:
    for code, e in unique_employees.items():
        name = e.get("name", "").strip()

        if code in existing_employees:
            employees_skipped += 1
            continue

        data = {
            "Code": code,
            "Description": name
        }

        try:
            r = client.post(
                f"{RENT1C}/Catalog_Сотрудники?$format=json",
                headers=headers(),
                content=json.dumps(data).encode()
            )
            if r.status_code in (200, 201):
                employees_created += 1
                log(f"   + {name}")
            else:
                employees_errors += 1
                log(f"   ! Ошибка {name}: {r.status_code} - {r.text[:100]}")
        except Exception as e:
            employees_errors += 1
            log(f"   ! Ошибка {name}: {e}")

log(f"\n   Создано: {employees_created}, пропущено: {employees_skipped}, ошибок: {employees_errors}")

log("\n" + "="*50)
log("Готово!")
log(f"  Цехов создано: {workshops_created}")
log(f"  Сотрудников создано: {employees_created}")
