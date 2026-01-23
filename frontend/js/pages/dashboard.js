/**
 * Dashboard Page
 */
const DashboardPage = {
    /**
     * Initialize dashboard
     */
    async init() {
        await this.loadStats();
    },

    /**
     * Load dashboard statistics
     */
    async loadStats() {
        try {
            const stats = await API.getDashboardStats();

            document.getElementById('stat-orders-today').textContent = stats.orders_today || 0;
            document.getElementById('stat-sum-today').textContent =
                (stats.sum_today || 0).toLocaleString('ru-RU') + ' \u20BD';
            document.getElementById('stat-in-progress').textContent = stats.in_progress || 0;
            document.getElementById('stat-clients').textContent = stats.clients_count || 0;

        } catch (error) {
            console.error('Failed to load dashboard stats:', error);
        }
    }
};
