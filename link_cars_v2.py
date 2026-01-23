#!/usr/bin/env python3
"""
Привязка автомобилей к клиентам в Rent1C v2

Использует /api/clients/{code}/full из 185.222 для получения связей.
"""
import httpx
import json
import base64
from datetime import datetime

# ===== НАСТРОЙКИ =====

SOURCE_API = "http://185.222.161.252:8080"

RENT1C_ODATA = "https://aclient.1c-hosting.com/1R96614/1R96614_AA61AS_e771ys34or/odata/standard.odata"
RENT1C_USER = "Администратор"
RENT1C_PASS = ""


def get_rent1c_headers():
    credentials = f"{RENT1C_USER}:{RENT1C_PASS}"
    encoded = base64.b64encode(credentials.encode()).decode()
    return {
        "Authorization": f"Basic {encoded}",
        "Content-Type": "application/json; charset=utf-8",
        "Accept": "application/json"
    }


def log(msg):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}")


# ===== ЭТАП 1: Получить клиентов из Rent1C =====

def get_rent1c_clients():
    """Получить клиентов из Rent1C (Code -> Ref_Key)"""
    log("Получение клиентов из Rent1C...")

    clients = {}  # Code -> Ref_Key

    try:
        headers = get_rent1c_headers()

        with httpx.Client(timeout=120, verify=False) as client:
            resp = client.get(
                f"{RENT1C_ODATA}/Catalog_Контрагенты?$select=Ref_Key,Code&$filter=IsFolder eq false&$top=50000&$format=json",
                headers=headers
            )
            if resp.status_code == 200:
                data = resp.json()
                for item in data.get("value", []):
                    code = item.get("Code", "").strip()
                    if code:
                        clients[code] = item.get("Ref_Key")

        log(f"Клиентов в Rent1C: {len(clients)}")

    except Exception as e:
        log(f"Ошибка: {e}")

    return clients


# ===== ЭТАП 2: Получить авто из Rent1C =====

def get_rent1c_cars():
    """Получить авто из Rent1C (VIN -> {ref, owner})"""
    log("Получение авто из Rent1C...")

    cars = {}  # VIN -> {ref, owner}

    try:
        headers = get_rent1c_headers()

        with httpx.Client(timeout=120, verify=False) as client:
            resp = client.get(
                f"{RENT1C_ODATA}/Catalog_Автомобили?$select=Ref_Key,VIN,Поставщик_Key&$top=50000&$format=json",
                headers=headers
            )
            if resp.status_code == 200:
                data = resp.json()
                for item in data.get("value", []):
                    vin = item.get("VIN") or ""
                    if vin:
                        vin = str(vin).strip().upper()
                        if len(vin) >= 10:  # VIN должен быть достаточно длинным
                            cars[vin] = {
                                "ref": item.get("Ref_Key"),
                                "owner": item.get("Поставщик_Key")
                            }

        log(f"Авто с VIN в Rent1C: {len(cars)}")

    except Exception as e:
        log(f"Ошибка: {e}")

    return cars


# ===== ЭТАП 3: Получить связи из 185.222 =====

def get_client_cars_from_source(client_code):
    """Получить авто клиента из 185.222"""
    try:
        with httpx.Client(timeout=30) as client:
            resp = client.get(f"{SOURCE_API}/api/clients/{client_code}/full")
            if resp.status_code == 200:
                data = resp.json()
                cars = data.get("cars", [])
                return [c.get("vin", "").strip().upper() for c in cars if c.get("vin")]
    except:
        pass
    return []


# ===== ЭТАП 4: Обновить владельца в Rent1C =====

def update_car_owner(car_ref, client_ref):
    """Обновить Поставщик_Key у авто"""
    try:
        headers = get_rent1c_headers()

        with httpx.Client(timeout=30, verify=False) as client:
            resp = client.patch(
                f"{RENT1C_ODATA}/Catalog_Автомобили(guid'{car_ref}')?$format=json",
                headers=headers,
                content=json.dumps({"Поставщик_Key": client_ref}, ensure_ascii=False).encode('utf-8')
            )
            return resp.status_code in (200, 204)
    except:
        return False


# ===== ГЛАВНЫЙ ПРОЦЕСС =====

def main():
    print("=" * 60)
    print("  ПРИВЯЗКА АВТО К КЛИЕНТАМ v2")
    print("  185.222 (связи) → Rent1C (обновление)")
    print("=" * 60)
    print()

    # Получаем данные из Rent1C
    rent1c_clients = get_rent1c_clients()
    rent1c_cars = get_rent1c_cars()

    if not rent1c_clients or not rent1c_cars:
        log("Нет данных!")
        return

    # Пустой владелец
    empty_owner = "00000000-0000-0000-0000-000000000000"

    # Находим авто без владельца
    cars_without_owner = {
        vin: data for vin, data in rent1c_cars.items()
        if not data["owner"] or data["owner"] == empty_owner
    }
    log(f"Авто без владельца: {len(cars_without_owner)}")

    if not cars_without_owner:
        log("Все авто уже имеют владельцев!")
        return

    # Обрабатываем клиентов
    updated = 0
    checked = 0
    errors = 0

    client_codes = list(rent1c_clients.keys())
    total = len(client_codes)

    log(f"Проверяем {total} клиентов...")

    for i, code in enumerate(client_codes):
        # Получаем авто клиента из 185.222
        client_vins = get_client_cars_from_source(code)

        for vin in client_vins:
            # Авто есть в Rent1C и без владельца?
            if vin in cars_without_owner:
                car_ref = cars_without_owner[vin]["ref"]
                client_ref = rent1c_clients[code]

                if update_car_owner(car_ref, client_ref):
                    updated += 1
                    # Убираем из списка
                    del cars_without_owner[vin]
                else:
                    errors += 1

        checked += 1

        # Прогресс каждые 100 клиентов
        if checked % 100 == 0:
            log(f"  Прогресс: {checked}/{total} клиентов, обновлено: {updated}, ошибок: {errors}")

        # Если все авто привязаны - выходим
        if not cars_without_owner:
            log("Все авто привязаны!")
            break

    log(f"Завершено: обновлено {updated}, ошибок {errors}")

    print()
    print("=" * 60)
    print("  ГОТОВО")
    print("=" * 60)


if __name__ == "__main__":
    main()
