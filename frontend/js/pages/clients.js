/**
 * Clients Page
 */
const ClientsPage = {
    /**
     * Initialize clients page
     */
    async init() {
        await this.loadClients();
        this.setupSearch();
    },

    /**
     * Setup search functionality
     */
    setupSearch() {
        const searchInput = document.getElementById('clients-search');
        if (searchInput) {
            searchInput.addEventListener('input', (e) => {
                this.filterClients(e.target.value);
            });
        }
    },

    /**
     * Load clients from API
     */
    async loadClients() {
        const container = document.getElementById('clients-list');
        container.innerHTML = 'Загрузка...';

        try {
            const data = await API.getClients({ limit: 100 });
            State.clients = data.clients || [];
            this.renderClients(State.clients);
        } catch (error) {
            container.innerHTML = `Ошибка: ${error.message}`;
        }
    },

    /**
     * Filter clients by search query
     */
    filterClients(query) {
        if (!query || query.length < 2) {
            this.renderClients(State.clients);
            return;
        }

        const q = query.toLowerCase();
        const filtered = State.clients.filter(c =>
            (c.name || '').toLowerCase().includes(q) ||
            (c.code || '').toLowerCase().includes(q) ||
            (c.phone || '').includes(q)
        );
        this.renderClients(filtered);
    },

    /**
     * Render clients list
     */
    renderClients(clients) {
        const container = document.getElementById('clients-list');

        if (!clients.length) {
            container.innerHTML = '<div class="empty-row">Нет клиентов</div>';
            return;
        }

        container.innerHTML = clients.map(c => `
            <div class="list-item" onclick="ClientsPage.openClient('${c.ref}')">
                <div class="client-avatar">${(c.name || '?')[0]}</div>
                <div class="client-info">
                    <div class="client-name">${c.name || '—'}</div>
                    <div class="client-details">${c.phone || ''} ${c.inn ? '• ИНН: ' + c.inn : ''}</div>
                </div>
            </div>
        `).join('');
    },

    /**
     * Open client card
     */
    async openClient(ref) {
        try {
            const data = await API.getClient(ref);
            State.setCurrentClient(data.client);
            State.setClientCars(data.cars || []);

            // Store orders for client card page
            State.currentClientOrders = data.orders || [];

            App.showPage('client-card');
            ClientCardPage.render(data);
        } catch (error) {
            alert('Ошибка загрузки клиента: ' + error.message);
        }
    },

    /**
     * Create new client
     */
    async createClient() {
        const name = document.getElementById('new-client-name').value.trim();
        const inn = document.getElementById('new-client-inn').value.trim();
        const comment = document.getElementById('new-client-comment').value.trim();

        if (!name) {
            alert('Введите наименование клиента');
            return;
        }

        try {
            const result = await API.createClient({ name, inn, comment });

            if (result.success) {
                alert('Клиент создан');
                App.closeModal('new-client');

                // Clear form
                document.getElementById('new-client-name').value = '';
                document.getElementById('new-client-inn').value = '';
                document.getElementById('new-client-comment').value = '';

                // Reload clients
                await this.loadClients();
            } else {
                alert('Ошибка: ' + (result.error || 'Неизвестная ошибка'));
            }
        } catch (error) {
            alert('Ошибка создания клиента: ' + error.message);
        }
    }
};
