// ============================================================
// ANALYTICAL DASHBOARD & MASTER DATA JAVASCRIPT
// ============================================================

let masterInventory = [];
let chartMonthly = null;
let chartCategory = null;
let chartTopExp = null;
let chartSupplier = null;

// ============================================================
// INITIALIZATION
// ============================================================
document.addEventListener("DOMContentLoaded", async () => {
    try {
        if (typeof setupDropZones === "function") setupDropZones();
        await loadUser();
        await loadStats();
        await loadCategories();
        if (typeof loadConversations === "function") await loadConversations();
        if (typeof connectWebSocket === "function") connectWebSocket();
    } catch (error) {
        console.error("Dashboard initialization error:", error);
    }
});

// ============================================================
// NAVIGATION
// ============================================================
function switchMainTab(tabId) {
    const views = ["chat", "inventory", "analytics", "upload"];
    views.forEach(view => {
        const viewElement = document.getElementById(`view-${view}`);
        const buttonElement = document.getElementById(`tab-btn-${view}`);
        if (viewElement) viewElement.style.display = (view === tabId ? "block" : "none");
        if (buttonElement) buttonElement.classList.toggle("active", view === tabId);
    });

    const pageTitle = document.getElementById("page-title");
    const pageSubtitle = document.getElementById("page-subtitle");

    if (tabId === "chat") {
        if (pageTitle) pageTitle.textContent = "Inventory Intelligence";
        if (pageSubtitle) pageSubtitle.textContent = "Real-time stock assistance, procurement intelligence & AI assistant";
    } else if (tabId === "inventory") {
        if (pageTitle) pageTitle.textContent = "Inventory Management";
        if (pageSubtitle) pageSubtitle.textContent = "Real-time inventory records. Click Edit to update stock or thresholds.";
        if (typeof loadInventoryTabTable === "function") loadInventoryTabTable();
    } else if (tabId === "analytics") {
        if (pageTitle) pageTitle.textContent = "Real-Time Analytical Dashboard";
        if (pageSubtitle) pageSubtitle.textContent = "Interactive spending trends, category breakdown & master inventory";
        refreshDashboardData();
    } else if (tabId === "upload") {
        if (pageTitle) pageTitle.textContent = "Excel Ingestion & Integration Hub";
        if (pageSubtitle) pageSubtitle.textContent = "Upload workbooks with duplicate prevention & auto categorization";
        if (typeof loadImportHistory === "function") loadImportHistory();
    }
}

// ============================================================
// USER
// ============================================================
async function loadUser() {
    try {
        const token = typeof getToken === "function" ? getToken() : localStorage.getItem("access_token");
        const response = await fetch("/api/auth/me", {
            headers: token ? { "Authorization": `Bearer ${token}` } : {}
        });
        if (!response.ok) return;

        const user = await response.json();
        const avatar = document.getElementById("sidebar-avatar");
        const nameElement = document.getElementById("sidebar-name");
        if (avatar && user.name) avatar.textContent = user.name.charAt(0).toUpperCase();
        if (nameElement && user.name) nameElement.textContent = user.name;
    } catch (error) {
        console.warn("Could not fetch user profile:", error);
    }
}

// ============================================================
// LOGOUT
// ============================================================
function handleLogout(event) {
    if (event) event.preventDefault();
    localStorage.removeItem("access_token");
    localStorage.removeItem("user");
    localStorage.removeItem("active_conversation_id");
    window.location.href = "/logout";
}

// ============================================================
// STATS
// ============================================================
async function loadStats() {
    try {
        const response = await fetch("/api/inventory/stats");
        if (!response.ok) {
            console.warn("Inventory stats request failed:", response.status);
            return;
        }

        const stats = await response.json();
        const totalElement = document.getElementById("stat-total");
        const lowElement = document.getElementById("stat-low");
        const unitsElement = document.getElementById("stat-units");
        const expensesElement = document.getElementById("stat-expenses");
        const badgeElement = document.getElementById("low-stock-badge");

        if (totalElement) totalElement.textContent = Number(stats.total_components || 0).toLocaleString();
        if (lowElement) lowElement.textContent = Number(stats.low_stock || 0).toLocaleString();
        if (unitsElement) unitsElement.textContent = Number(stats.total_units || 0).toLocaleString();
        if (expensesElement) expensesElement.textContent = "₹" + Number(stats.total_expenses || 0).toLocaleString(undefined, { maximumFractionDigits: 0 });
        if (badgeElement) badgeElement.textContent = Number(stats.low_stock || 0);
    } catch (error) {
        console.warn("Could not load stats:", error);
    }
}

// ============================================================
// CATEGORIES
// ============================================================
async function loadCategories() {
    const grid = document.getElementById("category-grid");
    if (!grid) return;

    try {
        const response = await fetch("/api/dashboard/analytics");
        if (!response.ok) return;

        const data = await response.json();
        const categories = Array.isArray(data.categories) ? data.categories : [];

        if (categories.length === 0) {
            grid.innerHTML = `
                <div class="conv-item-empty">
                    No inventory data yet.<br>
                    Upload Excel files in the <strong>Excel Import Hub</strong> to populate.
                </div>
            `;
            return;
        }

        const icons = ["📦", "📄", "⚙️", "🖥️", "🔋", "🔌", "📊", "🔀", "🚚", "💡"];
        grid.innerHTML = categories.map((category, index) => {
            const name = category.category || "Unknown";
            const count = Number(category.count || 0);
            const units = Number(category.units || 0);
            const expense = Number(category.expense || 0);

            return `
                <div class="category-card" onclick="quickAsk('Show all ${escapeHtml(name)}')">
                    <div class="category-icon">${icons[index % icons.length]}</div>
                    <div class="category-info">
                        <h4>${escapeHtml(name)}</h4>
                        <p>${count} product(s) · ${units} units · ₹${expense.toLocaleString()}</p>
                    </div>
                </div>
            `;
        }).join("");
    } catch (error) {
        console.warn("Could not load dynamic categories:", error);
    }
}

// ============================================================
// DASHBOARD DATA
// ============================================================
async function refreshDashboardData() {
    try {
        const response = await fetch("/api/dashboard/analytics");
        if (!response.ok) {
            console.error("Analytics API failed:", response.status);
            return;
        }

        const data = await response.json();
        await renderMasterTable();
        renderCharts(data);
        renderRecentProcurements(data.recent_procurements || []);
        renderRecentExpenses(data.recent_expenses || []);
    } catch (error) {
        console.error("Error refreshing dashboard data:", error);
    }
}

// ============================================================
// CHARTS
// ============================================================
async function renderCharts(data) {
    if (typeof Chart === "undefined") {
        console.error("Chart.js is not loaded.");
        return;
    }

    // 1. Monthly Expenses
    const monthlyCanvas = document.getElementById("chart-monthly-expenses");
    if (monthlyCanvas) {
        const monthly = Array.isArray(data.monthly_expenses) ? data.monthly_expenses : [];
        const labels = monthly.map(item => item.month || "Unknown");
        const values = monthly.map(item => Number(item.amount || 0));

        if (chartMonthly) { chartMonthly.destroy(); chartMonthly = null; }
        chartMonthly = new Chart(monthlyCanvas, {
            type: "line",
            data: {
                labels: labels.length ? labels : ["No Data"],
                datasets: [{
                    label: "Monthly Spend (₹)",
                    data: values.length ? values : [0],
                    borderColor: "#4f46e5",
                    backgroundColor: "rgba(79, 70, 229, 0.08)",
                    borderWidth: 2.5,
                    fill: true,
                    tension: 0.3,
                    pointBackgroundColor: "#4f46e5"
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: { legend: { display: false } },
                scales: { y: { beginAtZero: true } }
            }
        });
    }

    // 2. Category Breakdown
    const categoryCanvas = document.getElementById("chart-category-breakdown");
    if (categoryCanvas) {
        const categories = Array.isArray(data.categories) ? data.categories : [];
        const labels = categories.map(item => item.category || "Unknown");
        const values = categories.map(item => Number(item.units || 0));

        if (chartCategory) { chartCategory.destroy(); chartCategory = null; }
        chartCategory = new Chart(categoryCanvas, {
            type: "doughnut",
            data: {
                labels: labels.length ? labels : ["No Data"],
                datasets: [{
                    data: values.length ? values : [1],
                    backgroundColor: [
                        "#4f46e5", "#3b82f6", "#10b981", "#f59e0b",
                        "#8b5cf6", "#ec4899", "#06b6d4", "#64748b",
                        "#ef4444", "#14b8a6", "#f97316", "#84cc16"
                    ],
                    borderWidth: 2,
                    borderColor: "#fff"
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: { legend: { position: "right" } }
            }
        });
    }

    // 3. Top Expenses
    const topExpenseCanvas = document.getElementById("chart-top-expenses");
    if (topExpenseCanvas) {
        const topExpenses = Array.isArray(data.top_expenses) ? data.top_expenses : [];
        const labels = topExpenses.map(item => item.name || "Unknown");
        const values = topExpenses.map(item => Number(item.total_expense || 0));

        if (chartTopExp) { chartTopExp.destroy(); chartTopExp = null; }
        chartTopExp = new Chart(topExpenseCanvas, {
            type: "bar",
            data: {
                labels: labels.length ? labels : ["No Data"],
                datasets: [{
                    label: "Total Expense (₹)",
                    data: values.length ? values : [0],
                    backgroundColor: "#8b5cf6",
                    borderRadius: 6
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                indexAxis: "y",
                plugins: { legend: { display: false } }
            }
        });
    }

    // 4. Supplier Distribution
    const supplierCanvas = document.getElementById("chart-supplier-distribution");
    if (supplierCanvas) {
        try {
            const supplierResponse = await fetch("/api/inventory/suppliers");
            if (supplierResponse.ok) {
                let supplierData = await supplierResponse.json();
                let suppliers = Array.isArray(supplierData) ? supplierData :
                    (supplierData && Array.isArray(supplierData.value)) ? supplierData.value :
                    (supplierData && Array.isArray(supplierData.suppliers)) ? supplierData.suppliers : [];

                const labels = suppliers.map(supplier => String(supplier.supplier || "Unknown"));
                const values = suppliers.map(supplier => Number(supplier.total_units || 0));

                if (chartSupplier) { chartSupplier.destroy(); chartSupplier = null; }

                if (suppliers.length === 0 || values.every(v => v === 0)) {
                    const parent = supplierCanvas.parentElement;
                    if (parent) {
                        parent.innerHTML = `
                            <div style="width:100%; height:100%; min-height:300px; display:flex; align-items:center; justify-content:center; color:#64748b; font-size:14px;">
                                No supplier distribution data available.
                            </div>
                        `;
                    }
                } else {
                    chartSupplier = new Chart(supplierCanvas, {
                        type: "pie",
                        data: {
                            labels: labels,
                            datasets: [{
                                data: values,
                                backgroundColor: [
                                    "#10b981", "#3b82f6", "#f59e0b", "#ec4899",
                                    "#4f46e5", "#06b6d4", "#8b5cf6", "#ef4444",
                                    "#14b8a6", "#f97316", "#6366f1", "#84cc16"
                                ],
                                borderWidth: 2,
                                borderColor: "#ffffff"
                            }]
                        },
                        options: {
                            responsive: true,
                            maintainAspectRatio: false,
                            plugins: {
                                legend: { position: "right" },
                                tooltip: {
                                    callbacks: {
                                        label: function(context) {
                                            const supplier = context.label || "Unknown";
                                            const units = Number(context.raw || 0);
                                            const supplierInfo = suppliers.find(item => String(item.supplier || "Unknown") === supplier);
                                            const productCount = supplierInfo ? Number(supplierInfo.product_count || 0) : 0;
                                            return [`${supplier}`, `Stock: ${units.toLocaleString()} units`, `Products: ${productCount}`];
                                        }
                                    }
                                }
                            }
                        }
                    });
                }
            }
        } catch (error) {
            console.error("[Supplier Chart] Failed to load:", error);
        }
    }
}

// ============================================================
// TOGGLE CHARTS
// ============================================================
function toggleAllCharts() {
    const container = document.getElementById("analytics-charts-container");
    const button = document.getElementById("btn-toggle-all-charts");
    if (!container) return;

    const isHidden = container.style.display === "none";
    if (isHidden) {
        container.style.display = "grid";
        if (button) button.classList.add("active");
    } else {
        container.style.display = "none";
        if (button) button.classList.remove("active");
    }
}

// ============================================================
// MASTER INVENTORY TABLE
// ============================================================
async function renderMasterTable() {
    const tbody = document.getElementById("master-table-body");
    const categorySelect = document.getElementById("inventory-category-filter");
    if (!tbody) return;

    try {
        const response = await fetch("/api/inventory");
        if (!response.ok) return;

        masterInventory = await response.json();
        if (!Array.isArray(masterInventory)) masterInventory = [];

        if (categorySelect) {
            const uniqueCategories = Array.from(new Set(masterInventory.map(item => item.category).filter(Boolean)));
            const currentValue = categorySelect.value;
            categorySelect.innerHTML = `<option value="">All Categories</option>` +
                uniqueCategories.map(cat => `
                    <option value="${escapeHtml(cat)}" ${cat === currentValue ? "selected" : ""}>
                        ${escapeHtml(cat)}
                    </option>
                `).join("");
        }
        filterMasterTable();
    } catch (error) {
        console.error("Error loading master inventory table:", error);
    }
}

// ============================================================
// FILTER MASTER TABLE
// ============================================================
function filterMasterTable() {
    const tbody = document.getElementById("master-table-body");
    if (!tbody) return;

    const searchElement = document.getElementById("inventory-table-search");
    const categoryElement = document.getElementById("inventory-category-filter");
    const query = (searchElement?.value || "").toLowerCase().trim();
    const selectedCategory = categoryElement?.value || "";

    const filtered = masterInventory.filter(item => {
        const name = String(item.name || "").toLowerCase();
        const category = String(item.category || "").toLowerCase();
        const subCategory = String(item.sub_category || "").toLowerCase();
        const supplier = String(item.supplier || "").toLowerCase();
        const details = String(item.details || "").toLowerCase();

        const matchesSearch = !query ||
            name.includes(query) ||
            category.includes(query) ||
            subCategory.includes(query) ||
            supplier.includes(query) ||
            details.includes(query);

        const matchesCategory = !selectedCategory || item.category === selectedCategory;
        return matchesSearch && matchesCategory;
    });

    if (filtered.length === 0) {
        tbody.innerHTML = `<tr><td colspan="10" class="text-center">No matching inventory items found.</td></tr>`;
        return;
    }

    tbody.innerHTML = filtered.map(item => {
        const stock = Number(item.stock ?? item.current_stock ?? 0);
        const minStock = Number(item.min_stock ?? 0);
        const stockBadge = typeof getStockBadgeHtml === "function"
            ? getStockBadgeHtml(stock, minStock)
            : `<span>${stock} units</span>`;

        return `
            <tr>
                <td>
                    <strong>${escapeHtml(item.name || "Unknown")}</strong>
                    ${item.details ? `<br><small class="text-muted">${escapeHtml(item.details)}</small>` : ""}
                </td>
                <td><span class="badge-tag">${escapeHtml(item.category || "-")}</span></td>
                <td><span class="badge-tag" style="background:#f1f5f9; color:#475569;">${escapeHtml(item.sub_category || "-")}</span></td>
                <td>${stockBadge}</td>
                <td>${minStock} units</td>
                <td>₹${Number(item.unit_price || 0).toFixed(2)}</td>
                <td>₹${Number(item.total_expense || 0).toLocaleString()}</td>
                <td>${escapeHtml(item.supplier || "Standard Vendor")}</td>
                <td>
                    <span class="status-badge ${item.is_low_stock ? "low" : "ok"}">
                        ${item.is_low_stock ? "⚠️ Low Stock" : "✓ In Stock"}
                    </span>
                </td>
                <td>
                    <button class="edit-icon-btn" onclick="openEditModal('${item.id}')" title="Edit item">✏️ Edit</button>
                </td>
            </tr>
        `;
    }).join("");
}

// ============================================================
// RECENT PROCUREMENT
// ============================================================
function renderRecentProcurements(records) {
    const tbody = document.getElementById("recent-procurements-body");
    if (!tbody) return;

    if (!records.length) {
        tbody.innerHTML = `<tr><td colspan="6" class="text-center">No procurement records available.</td></tr>`;
        return;
    }

    tbody.innerHTML = records.map(record => `
        <tr>
            <td><strong>${escapeHtml(record.product_name || "-")}</strong></td>
            <td>${Number(record.quantity || 0)}</td>
            <td>₹${Number(record.unit_price || 0).toFixed(2)}</td>
            <td>
                <span class="status-badge ${String(record.order_status || "").toLowerCase() === "fulfilled" ? "ok" : "low"}">
                    ${escapeHtml(record.order_status || "Pending")}
                </span>
            </td>
            <td>${escapeHtml(record.vendor_name || "Vendor")}</td>
            <td>${escapeHtml(record.approved_by || "-")}</td>
        </tr>
    `).join("");
}

// ============================================================
// RECENT EXPENSES
// ============================================================
function renderRecentExpenses(records) {
    const tbody = document.getElementById("recent-expenses-body");
    if (!tbody) return;

    if (!records.length) {
        tbody.innerHTML = `<tr><td colspan="6" class="text-center">No expense records available.</td></tr>`;
        return;
    }

    tbody.innerHTML = records.map(record => `
        <tr>
            <td><strong>${escapeHtml(record.product_name || "-")}</strong></td>
            <td>${Number(record.quantity || 0)}</td>
            <td>₹${Number(record.amount || 0).toLocaleString()}</td>
            <td><span class="badge-tag">${escapeHtml(record.expense_month || "-")}</span></td>
            <td><span class="status-badge ok">${escapeHtml(record.status || "Paid")}</span></td>
            <td><small>${escapeHtml(record.remark || "-")}</small></td>
        </tr>
    `).join("");
}

// ============================================================
// KPI MODAL
// ============================================================
async function openKPIModal(kpiType) {
    const modal = document.getElementById("kpi-modal");
    const title = document.getElementById("kpi-modal-title");
    const subtitle = document.getElementById("kpi-modal-subtitle");
    const body = document.getElementById("kpi-modal-body");
    if (!modal || !body) return;

    modal.classList.add("active");
    body.innerHTML = `<div class="loading-state">Loading metric details...</div>`;

    try {
        if (kpiType === "total") {
            title.textContent = "📦 Total Registered Products";
            subtitle.textContent = "All products currently managed in the inventory";
            const response = await fetch("/api/inventory");
            const products = await response.json();

            body.innerHTML = `
                <div class="table-responsive">
                    <table class="styled-table compact">
                        <thead>
                            <tr>
                                <th>Product</th>
                                <th>Category</th>
                                <th>Sub-Category</th>
                                <th>Stock</th>
                                <th>Min Level</th>
                                <th>Price</th>
                                <th>Supplier</th>
                                <th>Status</th>
                            </tr>
                        </thead>
                        <tbody>
                            ${products.map(product => `
                                <tr>
                                    <td><strong>${escapeHtml(product.name || "-")}</strong></td>
                                    <td>${escapeHtml(product.category || "-")}</td>
                                    <td>${escapeHtml(product.sub_category || "-")}</td>
                                    <td>${getStockBadgeHtml(product.stock, product.min_stock)}</td>
                                    <td>${product.min_stock || 0}</td>
                                    <td>₹${Number(product.unit_price || 0).toFixed(2)}</td>
                                    <td>${escapeHtml(product.supplier || "-")}</td>
                                    <td>
                                        <span class="status-badge ${product.is_low_stock ? "low" : "ok"}">
                                            ${product.is_low_stock ? "Low Stock" : "In Stock"}
                                        </span>
                                    </td>
                                </tr>
                            `).join("")}
                        </tbody>
                    </table>
                </div>
            `;
        } else if (kpiType === "low_stock") {
            title.textContent = "⚠️ Low Stock Alert Items";
            subtitle.textContent = "Components requiring immediate procurement attention";
            const response = await fetch("/api/inventory/low-stock");
            const products = await response.json();

            body.innerHTML = products.length === 0
                ? `<div class="conv-item-empty">✅ All products have healthy stock levels!</div>`
                : `
                    <div class="table-responsive">
                        <table class="styled-table compact">
                            <thead>
                                <tr>
                                    <th>Product</th>
                                    <th>Current Stock</th>
                                    <th>Min Threshold</th>
                                    <th>Supplier</th>
                                    <th>Action</th>
                                </tr>
                            </thead>
                            <tbody>
                                ${products.map(product => `
                                    <tr>
                                        <td><strong>${escapeHtml(product.name || "-")}</strong></td>
                                        <td>${getStockBadgeHtml(product.stock, product.min_stock)}</td>
                                        <td>${product.min_stock || 0} units</td>
                                        <td>${escapeHtml(product.supplier || "-")}</td>
                                        <td>
                                            <button class="mini-btn primary" onclick="closeKPIModal(); quickAsk('Reorder 10 ${escapeHtml(product.name || "")}')">
                                                📦 Reorder
                                            </button>
                                        </td>
                                    </tr>
                                `).join("")}
                            </tbody>
                        </table>
                    </div>
                `;
        } else if (kpiType === "units") {
            title.textContent = "🚚 Total Stock Units Distribution";
            subtitle.textContent = "Product unit counts across categories";
            const response = await fetch("/api/dashboard/analytics");
            const data = await response.json();

            body.innerHTML = `
                <div class="table-responsive">
                    <table class="styled-table compact">
                        <thead>
                            <tr>
                                <th>Category</th>
                                <th>Products Count</th>
                                <th>Total Stock Units</th>
                                <th>Total Expense</th>
                            </tr>
                        </thead>
                        <tbody>
                            ${(data.categories || []).map(category => `
                                <tr>
                                    <td><strong>${escapeHtml(category.category || "-")}</strong></td>
                                    <td>${Number(category.count || 0)}</td>
                                    <td>${Number(category.units || 0).toLocaleString()} units</td>
                                    <td>₹${Number(category.expense || 0).toLocaleString()}</td>
                                </tr>
                            `).join("")}
                        </tbody>
                    </table>
                </div>
            `;
        } else if (kpiType === "expenses") {
            title.textContent = "💰 Expense Breakdown by Supplier & Month";
            subtitle.textContent = "Procurement spend across vendors";
            const response = await fetch("/api/dashboard/analytics");
            const data = await response.json();

            body.innerHTML = `
                <div class="table-responsive">
                    <table class="styled-table compact">
                        <thead>
                            <tr>
                                <th>Supplier</th>
                                <th>Products Supplied</th>
                                <th>Total Units</th>
                                <th>Total Spend</th>
                            </tr>
                        </thead>
                        <tbody>
                            ${(data.suppliers || []).map(supplier => `
                                <tr>
                                    <td><strong>${escapeHtml(supplier.supplier || "Unknown")}</strong></td>
                                    <td>${Number(supplier.product_count || 0)} products</td>
                                    <td>${Number(supplier.total_units || 0).toLocaleString()} units</td>
                                    <td><strong>₹${Number(supplier.total_expense || 0).toLocaleString()}</strong></td>
                                </tr>
                            `).join("")}
                        </tbody>
                    </table>
                </div>
            `;
        }
    } catch (error) {
        console.error("Error opening KPI modal:", error);
        body.innerHTML = `<div class="conv-item-empty">Failed to load details.</div>`;
    }
}

// ============================================================
// CLOSE KPI MODAL
// ============================================================
function closeKPIModal() {
    const modal = document.getElementById("kpi-modal");
    if (modal) modal.classList.remove("active");
}

// ============================================================
// MASTER SHEET DOWNLOAD
// ============================================================
async function downloadMasterSheet() {
    try {
        const token = typeof getToken === "function" ? getToken() : localStorage.getItem("access_token");
        const response = await fetch("/api/inventory/master-sheet/download", {
            headers: token ? { "Authorization": `Bearer ${token}` } : {}
        });

        if (!response.ok) {
            alert("Failed to generate master sheet.");
            return;
        }

        const blob = await response.blob();
        const url = window.URL.createObjectURL(blob);
        const anchor = document.createElement("a");
        anchor.href = url;
        anchor.download = `Master_Inventory_Sheet_${new Date().toISOString().slice(0, 10)}.xlsx`;
        document.body.appendChild(anchor);
        anchor.click();
        anchor.remove();
        window.URL.revokeObjectURL(url);
    } catch (error) {
        console.error("Error downloading master sheet:", error);
        alert("Error generating master sheet.");
    }
}