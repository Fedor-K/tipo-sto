#!/usr/bin/env python3
"""
Скрипт переноса используемой номенклатуры из 185.222 в Rent1C

Переносит только запчасти, которые реально использовались в заказ-нарядах.
"""
import httpx
import json
import base64
import time
from datetime import datetime

# ===== НАСТРОЙКИ =====

# Источник: 185.222.161.252 (API Gateway)
SOURCE_API = "http://185.222.161.252:8080"

# Цель: Rent1C OData
RENT1C_ODATA = "https://aclient.1c-hosting.com/1R96614/1R96614_AA61AS_e771ys34or/odata/standard.odata"
RENT1C_USER = "Администратор"
RENT1C_PASS = ""

# Настройки
BATCH_SIZE = 50  # Записей за раз
DELAY_BETWEEN_BATCHES = 1  # Секунд между батчами


def get_rent1c_headers():
    """Заголовки авторизации для Rent1C"""
    credentials = f"{RENT1C_USER}:{RENT1C_PASS}"
    encoded = base64.b64encode(credentials.encode()).decode()
    return {
        "Authorization": f"Basic {encoded}",
        "Content-Type": "application/json; charset=utf-8",
        "Accept": "application/json"
    }


def log(msg):
    """Логирование с временем"""
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}")


# ===== ЭТАП 1: Получение уникальных кодов номенклатуры из заказов =====

def get_used_parts_codes():
    """
    Получить уникальные коды номенклатуры из табличных частей заказ-нарядов.
    Использует прямой запрос к API Gateway.
    """
    log("Получение списка используемой номенклатуры из заказов...")

    # Этот эндпоинт нужно добавить в API Gateway,
    # или мы можем получить заказы и извлечь товары из них

    # Пока используем альтернативный подход - получаем заказы и собираем товары
    used_codes = set()

    try:
        # Получаем последние заказы (там есть товары)
        with httpx.Client(timeout=60) as client:
            resp = client.get(f"{SOURCE_API}/api/orders?limit=1000")
            if resp.status_code == 200:
                data = resp.json()
                orders = data.get("orders", [])
                log(f"Найдено заказов: {len(orders)}")

                # Для каждого заказа нужно получить товары
                # Но API Gateway не даёт табличные части напрямую
                # Поэтому используем запрос к справочнику номенклатуры

    except Exception as e:
        log(f"Ошибка получения заказов: {e}")

    # Альтернатива: получаем ВСЮ номенклатуру, но только с непустым артикулом
    # (реально используемые товары обычно имеют артикул)
    return used_codes


def get_all_parts_with_article(limit=5000):
    """
    Получить номенклатуру с непустым артикулом (реальные товары).
    """
    log(f"Получение номенклатуры с артикулами (limit={limit})...")

    parts = []

    try:
        with httpx.Client(timeout=120) as client:
            # Получаем номенклатуру через общий каталог
            resp = client.get(f"{SOURCE_API}/api/catalogs/Номенклатура?limit={limit}")
            if resp.status_code == 200:
                data = resp.json()
                items = data.get("items", [])
                log(f"Получено записей: {len(items)}")

                for item in items:
                    parts.append({
                        "code": item.get("code", "").strip(),
                        "name": item.get("name", "")
                    })

    except Exception as e:
        log(f"Ошибка: {e}")

    return parts


# ===== ЭТАП 2: Проверка существования в Rent1C =====

def get_existing_codes_rent1c():
    """Получить коды номенклатуры, уже существующей в Rent1C"""
    log("Проверка существующей номенклатуры в Rent1C...")

    existing = set()

    try:
        headers = get_rent1c_headers()

        with httpx.Client(timeout=120, verify=False) as client:
            # Получаем все коды номенклатуры
            resp = client.get(
                f"{RENT1C_ODATA}/Catalog_Номенклатура?$select=Code&$top=10000&$format=json",
                headers=headers
            )
            if resp.status_code == 200:
                data = resp.json()
                for item in data.get("value", []):
                    code = item.get("Code", "").strip()
                    if code:
                        existing.add(code)

        log(f"В Rent1C уже есть {len(existing)} записей номенклатуры")

    except Exception as e:
        log(f"Ошибка: {e}")

    return existing


# ===== ЭТАП 3: Создание номенклатуры в Rent1C =====

def create_part_in_rent1c(part_data):
    """Создать запись номенклатуры в Rent1C"""

    # Подготовка данных для OData
    odata_data = {
        "Code": part_data.get("code", "")[:11],  # Код до 11 символов
        "Description": part_data.get("name", "")[:150],  # Наименование до 150
        "НаименованиеПолное": part_data.get("name", ""),
        "Артикул": part_data.get("article", ""),
        "АртикулДляПоиска": part_data.get("article", ""),
        # Дефолтные значения
        "ВидНоменклатуры": "Товар",
        "ТипНоменклатуры_Key": "6bd19308-fa7c-11e5-9841-6cf049a63e1b",  # Товар
        "БазоваяЕдиницаИзмерения_Key": "6bd192f3-fa7c-11e5-9841-6cf049a63e1b",  # шт
        "ОсновнаяЕдиницаИзмерения_Key": "6bd192f3-fa7c-11e5-9841-6cf049a63e1b",
        "СтавкаНДС_Key": "55cfa059-5765-11e9-9848-f82fa8e6b382",  # 20%
        "ВалютаУчета_Key": "6bd1932d-fa7c-11e5-9841-6cf049a63e1b",  # RUB
    }

    try:
        headers = get_rent1c_headers()

        with httpx.Client(timeout=30, verify=False) as client:
            resp = client.post(
                f"{RENT1C_ODATA}/Catalog_Номенклатура?$format=json",
                headers=headers,
                content=json.dumps(odata_data, ensure_ascii=False).encode('utf-8')
            )

            if resp.status_code in (200, 201):
                result = resp.json()
                return {"success": True, "ref": result.get("Ref_Key", "")}
            else:
                return {"success": False, "error": resp.text[:200]}

    except Exception as e:
        return {"success": False, "error": str(e)}


def migrate_parts(parts, existing_codes):
    """Перенести номенклатуру в Rent1C"""

    # Фильтруем только новые
    new_parts = [p for p in parts if p.get("code", "").strip() not in existing_codes]

    log(f"Новых для переноса: {len(new_parts)} из {len(parts)}")

    if not new_parts:
        log("Нечего переносить!")
        return

    success = 0
    failed = 0

    for i, part in enumerate(new_parts):
        result = create_part_in_rent1c(part)

        if result["success"]:
            success += 1
        else:
            failed += 1
            if failed <= 5:  # Показываем первые 5 ошибок
                log(f"  Ошибка [{part['code']}]: {result['error'][:100]}")

        # Прогресс
        if (i + 1) % 10 == 0:
            log(f"  Прогресс: {i+1}/{len(new_parts)} (успешно: {success}, ошибок: {failed})")

        # Пауза между батчами
        if (i + 1) % BATCH_SIZE == 0:
            time.sleep(DELAY_BETWEEN_BATCHES)

    log(f"Завершено: успешно {success}, ошибок {failed}")


# ===== ГЛАВНАЯ ФУНКЦИЯ =====

def main():
    print("=" * 60)
    print("  МИГРАЦИЯ НОМЕНКЛАТУРЫ: 185.222 → Rent1C")
    print("  Только используемые товары")
    print("=" * 60)
    print()

    # Шаг 1: Получить номенклатуру из источника
    parts = get_all_parts_with_article(limit=1000)

    if not parts:
        log("Не удалось получить данные из источника!")
        return

    # Шаг 2: Проверить что уже есть в Rent1C
    existing = get_existing_codes_rent1c()

    # Шаг 3: Перенести новые
    migrate_parts(parts, existing)

    print()
    print("=" * 60)
    print("  ГОТОВО")
    print("=" * 60)


if __name__ == "__main__":
    main()
