from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="TIPO-STO API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mock данные - клиенты СТО
MOCK_CLIENTS = [
    {"code": "000001", "name": "Иванов Петр Сергеевич", "phone": "+7 999 123-45-67", "car": "Toyota Camry 2019"},
    {"code": "000002", "name": "ООО АвтоТранс", "phone": "+7 495 555-12-34", "car": "ГАЗель Next 2021"},
    {"code": "000003", "name": "Сидорова Анна Михайловна", "phone": "+7 916 777-88-99", "car": "Kia Rio 2020"},
    {"code": "000004", "name": "ИП Козлов", "phone": "+7 903 222-33-44", "car": "Ford Transit 2018"},
    {"code": "000005", "name": "Петров Алексей Иванович", "phone": "+7 925 111-22-33", "car": "Hyundai Solaris 2022"},
]

# Mock данные - заказ-наряды
MOCK_ORDERS = [
    {"number": "ЗН-000001", "client": "Иванов Петр Сергеевич", "car": "Toyota Camry", "status": "В работе", "sum": 15500},
    {"number": "ЗН-000002", "client": "ООО АвтоТранс", "car": "ГАЗель Next", "status": "Готов", "sum": 28000},
    {"number": "ЗН-000003", "client": "Сидорова Анна Михайловна", "car": "Kia Rio", "status": "Новый", "sum": 5200},
    {"number": "ЗН-000004", "client": "ИП Козлов", "car": "Ford Transit", "status": "Выдан", "sum": 42300},
]

@app.get("/")
async def root():
    return {"status": "ok", "message": "TIPO-STO API is running", "mode": "mock"}

@app.get("/api/clients")
async def get_clients():
    return {"clients": MOCK_CLIENTS, "count": len(MOCK_CLIENTS)}

@app.get("/api/orders")
async def get_orders():
    return {"orders": MOCK_ORDERS, "count": len(MOCK_ORDERS)}

@app.get("/ui", response_class=HTMLResponse)
async def ui():
    return """
<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>TIPO-STO</title>
    <style>
        * { box-sizing: border-box; margin: 0; padding: 0; }
        body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #f5f5f5; }
        .header { background: #2196F3; color: white; padding: 20px; text-align: center; }
        .header h1 { font-size: 24px; }
        .container { max-width: 1200px; margin: 20px auto; padding: 0 20px; }
        .tabs { display: flex; gap: 10px; margin-bottom: 20px; }
        .tab { padding: 12px 24px; background: white; border: none; cursor: pointer; border-radius: 8px; font-size: 16px; }
        .tab.active { background: #2196F3; color: white; }
        .card { background: white; border-radius: 12px; padding: 20px; margin-bottom: 15px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }
        .card-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px; }
        .card-title { font-size: 18px; font-weight: 600; color: #333; }
        .card-subtitle { color: #666; font-size: 14px; }
        .badge { padding: 4px 12px; border-radius: 20px; font-size: 12px; font-weight: 500; }
        .badge-new { background: #E3F2FD; color: #1976D2; }
        .badge-work { background: #FFF3E0; color: #F57C00; }
        .badge-ready { background: #E8F5E9; color: #388E3C; }
        .badge-done { background: #EEEEEE; color: #616161; }
        .info-row { display: flex; gap: 20px; margin-top: 10px; color: #666; font-size: 14px; }
        .sum { font-size: 18px; font-weight: 600; color: #2196F3; }
        .section-title { font-size: 20px; margin-bottom: 15px; color: #333; }
        .empty { text-align: center; padding: 40px; color: #999; }
        .stats { display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 15px; margin-bottom: 20px; }
        .stat-card { background: white; padding: 20px; border-radius: 12px; text-align: center; }
        .stat-value { font-size: 32px; font-weight: 700; color: #2196F3; }
        .stat-label { color: #666; margin-top: 5px; }
    </style>
</head>
<body>
    <div class="header">
        <h1>TIPO-STO</h1>
        <p>CRM для автосервиса</p>
    </div>

    <div class="container">
        <div class="stats" id="stats"></div>

        <div class="tabs">
            <button class="tab active" onclick="showTab('orders')">Заказ-наряды</button>
            <button class="tab" onclick="showTab('clients')">Клиенты</button>
        </div>

        <div id="orders"></div>
        <div id="clients" style="display:none"></div>
    </div>

    <script>
        function getBadgeClass(status) {
            const map = {'Новый': 'badge-new', 'В работе': 'badge-work', 'Готов': 'badge-ready', 'Выдан': 'badge-done'};
            return map[status] || 'badge-new';
        }

        function showTab(tab) {
            document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
            event.target.classList.add('active');
            document.getElementById('orders').style.display = tab === 'orders' ? 'block' : 'none';
            document.getElementById('clients').style.display = tab === 'clients' ? 'block' : 'none';
        }

        async function loadData() {
            const [clientsRes, ordersRes] = await Promise.all([
                fetch('/api/clients').then(r => r.json()),
                fetch('/api/orders').then(r => r.json())
            ]);

            // Stats
            const inWork = ordersRes.orders.filter(o => o.status === 'В работе').length;
            const ready = ordersRes.orders.filter(o => o.status === 'Готов').length;
            document.getElementById('stats').innerHTML = `
                <div class="stat-card"><div class="stat-value">${ordersRes.count}</div><div class="stat-label">Заказ-нарядов</div></div>
                <div class="stat-card"><div class="stat-value">${inWork}</div><div class="stat-label">В работе</div></div>
                <div class="stat-card"><div class="stat-value">${ready}</div><div class="stat-label">Готово</div></div>
                <div class="stat-card"><div class="stat-value">${clientsRes.count}</div><div class="stat-label">Клиентов</div></div>
            `;

            // Orders
            document.getElementById('orders').innerHTML = ordersRes.orders.map(o => `
                <div class="card">
                    <div class="card-header">
                        <div>
                            <div class="card-title">${o.number}</div>
                            <div class="card-subtitle">${o.client}</div>
                        </div>
                        <span class="badge ${getBadgeClass(o.status)}">${o.status}</span>
                    </div>
                    <div class="info-row">
                        <span>${o.car}</span>
                        <span class="sum">${o.sum.toLocaleString('ru-RU')} ₽</span>
                    </div>
                </div>
            `).join('');

            // Clients
            document.getElementById('clients').innerHTML = clientsRes.clients.map(c => `
                <div class="card">
                    <div class="card-header">
                        <div>
                            <div class="card-title">${c.name}</div>
                            <div class="card-subtitle">${c.phone}</div>
                        </div>
                        <span style="color:#666">${c.code}</span>
                    </div>
                    <div class="info-row">
                        <span>${c.car}</span>
                    </div>
                </div>
            `).join('');
        }

        loadData();
    </script>
</body>
</html>
"""

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
