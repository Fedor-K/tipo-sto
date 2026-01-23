/**
 * Main Application Controller
 */
const App = {
    /**
     * Initialize application
     */
    async init() {
        console.log('TIPO-STO initializing...');

        // Setup navigation
        this.setupNavigation();

        // Load initial page
        await this.showPage('orders');

        // Preload clients list
        ClientsPage.loadClients();

        console.log('TIPO-STO ready');
    },

    /**
     * Setup navigation handlers
     */
    setupNavigation() {
        document.querySelectorAll('.nav-item').forEach(item => {
            item.addEventListener('click', () => {
                const page = item.getAttribute('data-page');
                if (page) {
                    this.showPage(page);
                }
            });
        });
    },

    /**
     * Show page
     */
    async showPage(pageName) {
        State.currentPage = pageName;

        // Hide all pages
        document.querySelectorAll('.page').forEach(page => {
            page.classList.add('hidden');
        });

        // Update navigation
        document.querySelectorAll('.nav-item').forEach(item => {
            item.classList.remove('active');
            if (item.getAttribute('data-page') === pageName) {
                item.classList.add('active');
            }
        });

        // Show target page
        const pageElement = document.getElementById(`page-${pageName}`);
        if (pageElement) {
            pageElement.classList.remove('hidden');
        }

        // Initialize page
        switch (pageName) {
            case 'dashboard':
                await DashboardPage.init();
                break;
            case 'orders':
                await OrdersPage.init();
                break;
            case 'clients':
                await ClientsPage.init();
                break;
            case 'client-card':
                ClientCardPage.init();
                break;
            case 'order-form':
                await OrderForm.init();
                break;
            case 'cars':
                await CarsPage.init();
                break;
        }
    },

    /**
     * Open modal
     */
    openModal(type) {
        const modal = document.getElementById(`modal-${type}`);
        if (modal) {
            modal.classList.add('open');

            // Load modal content
            switch (type) {
                case 'works':
                    OrderForm.openWorksModal();
                    break;
                case 'parts':
                    OrderForm.openPartsModal();
                    break;
            }
        }
    },

    /**
     * Close modal
     */
    closeModal(type) {
        const modal = document.getElementById(`modal-${type}`);
        if (modal) {
            modal.classList.remove('open');
        }
    },

    /**
     * Format currency
     */
    formatCurrency(value) {
        return (value || 0).toLocaleString('ru-RU') + ' \u20BD';
    },

    /**
     * Format date
     */
    formatDate(dateStr) {
        if (!dateStr) return '';
        const date = new Date(dateStr);
        return date.toLocaleDateString('ru-RU');
    }
};

// Initialize app when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
    App.init();
});

// Close modals on escape key
document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') {
        document.querySelectorAll('.modal.open').forEach(modal => {
            modal.classList.remove('open');
        });
    }
});

// Close modals on backdrop click
document.addEventListener('click', (e) => {
    if (e.target.classList.contains('modal')) {
        e.target.classList.remove('open');
    }
});
