/**
 * Orders Page
 */
const OrdersPage = {
    /**
     * Initialize orders page
     */
    async init() {
        await this.loadOrders();
        this.setupSearch();
    },

    /**
     * Setup search functionality
     */
    setupSearch() {
        const searchInput = document.getElementById('orders-search');
        if (searchInput) {
            searchInput.addEventListener('input', (e) => {
                this.filterOrders(e.target.value);
            });
        }
    },

    /**
     * Load orders from API
     */
    async loadOrders() {
        const container = document.getElementById('orders-list');
        container.innerHTML = 'Загрузка...';

        try {
            const data = await API.getOrders({ limit: 50 });
            State.orders = data.orders || [];
            this.renderOrders(State.orders);
        } catch (error) {
            container.innerHTML = `Ошибка: ${error.message}`;
        }
    },

    /**
     * Filter orders by search query
     */
    filterOrders(query) {
        if (!query || query.length < 2) {
            this.renderOrders(State.orders);
            return;
        }

        const q = query.toLowerCase();
        const filtered = State.orders.filter(o =>
            (o.number || '').toLowerCase().includes(q) ||
            (o.client || '').toLowerCase().includes(q) ||
            (o.comment || '').toLowerCase().includes(q)
        );
        this.renderOrders(filtered);
    },

    /**
     * Render orders list
     */
    renderOrders(orders) {
        const container = document.getElementById('orders-list');

        if (!orders.length) {
            container.innerHTML = '<div class="empty-row">Нет заказов</div>';
            return;
        }

        container.innerHTML = orders.map(o => `
            <div class="order-item" onclick="OrdersPage.openOrder('${o.ref}')">
                <div class="order-num">№${(o.number || '').trim()}</div>
                <div class="order-date">${o.date || ''}</div>
                <div class="order-desc">
                    <div class="order-client">${o.client || '—'}</div>
                    <div class="order-comment">${o.comment || 'Ремонт'}</div>
                </div>
                <div class="order-sum">${(o.sum || 0).toLocaleString('ru-RU')} \u20BD</div>
            </div>
        `).join('');
    },

    /**
     * Open order details
     */
    async openOrder(ref) {
        try {
            const order = await API.getOrder(ref);
            // For now, show alert with order info
            alert(`Заказ №${order.number}\nКлиент: ${order.client}\nСумма: ${order.sum} руб.\nСтатус: ${order.status}`);
        } catch (error) {
            alert('Ошибка загрузки заказа: ' + error.message);
        }
    }
};
