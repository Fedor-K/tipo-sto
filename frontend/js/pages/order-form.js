/**
 * Order Form Page
 */
const OrderForm = {
    /**
     * Initialize order form page
     */
    async init() {
        State.clearOrderForm();
        this.renderClientInfo();
        this.renderCars();
        this.renderWorks();
        this.renderParts();
        this.updateTotals();
        await this.loadCatalogs();
    },

    /**
     * Render client info
     */
    renderClientInfo() {
        const container = document.getElementById('order-form-client');
        const client = State.currentClient;

        if (!client) {
            container.innerHTML = 'Не выбран';
            return;
        }

        container.innerHTML = `
            <div style="font-weight: 600;">${client.name || '—'}</div>
            <div style="font-size: 12px; color: #888;">${client.type || ''}</div>
        `;
    },

    /**
     * Render cars list
     */
    renderCars() {
        const container = document.getElementById('order-form-cars');
        const cars = State.currentClientCars;

        let html = '';

        if (cars.length) {
            html = cars.map(c => `
                <div class="car-item" onclick="OrderForm.selectCar(this, '${c.ref}')">
                    <span class="car-icon">🚗</span>
                    <div class="car-info">
                        <div class="car-name">${c.name || '—'}</div>
                        <div class="car-vin">VIN: ${c.vin || '—'}</div>
                    </div>
                </div>
            `).join('');
        }

        html += `
            <div style="margin-top: 10px; padding-top: 10px; border-top: 1px solid #eee;">
                <button class="btn btn-secondary btn-sm" onclick="OrderForm.openCarSelector()">
                    Выбрать из справочника
                </button>
            </div>
        `;

        container.innerHTML = html;
    },

    /**
     * Select car
     */
    selectCar(element, ref) {
        document.querySelectorAll('#order-form-cars .car-item').forEach(el => {
            el.classList.remove('selected');
        });
        element.classList.add('selected');
        document.getElementById('selected-car-key').value = ref;
    },

    /**
     * Open car selector modal
     */
    async openCarSelector() {
        App.openModal('car-select');
        const container = document.getElementById('car-select-modal-list');
        container.innerHTML = 'Загрузка...';

        try {
            const data = await API.getCars({ limit: 50 });
            State.cars = data.cars || [];
            this.renderCarModalList(State.cars);

            // Setup search
            const searchInput = document.getElementById('car-select-modal-search');
            searchInput.value = '';
            searchInput.oninput = (e) => {
                const q = e.target.value.toLowerCase();
                const filtered = State.cars.filter(c =>
                    (c.name || '').toLowerCase().includes(q) ||
                    (c.vin || '').toLowerCase().includes(q)
                );
                this.renderCarModalList(filtered);
            };
        } catch (error) {
            container.innerHTML = `Ошибка: ${error.message}`;
        }
    },

    /**
     * Render car modal list
     */
    renderCarModalList(cars) {
        const container = document.getElementById('car-select-modal-list');
        container.innerHTML = cars.slice(0, 30).map(c => `
            <div class="modal-list-item" onclick="OrderForm.selectCarFromModal('${c.ref}', '${(c.name || '').replace(/'/g, "\\'")}', '${c.vin || ''}')">
                <div class="modal-item-title">🚗 ${c.name || '—'}</div>
                <div class="modal-item-subtitle">VIN: ${c.vin || '—'}</div>
            </div>
        `).join('');
    },

    /**
     * Select car from modal
     */
    selectCarFromModal(ref, name, vin) {
        State.currentClientCars.push({ ref, name, vin });
        this.renderCars();
        App.closeModal('car-select');

        // Select the newly added car
        setTimeout(() => {
            const items = document.querySelectorAll('#order-form-cars .car-item');
            if (items.length) {
                const last = items[items.length - 1];
                this.selectCar(last, ref);
            }
        }, 100);
    },

    /**
     * Load catalogs for dropdowns
     */
    async loadCatalogs() {
        try {
            // Load repair types
            const repairTypes = await API.getRepairTypes();
            const rtSelect = document.getElementById('order-repair-type');
            rtSelect.innerHTML = '<option value="">— Выберите —</option>' +
                (repairTypes.items || []).map(t =>
                    `<option value="${t.ref}">${t.name}</option>`
                ).join('');

            // Load workshops
            const workshops = await API.getWorkshops();
            const wsSelect = document.getElementById('order-workshop');
            wsSelect.innerHTML = '<option value="">— Выберите —</option>' +
                (workshops.items || []).map(w =>
                    `<option value="${w.ref}">${w.name}</option>`
                ).join('');

            // Load employees (masters)
            const employees = await API.getEmployees();
            const empSelect = document.getElementById('order-master');
            empSelect.innerHTML = '<option value="">— Выберите —</option>' +
                (employees.items || []).map(e =>
                    `<option value="${e.ref}">${e.name}</option>`
                ).join('');
        } catch (error) {
            console.error('Failed to load catalogs:', error);
        }
    },

    /**
     * Render works table
     */
    renderWorks() {
        const tbody = document.getElementById('works-table');

        if (!State.orderWorks.length) {
            tbody.innerHTML = '<tr><td colspan="6" class="empty-row">Добавьте работы</td></tr>';
            return;
        }

        tbody.innerHTML = State.orderWorks.map((w, i) => `
            <tr>
                <td>${i + 1}</td>
                <td>${w.name}</td>
                <td><input type="number" value="${w.qty}" min="1" onchange="OrderForm.updateWork(${i}, 'qty', this.value)"></td>
                <td><input type="number" value="${w.price}" min="0" onchange="OrderForm.updateWork(${i}, 'price', this.value)"></td>
                <td>${(w.qty * w.price).toLocaleString('ru-RU')} \u20BD</td>
                <td><button class="remove-btn" onclick="OrderForm.removeWork(${i})">✕</button></td>
            </tr>
        `).join('');
    },

    /**
     * Add work from modal
     */
    addWork(ref, name) {
        State.addWork({ ref, name });
        this.renderWorks();
        this.updateTotals();
        App.closeModal('works');
    },

    /**
     * Update work
     */
    updateWork(index, field, value) {
        State.updateWork(index, field, value);
        this.renderWorks();
        this.updateTotals();
    },

    /**
     * Remove work
     */
    removeWork(index) {
        State.removeWork(index);
        this.renderWorks();
        this.updateTotals();
    },

    /**
     * Render parts table
     */
    renderParts() {
        const tbody = document.getElementById('parts-table');

        if (!State.orderParts.length) {
            tbody.innerHTML = '<tr><td colspan="7" class="empty-row">Добавьте запчасти</td></tr>';
            return;
        }

        tbody.innerHTML = State.orderParts.map((p, i) => {
            const sum = p.qty * p.price * (1 - p.discount / 100);
            return `
                <tr>
                    <td>${i + 1}</td>
                    <td>${p.name}</td>
                    <td><input type="number" value="${p.qty}" min="1" onchange="OrderForm.updatePart(${i}, 'qty', this.value)"></td>
                    <td><input type="number" value="${p.price}" min="0" onchange="OrderForm.updatePart(${i}, 'price', this.value)"></td>
                    <td><input type="number" value="${p.discount}" min="0" max="100" onchange="OrderForm.updatePart(${i}, 'discount', this.value)">%</td>
                    <td>${sum.toLocaleString('ru-RU')} \u20BD</td>
                    <td><button class="remove-btn" onclick="OrderForm.removePart(${i})">✕</button></td>
                </tr>
            `;
        }).join('');
    },

    /**
     * Add part from modal
     */
    addPart(ref, name) {
        State.addPart({ ref, name });
        this.renderParts();
        this.updateTotals();
        App.closeModal('parts');
    },

    /**
     * Update part
     */
    updatePart(index, field, value) {
        State.updatePart(index, field, value);
        this.renderParts();
        this.updateTotals();
    },

    /**
     * Remove part
     */
    removePart(index) {
        State.removePart(index);
        this.renderParts();
        this.updateTotals();
    },

    /**
     * Update totals
     */
    updateTotals() {
        const worksSum = State.getWorksTotal();
        const partsSum = State.getPartsTotal();
        const total = State.getOrderTotal();

        document.getElementById('works-sum').textContent = worksSum.toLocaleString('ru-RU') + ' \u20BD';
        document.getElementById('parts-sum').textContent = partsSum.toLocaleString('ru-RU') + ' \u20BD';
        document.getElementById('total-works').textContent = worksSum.toLocaleString('ru-RU') + ' \u20BD';
        document.getElementById('total-parts').textContent = partsSum.toLocaleString('ru-RU') + ' \u20BD';
        document.getElementById('total-sum').textContent = total.toLocaleString('ru-RU') + ' \u20BD';
    },

    /**
     * Open works modal
     */
    async openWorksModal() {
        const container = document.getElementById('works-modal-list');
        container.innerHTML = 'Загрузка...';

        try {
            const data = await API.getWorks({ limit: 100 });
            State.works = data.items || [];
            this.renderWorksModalList(State.works);

            // Setup search
            const searchInput = document.getElementById('works-modal-search');
            searchInput.value = '';
            searchInput.oninput = (e) => {
                const q = e.target.value.toLowerCase();
                const filtered = State.works.filter(w =>
                    (w.name || '').toLowerCase().includes(q)
                );
                this.renderWorksModalList(filtered);
            };
        } catch (error) {
            container.innerHTML = `Ошибка: ${error.message}`;
        }
    },

    /**
     * Render works modal list
     */
    renderWorksModalList(works) {
        const container = document.getElementById('works-modal-list');
        container.innerHTML = works.slice(0, 50).map(w => `
            <div class="modal-list-item" onclick="OrderForm.addWork('${w.ref}', '${(w.name || '').replace(/'/g, "\\'")}')">
                <div class="modal-item-title">🔧 ${w.name || '—'}</div>
                <div class="modal-item-subtitle">Время: ${w.time || 0} мин</div>
            </div>
        `).join('');
    },

    /**
     * Open parts modal
     */
    async openPartsModal() {
        const container = document.getElementById('parts-modal-list');
        container.innerHTML = 'Загрузка...';

        try {
            const data = await API.getParts({ limit: 100 });
            State.parts = data.items || [];
            this.renderPartsModalList(State.parts);

            // Setup search
            const searchInput = document.getElementById('parts-modal-search');
            searchInput.value = '';
            searchInput.oninput = (e) => {
                const q = e.target.value.toLowerCase();
                const filtered = State.parts.filter(p =>
                    (p.name || '').toLowerCase().includes(q) ||
                    (p.article || '').toLowerCase().includes(q)
                );
                this.renderPartsModalList(filtered);
            };
        } catch (error) {
            container.innerHTML = `Ошибка: ${error.message}`;
        }
    },

    /**
     * Render parts modal list
     */
    renderPartsModalList(parts) {
        const container = document.getElementById('parts-modal-list');
        container.innerHTML = parts.slice(0, 50).map(p => `
            <div class="modal-list-item" onclick="OrderForm.addPart('${p.ref}', '${(p.name || '').replace(/'/g, "\\'")}')">
                <div class="modal-item-title">📦 ${p.name || '—'}</div>
                <div class="modal-item-subtitle">Артикул: ${p.article || '—'}</div>
            </div>
        `).join('');
    },

    /**
     * Save order
     */
    async save() {
        if (!State.currentClient) {
            alert('Нет клиента');
            return;
        }

        const carKey = document.getElementById('selected-car-key').value;
        const repairTypeKey = document.getElementById('order-repair-type').value;
        const workshopKey = document.getElementById('order-workshop').value;
        const masterKey = document.getElementById('order-master').value;
        const mileage = document.getElementById('order-mileage').value;
        const comment = document.getElementById('order-reason').value;

        // Format for backend API - use _key for refs (GUIDs)
        const orderData = {
            client_key: State.currentClient.ref,
            car_key: carKey || null,
            repair_type_key: repairTypeKey || null,
            workshop_key: workshopKey || null,
            master_key: masterKey || null,
            mileage: mileage || '0',
            comment: comment || 'Ремонт',
            works: State.orderWorks.map(w => ({
                work_key: w.ref,  // GUID of work
                qty: w.qty,
                price: w.price,
                sum: w.qty * w.price
            })),
            parts: State.orderParts.map(p => ({
                part_key: p.ref,  // GUID of nomenclature
                qty: p.qty,
                price: p.price,
                discount: p.discount,
                sum: p.qty * p.price * (1 - p.discount / 100)
            }))
        };

        try {
            const result = await API.createOrder(orderData);

            if (result.success) {
                alert('Заказ создан: №' + (result.number || '').trim());
                App.showPage('client-card');

                // Reload client orders
                const clientData = await API.getClient(State.currentClient.ref);
                ClientCardPage.renderOrders(clientData.orders || []);
            } else {
                alert('Ошибка: ' + (result.error || 'Неизвестная ошибка'));
            }
        } catch (error) {
            alert('Ошибка создания заказа: ' + error.message);
        }
    }
};
