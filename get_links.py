#!/usr/bin/env python3
import httpx
import sys

SOURCE = "http://185.222.161.252:8080"

print("Получаю клиентов...", flush=True)
r = httpx.get(f"{SOURCE}/api/clients?limit=100", timeout=30)
clients = r.json().get("clients", [])

links = []
for i, cl in enumerate(clients):
    code = cl.get("code", "")
    name = cl.get("name", "")
    try:
        r = httpx.get(f"{SOURCE}/api/clients/{code}/full", timeout=5)
        for car in r.json().get("cars", []):
            vin = (car.get("vin") or "").strip()
            car_name = car.get("name", "")
            if vin and len(vin) >= 10:
                links.append({"client": name, "code": code, "car": car_name, "vin": vin})
    except:
        pass
    if (i+1) % 25 == 0:
        print(f"  {i+1}/100", flush=True)

print(f"\nВсего связей: {len(links)}\n", flush=True)
for i, l in enumerate(links, 1):
    client = l["client"][:28]
    code = l["code"]
    car = l["car"][:42]
    print(f"{i:2}. {code:12} {client:28} | {car}", flush=True)
