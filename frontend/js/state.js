/**
 * Application State Management
 */
const State = {
    // Current page
    currentPage: 'orders',

    // Current client (for client card and order form)
    currentClient: null,

    // Client's cars (loaded from order history)
    currentClientCars: [],

    // Cached data
    clients: [],
    orders: [],
    cars: [],
    works: [],
    parts: [],

    // Order form data
    orderWorks: [],
    orderParts: [],

    // Catalogs
    repairTypes: [],
    workshops: [],
    employees: [],

    /**
     * Set current client
     */
    setCurrentClient(client) {
        this.currentClient = client;
        this.currentClientCars = [];
    },

    /**
     * Set client cars
     */
    setClientCars(cars) {
        this.currentClientCars = cars;
    },

    /**
     * Clear order form
     */
    clearOrderForm() {
        this.orderWorks = [];
        this.orderParts = [];
    },

    /**
     * Add work to order
     */
    addWork(work) {
        this.orderWorks.push({
            ref: work.ref,
            name: work.name,
            qty: 1,
            price: 0
        });
    },

    /**
     * Remove work from order
     */
    removeWork(index) {
        this.orderWorks.splice(index, 1);
    },

    /**
     * Update work in order
     */
    updateWork(index, field, value) {
        if (this.orderWorks[index]) {
            this.orderWorks[index][field] = parseFloat(value) || 0;
        }
    },

    /**
     * Add part to order
     */
    addPart(part) {
        this.orderParts.push({
            ref: part.ref,
            name: part.name,
            qty: 1,
            price: 0,
            discount: 0
        });
    },

    /**
     * Remove part from order
     */
    removePart(index) {
        this.orderParts.splice(index, 1);
    },

    /**
     * Update part in order
     */
    updatePart(index, field, value) {
        if (this.orderParts[index]) {
            this.orderParts[index][field] = parseFloat(value) || 0;
        }
    },

    /**
     * Calculate works total
     */
    getWorksTotal() {
        return this.orderWorks.reduce((sum, w) => sum + (w.qty * w.price), 0);
    },

    /**
     * Calculate parts total (with discounts)
     */
    getPartsTotal() {
        return this.orderParts.reduce((sum, p) => {
            const subtotal = p.qty * p.price;
            const discount = subtotal * (p.discount / 100);
            return sum + (subtotal - discount);
        }, 0);
    },

    /**
     * Calculate order total
     */
    getOrderTotal() {
        return this.getWorksTotal() + this.getPartsTotal();
    }
};
