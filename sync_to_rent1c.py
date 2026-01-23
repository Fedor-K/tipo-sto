#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Sync data from 185.222.161.252 API to Rent1C OData
"""
import requests
import json
import base64

# Source: 185.222.161.252 API Gateway
SOURCE_API = "http://185.222.161.252:8080"

# Target: Rent1C OData
RENT1C_ODATA = "https://aclient.1c-hosting.com/1R96614/1R96614_AA61AS_e771ys34or/odata/standard.odata"
RENT1C_USER = "Администратор"
RENT1C_PASS = ""

def get_auth_header():
    """Create basic auth header with UTF-8 encoding"""
    credentials = f"{RENT1C_USER}:{RENT1C_PASS}"
    b64 = base64.b64encode(credentials.encode('utf-8')).decode('ascii')
    return {"Authorization": f"Basic {b64}"}

def get_source_data(limit=10):
    """Get clients data from source API"""
    print(f"Getting {limit} clients from 185.222...")
    resp = requests.get(f"{SOURCE_API}/api/export/clients?limit={limit}", timeout=60)
    data = resp.json()
    print(f"Got {data.get('count', 0)} clients")
    return data.get('clients', [])

def create_client_in_rent1c(client_data):
    """Create client in Rent1C via OData"""
    client = client_data['client']

    # Check if client exists
    check_url = f"{RENT1C_ODATA}/Catalog_Контрагенты?$filter=Code eq '{client['code']}'&$format=json"
    resp = requests.get(check_url, headers=get_auth_header())

    if resp.status_code == 200:
        data = resp.json()
        if data.get('value') and len(data['value']) > 0:
            print(f"  Client {client['code']} already exists, skipping")
            return data['value'][0].get('Ref_Key')

    # Create new client
    payload = {
        "Code": client['code'],
        "Description": client['name'],
        "ИНН": client.get('inn', ''),
        "Комментарий": client.get('comment', '')
    }

    create_url = f"{RENT1C_ODATA}/Catalog_Контрагенты?$format=json"
    headers = get_auth_header()
    headers["Content-Type"] = "application/json"
    resp = requests.post(create_url, json=payload, headers=headers)

    if resp.status_code in [200, 201]:
        result = resp.json()
        print(f"  Created client {client['code']}: {client['name']}")
        return result.get('Ref_Key')
    else:
        print(f"  Failed to create client {client['code']}: {resp.status_code} - {resp.text[:200]}")
        return None

def create_contract_in_rent1c(contract, client_ref):
    """Create contract in Rent1C"""
    if not client_ref:
        return None

    # Check if contract exists
    check_url = f"{RENT1C_ODATA}/Catalog_ДоговорыВзаиморасчетов?$filter=Code eq '{contract['code']}'&$format=json"
    resp = requests.get(check_url, headers=get_auth_header())

    if resp.status_code == 200:
        data = resp.json()
        if data.get('value') and len(data['value']) > 0:
            print(f"    Contract {contract['code']} already exists")
            return data['value'][0].get('Ref_Key')

    # Create contract
    payload = {
        "Code": contract['code'],
        "Description": contract['name'],
        "Owner_Key": client_ref
    }

    create_url = f"{RENT1C_ODATA}/Catalog_ДоговорыВзаиморасчетов?$format=json"
    headers = get_auth_header()
    headers["Content-Type"] = "application/json"
    resp = requests.post(create_url, json=payload, headers=headers)

    if resp.status_code in [200, 201]:
        print(f"    Created contract {contract['code']}")
        return resp.json().get('Ref_Key')
    else:
        print(f"    Failed to create contract: {resp.status_code}")
        return None

def create_car_in_rent1c(car, client_ref):
    """Create or update car in Rent1C"""
    if not client_ref:
        return None

    # Check if car exists
    check_url = f"{RENT1C_ODATA}/Catalog_Автомобили?$filter=Code eq '{car['code']}'&$format=json"
    resp = requests.get(check_url, headers=get_auth_header())

    if resp.status_code == 200:
        data = resp.json()
        if data.get('value') and len(data['value']) > 0:
            existing_car = data['value'][0]
            car_ref = existing_car.get('Ref_Key')
            existing_owner = existing_car.get('Поставщик_Key', '00000000-0000-0000-0000-000000000000')

            # Update owner if not set
            if existing_owner == '00000000-0000-0000-0000-000000000000':
                update_url = f"{RENT1C_ODATA}/Catalog_Автомобили(guid'{car_ref}')?$format=json"
                headers = get_auth_header()
                headers["Content-Type"] = "application/json"
                update_payload = {"Поставщик_Key": client_ref}
                update_resp = requests.patch(update_url, json=update_payload, headers=headers)
                if update_resp.status_code in [200, 204]:
                    print(f"    Updated car {car['code']} owner")
                else:
                    print(f"    Car {car['code']} exists (owner update failed)")
            else:
                print(f"    Car {car['code']} already exists with owner")
            return car_ref

    # Create car
    payload = {
        "Code": car['code'],
        "Description": car['name'],
        "VIN": car.get('vin', ''),
        "Поставщик_Key": client_ref
    }

    create_url = f"{RENT1C_ODATA}/Catalog_Автомобили?$format=json"
    headers = get_auth_header()
    headers["Content-Type"] = "application/json"
    resp = requests.post(create_url, json=payload, headers=headers)

    if resp.status_code in [200, 201]:
        print(f"    Created car {car['code']}: {car['name'][:40]}")
        return resp.json().get('Ref_Key')
    else:
        print(f"    Failed to create car: {resp.status_code} - {resp.text[:100]}")
        return None

def create_order_in_rent1c(order, client_ref, contract_ref=None):
    """Create order in Rent1C"""
    if not client_ref:
        return None

    # Check if order exists
    check_url = f"{RENT1C_ODATA}/Document_ЗаказНаряд?$filter=Number eq '{order['number']}'&$format=json"
    resp = requests.get(check_url, headers=get_auth_header())

    if resp.status_code == 200:
        data = resp.json()
        if data.get('value') and len(data['value']) > 0:
            print(f"    Order {order['number']} already exists")
            return data['value'][0].get('Ref_Key')

    # Get client's contract if not provided
    if not contract_ref:
        contract_url = f"{RENT1C_ODATA}/Catalog_ДоговорыВзаиморасчетов?$filter=Owner_Key eq guid'{client_ref}'&$top=1&$format=json"
        contract_resp = requests.get(contract_url, headers=get_auth_header())
        if contract_resp.status_code == 200:
            contract_data = contract_resp.json()
            if contract_data.get('value'):
                contract_ref = contract_data['value'][0].get('Ref_Key')

    if not contract_ref:
        print(f"    No contract for order {order['number']}, skipping")
        return None

    # Default GUIDs from Rent1C (same as production)
    DEFAULT_ORG = "39b4c1f1-fa7c-11e5-9841-6cf049a63e1b"  # ООО Сервис-Авто
    DEFAULT_DIVISION = "39b4c1f0-fa7c-11e5-9841-6cf049a63e1b"  # Вся компания
    DEFAULT_PRICE_TYPE = "65ce4042-fa7c-11e5-9841-6cf049a63e1b"  # Основной тип цен продажи
    DEFAULT_WORKSHOP = "65ce404a-fa7c-11e5-9841-6cf049a63e1b"  # Основной цех
    DEFAULT_MASTER = "c94de32f-fa7c-11e5-9841-6cf049a63e1b"  # Дмитренко
    DEFAULT_CURRENCY = "6bd1932d-fa7c-11e5-9841-6cf049a63e1b"  # RUB
    DEFAULT_AUTHOR = "39b4c1f2-fa7c-11e5-9841-6cf049a63e1b"  # Администратор
    DEFAULT_REPAIR_TYPE = "7d9f8931-1a7f-11e6-bee5-20689d8f1e0d"  # Вид ремонта
    DEFAULT_STATUS = "6bd193fc-fa7c-11e5-9841-6cf049a63e1b"  # Заявка
    DEFAULT_NORM_HOUR = "65ce4048-fa7c-11e5-9841-6cf049a63e1b"  # Нормочас

    # Create order with all required fields
    payload = {
        "Number": order['number'],
        "Date": f"{order['date']}T12:00:00",
        "Posted": False,  # Don't post synced orders
        "Контрагент_Key": client_ref,
        "ДоговорВзаиморасчетов_Key": contract_ref,
        "Организация_Key": DEFAULT_ORG,
        "ПодразделениеКомпании_Key": DEFAULT_DIVISION,
        "ТипЦен_Key": DEFAULT_PRICE_TYPE,
        "ТипЦенРабот_Key": DEFAULT_PRICE_TYPE,
        "ВидРемонта_Key": DEFAULT_REPAIR_TYPE,
        "Состояние_Key": DEFAULT_STATUS,
        "Цех_Key": DEFAULT_WORKSHOP,
        "Мастер_Key": DEFAULT_MASTER,
        "ВалютаДокумента_Key": DEFAULT_CURRENCY,
        "Автор_Key": DEFAULT_AUTHOR,
        "Нормочас_Key": DEFAULT_NORM_HOUR,
        "КурсДокумента": 1,
        "КурсВалютыВзаиморасчетов": 1,
        "РегламентированныйУчет": True,
        "СуммаДокумента": order.get('sum', 0),
        "Комментарий": order.get('comment', '')
    }

    create_url = f"{RENT1C_ODATA}/Document_ЗаказНаряд?$format=json"
    headers = get_auth_header()
    headers["Content-Type"] = "application/json"
    resp = requests.post(create_url, json=payload, headers=headers)

    if resp.status_code in [200, 201]:
        print(f"    Created order {order['number']} (sum: {order.get('sum', 0)})")
        return resp.json().get('Ref_Key')
    else:
        print(f"    Failed to create order {order['number']}: {resp.status_code} - {resp.text[:200]}")
        return None

def sync_clients(limit=10):
    """Main sync function"""
    print("=" * 50)
    print("Starting sync from 185.222 to Rent1C")
    print("=" * 50)

    # Get data from source
    clients_data = get_source_data(limit)

    if not clients_data:
        print("No clients to sync")
        return

    success_count = 0

    for i, client_data in enumerate(clients_data, 1):
        client = client_data['client']
        print(f"\n[{i}/{len(clients_data)}] Processing {client['code']}: {client['name']}")

        # Create client
        client_ref = create_client_in_rent1c(client_data)

        if client_ref:
            success_count += 1

            # Create cars
            for car in client_data.get('cars', []):
                create_car_in_rent1c(car, client_ref)

            # Create contracts
            for contract in client_data.get('contracts', []):
                create_contract_in_rent1c(contract, client_ref)

            # Create orders
            for order in client_data.get('orders', []):
                create_order_in_rent1c(order, client_ref)

    print("\n" + "=" * 50)
    print(f"Sync completed: {success_count}/{len(clients_data)} clients")
    print("=" * 50)

if __name__ == "__main__":
    import sys
    limit = int(sys.argv[1]) if len(sys.argv) > 1 else 10
    sync_clients(limit)
