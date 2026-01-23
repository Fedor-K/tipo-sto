/**
 * API Client for TIPO-STO Backend
 */
const API = {
    baseUrl: '/api',

    /**
     * Make API request
     */
    async request(endpoint, options = {}) {
        const url = `${this.baseUrl}${endpoint}`;
        const config = {
            headers: {
                'Content-Type': 'application/json',
                ...options.headers
            },
            ...options
        };

        try {
            const response = await fetch(url, config);
            const data = await response.json();

            if (!response.ok) {
                throw new Error(data.error || data.detail || 'Request failed');
            }

            return data;
        } catch (error) {
            console.error(`API Error [${endpoint}]:`, error);
            throw error;
        }
    },

    /**
     * GET request
     */
    async get(endpoint, params = {}) {
        const queryString = new URLSearchParams(params).toString();
        const url = queryString ? `${endpoint}?${queryString}` : endpoint;
        return this.request(url);
    },

    /**
     * POST request
     */
    async post(endpoint, data = {}) {
        return this.request(endpoint, {
            method: 'POST',
            body: JSON.stringify(data)
        });
    },

    /**
     * PATCH request
     */
    async patch(endpoint, data = {}) {
        return this.request(endpoint, {
            method: 'PATCH',
            body: JSON.stringify(data)
        });
    },

    // ===== Clients =====

    /**
     * Get clients list
     */
    async getClients(params = {}) {
        return this.get('/clients', params);
    },

    /**
     * Get client details
     */
    async getClient(ref) {
        return this.get(`/clients/${ref}`);
    },

    /**
     * Get client's cars
     */
    async getClientCars(ref) {
        return this.get(`/clients/${ref}/cars`);
    },

    /**
     * Get client's orders
     */
    async getClientOrders(ref) {
        return this.get(`/clients/${ref}/orders`);
    },

    /**
     * Create client
     */
    async createClient(data) {
        return this.post('/clients', data);
    },

    // ===== Orders =====

    /**
     * Get orders list
     */
    async getOrders(params = {}) {
        return this.get('/orders', params);
    },

    /**
     * Get order details
     */
    async getOrder(ref) {
        return this.get(`/orders/${ref}`);
    },

    /**
     * Create order
     */
    async createOrder(data) {
        return this.post('/orders', data);
    },

    /**
     * Update order
     */
    async updateOrder(ref, data) {
        return this.patch(`/orders/${ref}`, data);
    },

    // ===== Cars =====

    /**
     * Get cars list
     */
    async getCars(params = {}) {
        return this.get('/cars', params);
    },

    /**
     * Get car details
     */
    async getCar(ref) {
        return this.get(`/cars/${ref}`);
    },

    /**
     * Create car
     */
    async createCar(data) {
        return this.post('/cars', data);
    },

    // ===== Catalogs =====

    /**
     * Get works catalog
     */
    async getWorks(params = {}) {
        return this.get('/catalogs/works', params);
    },

    /**
     * Get parts catalog
     */
    async getParts(params = {}) {
        return this.get('/catalogs/parts', params);
    },

    /**
     * Get repair types
     */
    async getRepairTypes() {
        return this.get('/catalogs/repair-types');
    },

    /**
     * Get workshops
     */
    async getWorkshops() {
        return this.get('/catalogs/workshops');
    },

    /**
     * Get employees
     */
    async getEmployees() {
        return this.get('/catalogs/employees');
    },

    /**
     * Get order statuses
     */
    async getOrderStatuses() {
        return this.get('/catalogs/order-statuses');
    },

    // ===== Stats =====

    /**
     * Get dashboard stats
     */
    async getDashboardStats() {
        return this.get('/stats/dashboard');
    },

    // ===== Search =====

    /**
     * Universal search
     */
    async search(query) {
        return this.get('/search', { q: query });
    }
};
