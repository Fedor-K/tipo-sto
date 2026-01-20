# TIPO-STO - CRM для автосервиса

## Текущая архитектура

### Серверы
- **147.45.98.69** - TIPO-STO (FastAPI приложение)
  - SSH: Administrator / kFop??zSpU4QK-
  - IPv6: 2a03:6f00:a::1:6021
  - Python 3.12 установлен
  - TIPO-STO работает на порту 8000
  - UI: http://147.45.98.69:8000/ui
  - Есть VPN подключение к Rent1C (адаптер 1CAAS, IP 172.22.138.80)
  - Файл базы: C:\tipoSTO\1Cv8.dt (328 МБ) - ЗАГРУЖЕН В RENT1C

- **185.222.161.252** - Сервер 1С (старый API Gateway) - НЕ ИСПОЛЬЗУЕТСЯ
  - RDP: порт 6677
  - Логин: 22Linia1 / RhK312Sz1$
  - Claude Code установлен

### Rent1C (облачная 1С) - ОСНОВНОЙ ВАРИАНТ
- Аккаунт: 1R96614U1 / X7gDhIChmV
- Сервер: rca-farm-01.1c-hosting.com
- База: 1R96614_AVTOSERV30_4pgnl9opb4
- Пользователь 1С: Администратор (без пароля)
- Конфигурация: Альфа-Авто (автосервис)
- **OData: ВКЛЮЧЕН поддержкой Rent1C**
- **База .dt загружена на общий диск - ждём загрузки в систему**

## Текущий статус

### Ожидание:
- Rent1C загружает базу из .dt файла
- После загрузки нужно получить URL для OData

### Готово:
- TIPO-STO обновлён для работы с OData (src/main.py)
- VPN к Rent1C работает с 147.45.98.69
- SSH доступ к 147.45.98.69 работает через sshpass

### Команда для деплоя на 147.45.98.69:
```bash
sshpass -p 'kFop??zSpU4QK-' scp -o StrictHostKeyChecking=no src/main.py Administrator@147.45.98.69:"C:\\tipoSTO\\main.py"
sshpass -p 'kFop??zSpU4QK-' ssh -o StrictHostKeyChecking=no Administrator@147.45.98.69 "taskkill /F /IM python.exe"
```

## OData настройки в TIPO-STO

Текущий URL (нужно уточнить после загрузки базы):
```python
ODATA_URL = "http://172.22.0.89/1R96614/1R96614_AVTOSERV30_4pgnl9opb4/odata/standard.odata"
ODATA_USER = "Администратор"
ODATA_PASS = ""
```

## После получения URL от Rent1C

1. Обновить ODATA_URL в src/main.py
2. Задеплоить на 147.45.98.69
3. Перезапустить TIPO-STO
4. Проверить http://147.45.98.69:8000/api/test-odata

## Структура документа ЗаказНаряд в 1С

Обязательные поля для создания:
- Организация (Catalog.Организации)
- Контрагент (Catalog.Контрагенты)

Доступные организации (на сервере 185.222.161.252):
- 00001 - ООО "ПСА"
- ЦБ000001 - ИП Сазонов Н.Н.
- ЦБ000003 - ООО "Инновация"
- ЦБ000002 - ИП Устименко А.В.

## Файлы проекта

- `/Users/khatlamadzieva/tipo-sto/src/main.py` - TIPO-STO приложение (OData версия)
- `C:\tipoSTO\main.py` на 147.45.98.69 - развёрнутое приложение
- `C:\tipoSTO\1Cv8.dt` на 147.45.98.69 - выгрузка базы 1С (загружена в Rent1C)

## Автозапуск TIPO-STO

На 147.45.98.69 через Task Scheduler: задача "TIPO-STO"
