from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional
import httpx

app = FastAPI(title="TIPO-STO API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# 1C API Gateway URL
API_1C_URL = "http://185.222.161.252:8080"

# Models
class OrderCreate(BaseModel):
    client_code: str
    car: str = ""
    comment: str = ""

class OrderUpdate(BaseModel):
    status: Optional[str] = None
    comment: Optional[str] = None

async def fetch_from_1c(endpoint: str, method: str = "GET", data: dict = None):
    """Fetch data from 1C API Gateway"""
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            if method == "GET":
                response = await client.get(f"{API_1C_URL}{endpoint}")
            elif method == "POST":
                response = await client.post(f"{API_1C_URL}{endpoint}", json=data)
            elif method == "PUT":
                response = await client.put(f"{API_1C_URL}{endpoint}", json=data)
            return response.json()
    except Exception as e:
        return {"error": str(e)}

@app.get("/")
async def root():
    return {"status": "ok", "message": "TIPO-STO API is running", "mode": "live", "source": "1C"}

@app.get("/api/clients")
async def get_clients():
    data = await fetch_from_1c("/api/clients")
    if "error" in data:
        return {"clients": [], "count": 0, "error": data["error"]}
    return data

@app.get("/api/orders")
async def get_orders():
    data = await fetch_from_1c("/api/orders")
    if "error" in data:
        return {"orders": [], "count": 0, "error": data["error"]}
    return data

@app.get("/api/orders/{order_number}")
async def get_order(order_number: str):
    data = await fetch_from_1c(f"/api/orders/{order_number}")
    return data

@app.post("/api/orders")
async def create_order(order: OrderCreate):
    data = await fetch_from_1c("/api/orders", method="POST", data=order.dict())
    return data

@app.put("/api/orders/{order_number}")
async def update_order(order_number: str, order: OrderUpdate):
    data = await fetch_from_1c(f"/api/orders/{order_number}", method="PUT", data=order.dict())
    return data

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
        .card { background: white; border-radius: 12px; padding: 20px; margin-bottom: 15px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); cursor: pointer; transition: transform 0.1s; }
        .card:hover { transform: translateY(-2px); box-shadow: 0 4px 8px rgba(0,0,0,0.15); }
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
        .stats { display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 15px; margin-bottom: 20px; }
        .stat-card { background: white; padding: 20px; border-radius: 12px; text-align: center; }
        .stat-value { font-size: 32px; font-weight: 700; color: #2196F3; }
        .stat-label { color: #666; margin-top: 5px; }

        /* Button styles */
        .btn { padding: 12px 24px; border: none; border-radius: 8px; cursor: pointer; font-size: 16px; font-weight: 500; }
        .btn-primary { background: #2196F3; color: white; }
        .btn-primary:hover { background: #1976D2; }
        .btn-secondary { background: #E0E0E0; color: #333; }
        .btn-success { background: #4CAF50; color: white; }
        .btn-success:hover { background: #388E3C; }
        .add-btn { position: fixed; bottom: 30px; right: 30px; width: 60px; height: 60px; border-radius: 50%; font-size: 30px; box-shadow: 0 4px 12px rgba(33,150,243,0.4); }

        /* Modal styles */
        .modal { display: none; position: fixed; top: 0; left: 0; width: 100%; height: 100%; background: rgba(0,0,0,0.5); z-index: 1000; }
        .modal.active { display: flex; align-items: center; justify-content: center; }
        .modal-content { background: white; border-radius: 16px; padding: 30px; width: 90%; max-width: 500px; max-height: 90vh; overflow-y: auto; }
        .modal-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px; }
        .modal-title { font-size: 24px; font-weight: 600; }
        .close-btn { background: none; border: none; font-size: 28px; cursor: pointer; color: #999; }

        /* Form styles */
        .form-group { margin-bottom: 20px; }
        .form-label { display: block; margin-bottom: 8px; font-weight: 500; color: #333; }
        .form-input, .form-select, .form-textarea { width: 100%; padding: 12px; border: 2px solid #E0E0E0; border-radius: 8px; font-size: 16px; }
        .form-input:focus, .form-select:focus, .form-textarea:focus { outline: none; border-color: #2196F3; }
        .form-textarea { min-height: 100px; resize: vertical; }
        .form-actions { display: flex; gap: 10px; justify-content: flex-end; margin-top: 20px; }

        /* Alert */
        .alert { padding: 15px; border-radius: 8px; margin-bottom: 15px; }
        .alert-success { background: #E8F5E9; color: #2E7D32; }
        .alert-error { background: #FFEBEE; color: #C62828; }
    </style>
</head>
<body>
    <div class="header">
        <h1>TIPO-STO</h1>
        <p>CRM для автосервиса</p>
    </div>

    <div class="container">
        <div id="alert"></div>
        <div class="stats" id="stats"></div>

        <div class="tabs">
            <button class="tab active" onclick="showTab('orders')">Заказ-наряды</button>
            <button class="tab" onclick="showTab('clients')">Клиенты</button>
        </div>

        <div id="orders"></div>
        <div id="clients" style="display:none"></div>
    </div>

    <button class="btn btn-primary add-btn" onclick="openCreateModal()" title="Создать заказ-наряд">+</button>

    <!-- Create Order Modal -->
    <div class="modal" id="createModal">
        <div class="modal-content">
            <div class="modal-header">
                <h2 class="modal-title">Новый заказ-наряд</h2>
                <button class="close-btn" onclick="closeModal('createModal')">&times;</button>
            </div>
            <form id="createForm" onsubmit="createOrder(event)">
                <div class="form-group">
                    <label class="form-label">Клиент *</label>
                    <select class="form-select" id="clientSelect" required>
                        <option value="">Выберите клиента...</option>
                    </select>
                </div>
                <div class="form-group">
                    <label class="form-label">Автомобиль</label>
                    <input type="text" class="form-input" id="carInput" placeholder="Марка, модель, гос. номер">
                </div>
                <div class="form-group">
                    <label class="form-label">Комментарий</label>
                    <textarea class="form-textarea" id="commentInput" placeholder="Описание работ..."></textarea>
                </div>
                <div class="form-actions">
                    <button type="button" class="btn btn-secondary" onclick="closeModal('createModal')">Отмена</button>
                    <button type="submit" class="btn btn-success">Создать</button>
                </div>
            </form>
        </div>
    </div>

    <!-- Edit Order Modal -->
    <div class="modal" id="editModal">
        <div class="modal-content">
            <div class="modal-header">
                <h2 class="modal-title">Редактирование <span id="editOrderNumber"></span></h2>
                <button class="close-btn" onclick="closeModal('editModal')">&times;</button>
            </div>
            <form id="editForm" onsubmit="updateOrder(event)">
                <input type="hidden" id="editOrderId">
                <div class="form-group">
                    <label class="form-label">Клиент</label>
                    <input type="text" class="form-input" id="editClient" readonly style="background:#f5f5f5">
                </div>
                <div class="form-group">
                    <label class="form-label">Статус</label>
                    <select class="form-select" id="editStatus">
                        <option value="Черновик">Черновик</option>
                        <option value="Проведен">Проведен</option>
                    </select>
                </div>
                <div class="form-group">
                    <label class="form-label">Комментарий</label>
                    <textarea class="form-textarea" id="editComment"></textarea>
                </div>
                <div class="form-actions">
                    <button type="button" class="btn btn-secondary" onclick="closeModal('editModal')">Отмена</button>
                    <button type="submit" class="btn btn-success">Сохранить</button>
                </div>
            </form>
        </div>
    </div>

    <script>
        let clientsData = [];
        let ordersData = [];

        function getBadgeClass(status) {
            const map = {
                'Новый': 'badge-new',
                'В работе': 'badge-work',
                'Готов': 'badge-ready',
                'Выдан': 'badge-done',
                'Черновик': 'badge-new',
                'Проведен': 'badge-done'
            };
            return map[status] || 'badge-new';
        }

        function showTab(tab) {
            document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
            event.target.classList.add('active');
            document.getElementById('orders').style.display = tab === 'orders' ? 'block' : 'none';
            document.getElementById('clients').style.display = tab === 'clients' ? 'block' : 'none';
        }

        function showAlert(message, type = 'success') {
            const alert = document.getElementById('alert');
            alert.innerHTML = `<div class="alert alert-${type}">${message}</div>`;
            setTimeout(() => { alert.innerHTML = ''; }, 5000);
        }

        function openCreateModal() {
            // Populate client select
            const select = document.getElementById('clientSelect');
            select.innerHTML = '<option value="">Выберите клиента...</option>' +
                clientsData.map(c => `<option value="${c.code}">${c.name}</option>`).join('');
            document.getElementById('carInput').value = '';
            document.getElementById('commentInput').value = '';
            document.getElementById('createModal').classList.add('active');
        }

        function openEditModal(orderNumber) {
            fetch(`/api/orders/${orderNumber}`)
                .then(r => r.json())
                .then(order => {
                    if (order.error) {
                        showAlert(order.error, 'error');
                        return;
                    }
                    document.getElementById('editOrderId').value = order.number;
                    document.getElementById('editOrderNumber').textContent = order.number;
                    document.getElementById('editClient').value = order.client;
                    document.getElementById('editStatus').value = order.status;
                    document.getElementById('editComment').value = order.comment || '';
                    document.getElementById('editModal').classList.add('active');
                })
                .catch(e => showAlert('Ошибка загрузки: ' + e, 'error'));
        }

        function closeModal(modalId) {
            document.getElementById(modalId).classList.remove('active');
        }

        async function createOrder(e) {
            e.preventDefault();
            const data = {
                client_code: document.getElementById('clientSelect').value,
                car: document.getElementById('carInput').value,
                comment: document.getElementById('commentInput').value
            };

            try {
                const res = await fetch('/api/orders', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify(data)
                });
                const result = await res.json();

                if (result.success) {
                    showAlert(`Заказ-наряд ${result.number} создан!`);
                    closeModal('createModal');
                    loadData();
                } else {
                    showAlert(result.detail || result.error || 'Ошибка создания', 'error');
                }
            } catch (e) {
                showAlert('Ошибка: ' + e, 'error');
            }
        }

        async function updateOrder(e) {
            e.preventDefault();
            const orderNumber = document.getElementById('editOrderId').value;
            const data = {
                status: document.getElementById('editStatus').value,
                comment: document.getElementById('editComment').value
            };

            try {
                const res = await fetch(`/api/orders/${orderNumber}`, {
                    method: 'PUT',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify(data)
                });
                const result = await res.json();

                if (result.success) {
                    showAlert(`Заказ-наряд ${orderNumber} обновлен!`);
                    closeModal('editModal');
                    loadData();
                } else {
                    showAlert(result.detail || result.error || 'Ошибка обновления', 'error');
                }
            } catch (e) {
                showAlert('Ошибка: ' + e, 'error');
            }
        }

        async function loadData() {
            try {
                const [clientsRes, ordersRes] = await Promise.all([
                    fetch('/api/clients').then(r => r.json()),
                    fetch('/api/orders').then(r => r.json())
                ]);

                clientsData = clientsRes.clients || [];
                ordersData = ordersRes.orders || [];

                // Stats
                const posted = ordersData.filter(o => o.status === 'Проведен').length;
                const draft = ordersData.filter(o => o.status === 'Черновик').length;
                document.getElementById('stats').innerHTML = `
                    <div class="stat-card"><div class="stat-value">${ordersRes.count}</div><div class="stat-label">Заказ-нарядов</div></div>
                    <div class="stat-card"><div class="stat-value">${posted}</div><div class="stat-label">Проведено</div></div>
                    <div class="stat-card"><div class="stat-value">${draft}</div><div class="stat-label">Черновиков</div></div>
                    <div class="stat-card"><div class="stat-value">${clientsRes.count}</div><div class="stat-label">Клиентов</div></div>
                `;

                // Orders
                if (ordersData.length === 0) {
                    document.getElementById('orders').innerHTML = '<div class="card"><p style="text-align:center;color:#999">Нет заказ-нарядов. Нажмите + чтобы создать.</p></div>';
                } else {
                    document.getElementById('orders').innerHTML = ordersData.map(o => `
                        <div class="card" onclick="openEditModal('${o.number}')">
                            <div class="card-header">
                                <div>
                                    <div class="card-title">${o.number}</div>
                                    <div class="card-subtitle">${o.client}</div>
                                </div>
                                <span class="badge ${getBadgeClass(o.status)}">${o.status}</span>
                            </div>
                            <div class="info-row">
                                <span>${o.date || ''}</span>
                                <span class="sum">${(o.sum || 0).toLocaleString('ru-RU')} ₽</span>
                            </div>
                            ${o.comment ? `<div style="margin-top:10px;color:#666;font-size:14px">${o.comment}</div>` : ''}
                        </div>
                    `).join('');
                }

                // Clients
                document.getElementById('clients').innerHTML = clientsData.map(c => `
                    <div class="card">
                        <div class="card-header">
                            <div>
                                <div class="card-title">${c.name}</div>
                                <div class="card-subtitle">${c.phone || 'Нет телефона'}</div>
                            </div>
                            <span style="color:#666">${c.code}</span>
                        </div>
                    </div>
                `).join('');

            } catch (e) {
                showAlert('Ошибка загрузки данных: ' + e, 'error');
            }
        }

        // Close modal on outside click
        document.querySelectorAll('.modal').forEach(modal => {
            modal.addEventListener('click', (e) => {
                if (e.target === modal) closeModal(modal.id);
            });
        });

        loadData();
    </script>
</body>
</html>
"""

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
