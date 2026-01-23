/**
 * Client Card Page
 */
const ClientCardPage = {
    /**
     * Initialize client card page
     */
    init() {
        // Page is rendered when client is selected
    },

    /**
     * Render client card
     */
    render(data) {
        const client = data.client || {};

        // Header
        document.getElementById('client-card-title').textContent = client.name || 'Клиент';
        document.getElementById('client-card-name').textContent = client.full_name || client.name || '—';
        document.getElementById('client-card-type').textContent = client.type || 'Клиент';
        document.getElementById('client-card-avatar').textContent = (client.name || '?')[0];

        // Stats
        document.getElementById('client-stat-orders').textContent = data.orders_count || 0;
        document.getElementById('client-stat-sum').textContent =
            (data.total_sum || 0).toLocaleString('ru-RU') + ' \u20BD';

        // Info
        document.getElementById('client-card-inn').textContent = client.inn || '—';
        document.getElementById('client-card-comment').textContent = client.comment || '—';

        // Cars
        this.renderCars(data.cars || []);

        // Orders
        this.renderOrders(data.orders || []);
    },

    /**
     * Render client's cars
     */
    renderCars(cars) {
        const container = document.getElementById('client-cars-list');

        if (!cars.length) {
            container.innerHTML = `
                <div style="color: #888; padding: 10px;">
                    Нет автомобилей в истории.<br>
                    <small>При создании заказа можно выбрать из справочника.</small>
                </div>
            `;
            return;
        }

        container.innerHTML = cars.map(c => `
            <div class="car-item">
                <span class="car-icon">🚗</span>
                <div class="car-info">
                    <div class="car-name">${c.name || '—'}</div>
                    <div class="car-vin">VIN: ${c.vin || '—'}</div>
                </div>
            </div>
        `).join('');
    },

    /**
     * Render client's orders
     */
    renderOrders(orders) {
        const container = document.getElementById('client-orders-list');

        if (!orders.length) {
            container.innerHTML = '<div class="empty-row">Нет заказов</div>';
            return;
        }

        container.innerHTML = orders.map(o => `
            <div class="order-item">
                <div class="order-num">№${(o.number || '').trim()}</div>
                <div class="order-date">${o.date || ''}</div>
                <div class="order-desc">
                    <div class="order-comment">${o.comment || 'Ремонт'}</div>
                </div>
                <div class="order-sum">${(o.sum || 0).toLocaleString('ru-RU')} \u20BD</div>
            </div>
        `).join('');
    }
};
