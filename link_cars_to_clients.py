#!/usr/bin/env python3
"""
Скрипт привязки автомобилей к клиентам в Rent1C

Использует данные заказов из 185.222 для определения владельцев авто.
"""
import httpx
import json
import base64
import re
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


def extract_vin(car_name):
    """Извлечь VIN из названия автомобиля"""
    # VIN обычно 17 символов, в конце названия после "VIN "
    match = re.search(r'VIN\s*([A-HJ-NPR-Z0-9]{17})', car_name, re.IGNORECASE)
    if match:
        return match.group(1).upper()
    return None


# ===== ЭТАП 1: Получить связи авто-клиент из заказов =====

def get_car_client_links():
    """Получить уникальные пары авто(VIN) -> клиент(код) из заказов"""
    log("Получение заказов из 185.222...")

    links = {}  # VIN -> client_code

    try:
        with httpx.Client(timeout=120) as client:
            # Получаем все заказы
            resp = client.get(f"{SOURCE_API}/api/orders?limit=5000")
            if resp.status_code == 200:
                data = resp.json()
                orders = data.get("orders", [])
                log(f"Найдено заказов: {len(orders)}")

                for order in orders:
                    car_name = order.get("car_name", "")
                    client_code = order.get("client_code", "").strip()

                    if not car_name or not client_code:
                        continue

                    vin = extract_vin(car_name)
                    if vin:
                        # Сохраняем последнего клиента для VIN
                        links[vin] = client_code

                log(f"Уникальных связей VIN->клиент: {len(links)}")

    except Exception as e:
        log(f"Ошибка: {e}")

    return links


# ===== ЭТАП 2: Получить справочники из Rent1C =====

def get_rent1c_cars():
    """Получить все автомобили из Rent1C (VIN -> Ref_Key)"""
    log("Получение автомобилей из Rent1C...")

    cars = {}  # VIN -> {ref, current_owner}

    try:
        headers = get_rent1c_headers()

        with httpx.Client(timeout=120, verify=False) as client:
            resp = client.get(
                f"{RENT1C_ODATA}/Catalog_Автомобили?$select=Ref_Key,VIN,Поставщик_Key&$top=10000&$format=json",
                headers=headers
            )
            if resp.status_code == 200:
                data = resp.json()
                for item in data.get("value", []):
                    vin = item.get("VIN", "").strip().upper()
                    if vin and len(vin) == 17:
                        cars[vin] = {
                            "ref": item.get("Ref_Key"),
                            "owner": item.get("Поставщик_Key")
                        }

                log(f"Автомобилей с VIN: {len(cars)}")

    except Exception as e:
        log(f"Ошибка: {e}")

    return cars


def get_rent1c_clients():
    """Получить всех клиентов из Rent1C (Code -> Ref_Key)"""
    log("Получение клиентов из Rent1C...")

    clients = {}  # Code -> Ref_Key

    try:
        headers = get_rent1c_headers()

        with httpx.Client(timeout=120, verify=False) as client:
            resp = client.get(
                f"{RENT1C_ODATA}/Catalog_Контрагенты?$select=Ref_Key,Code&$top=50000&$format=json",
                headers=headers
            )
            if resp.status_code == 200:
                data = resp.json()
                for item in data.get("value", []):
                    code = item.get("Code", "").strip()
                    if code:
                        clients[code] = item.get("Ref_Key")

                log(f"Клиентов: {len(clients)}")

    except Exception as e:
        log(f"Ошибка: {e}")

    return clients


# ===== ЭТАП 3: Обновить владельцев авто =====

def update_car_owner(car_ref, client_ref):
    """Обновить поле Поставщик_Key у автомобиля"""

    odata_data = {
        "Поставщик_Key": client_ref
    }

    try:
        headers = get_rent1c_headers()

        with httpx.Client(timeout=30, verify=False) as client:
            resp = client.patch(
                f"{RENT1C_ODATA}/Catalog_Автомобили(guid'{car_ref}')?$format=json",
                headers=headers,
                content=json.dumps(odata_data, ensure_ascii=False).encode('utf-8')
            )

            if resp.status_code in (200, 204):
                return {"success": True}
            else:
                return {"success": False, "error": resp.text[:200]}

    except Exception as e:
        return {"success": False, "error": str(e)}


def link_cars_to_clients():
    """Основной процесс привязки"""

    # Получаем данные
    links = get_car_client_links()
    if not links:
        log("Нет данных о связях!")
        return

    cars = get_rent1c_cars()
    clients = get_rent1c_clients()

    # Находим совпадения
    empty_owner = "00000000-0000-0000-0000-000000000000"
    updates_needed = []

    for vin, client_code in links.items():
        # Авто есть в Rent1C?
        if vin not in cars:
            continue

        car = cars[vin]

        # У авто уже есть владелец?
        if car["owner"] and car["owner"] != empty_owner:
            continue

        # Клиент есть в Rent1C?
        if client_code not in clients:
            continue

        updates_needed.append({
            "vin": vin,
            "car_ref": car["ref"],
            "client_code": client_code,
            "client_ref": clients[client_code]
        })

    log(f"Нужно обновить: {len(updates_needed)} автомобилей")

    if not updates_needed:
        log("Нечего обновлять!")
        return

    # Обновляем
    success = 0
    failed = 0

    for i, item in enumerate(updates_needed):
        result = update_car_owner(item["car_ref"], item["client_ref"])

        if result["success"]:
            success += 1
        else:
            failed += 1
            if failed <= 5:
                log(f"  Ошибка [{item['vin']}]: {result['error'][:100]}")

        if (i + 1) % 10 == 0:
            log(f"  Прогресс: {i+1}/{len(updates_needed)} (успешно: {success}, ошибок: {failed})")

    log(f"Завершено: успешно {success}, ошибок {failed}")


def main():
    print("=" * 60)
    print("  ПРИВЯЗКА АВТОМОБИЛЕЙ К КЛИЕНТАМ")
    print("  185.222 заказы → Rent1C автомобили")
    print("=" * 60)
    print()

    link_cars_to_clients()

    print()
    print("=" * 60)
    print("  ГОТОВО")
    print("=" * 60)


if __name__ == "__main__":
    main()
