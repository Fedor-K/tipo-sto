/**
 * Cars Page
 */
const CarsPage = {
    /**
     * Initialize cars page
     */
    async init() {
        await this.loadCars();
        this.setupSearch();
    },

    /**
     * Setup search functionality
     */
    setupSearch() {
        const searchInput = document.getElementById('cars-search');
        if (searchInput) {
            searchInput.addEventListener('input', (e) => {
                this.filterCars(e.target.value);
            });
        }
    },

    /**
     * Load cars from API
     */
    async loadCars() {
        const container = document.getElementById('cars-list');
        container.innerHTML = 'Загрузка...';

        try {
            const data = await API.getCars({ limit: 100 });
            State.cars = data.cars || [];
            this.renderCars(State.cars);
        } catch (error) {
            container.innerHTML = `Ошибка: ${error.message}`;
        }
    },

    /**
     * Filter cars by search query
     */
    filterCars(query) {
        if (!query || query.length < 2) {
            this.renderCars(State.cars);
            return;
        }

        const q = query.toLowerCase();
        const filtered = State.cars.filter(c =>
            (c.name || '').toLowerCase().includes(q) ||
            (c.vin || '').toLowerCase().includes(q) ||
            (c.plate || '').toLowerCase().includes(q)
        );
        this.renderCars(filtered);
    },

    /**
     * Render cars list
     */
    renderCars(cars) {
        const container = document.getElementById('cars-list');

        if (!cars.length) {
            container.innerHTML = '<div class="empty-row">Нет автомобилей</div>';
            return;
        }

        container.innerHTML = cars.map(c => `
            <div class="list-item" onclick="CarsPage.openCar('${c.ref}')">
                <span class="car-icon" style="font-size: 24px; margin-right: 15px;">🚗</span>
                <div class="car-info" style="flex: 1;">
                    <div class="car-name">${c.name || '—'}</div>
                    <div class="car-vin">VIN: ${c.vin || '—'} ${c.plate ? '• ' + c.plate : ''}</div>
                </div>
                ${c.owner_name ? `<div class="car-owner" style="color: #2196f3; font-size: 13px;">👤 ${c.owner_name}</div>` : '<div class="car-owner" style="color: #999; font-size: 12px;">Без владельца</div>'}
            </div>
        `).join('');
    },

    /**
     * Open car details
     */
    async openCar(ref) {
        try {
            const car = await API.getCar(ref);
            alert(`Автомобиль: ${car.name}\nVIN: ${car.vin || '—'}\nГос. номер: ${car.plate || '—'}`);
        } catch (error) {
            alert('Ошибка загрузки автомобиля: ' + error.message);
        }
    }
};
