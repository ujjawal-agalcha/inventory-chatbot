// ============================================================
// ANALYTICAL DASHBOARD & MASTER DATA JAVASCRIPT
// ============================================================

let masterInventory = [];
let chartMonthly = null;
let chartCategory = null;
let chartTopExp = null;
let chartSupplier = null;

// ============================================================
// INITIALIZATION & MAIN NAVIGATION
// ============================================================

document.addEventListener("DOMContentLoaded", async () => {
    if (typeof setupDropZones === "function") setupDropZones();
    await loadUser();
    await loadStats();
    await loadCategories();
    if (typeof loadConversations === "function") await loadConversations();
    if (typeof connectWebSocket === "function") connectWebSocket();
});

function switchMainTab(tabId) {
    const views = ["chat", "inventory", "analytics", "upload"];
    views.forEach(v => {
        const viewEl = document.getElementById(`view-${v}`);
        const btnEl = document.getElementById(`tab-btn-${v}`);
        if (viewEl) viewEl.style.display = (v === tabId) ? "block" : "none";
        if (btnEl) {
            if (v === tabId) btnEl.classList.add("active");
            else btnEl.classList.remove("active");
        }
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

async function loadUser() {
    try {
        const token = getToken();
        const res = await fetch("/api/auth/me", {
            headers: token ? { "Authorization": `Bearer ${token}` } : {}
        });
        if (res.ok) {
            const user = await res.json();
            const avatar = document.getElementById("sidebar-avatar");
            const nameEl = document.getElementById("sidebar-name");
            if (avatar && user.name) avatar.textContent = user.name.charAt(0).toUpperCase();
            if (nameEl && user.name) nameEl.textContent = user.name;
        }
    } catch (e) {
        console.warn("Could not fetch user profile:", e);
    }
}

function handleLogout(e) {
    e.preventDefault();
    localStorage.removeItem("access_token");
    localStorage.removeItem("user");
    localStorage.removeItem("active_conversation_id");
    window.location.href = "/logout";
}

// ============================================================
// STATS & CATEGORIES
// ============================================================

async function loadStats() {
    try {
        const res = await fetch("/api/inventory/stats");
        if (res.ok) {
            const stats = await res.json();
            const elTotal = document.getElementById("stat-total");
            const elLow = document.getElementById("stat-low");
            const elUnits = document.getElementById("stat-units");
            const elExp = document.getElementById("stat-expenses");
            const elBadge = document.getElementById("low-stock-badge");

            if (elTotal) elTotal.textContent = stats.total_components;
            if (elLow) elLow.textContent = stats.low_stock;
            if (elUnits) elUnits.textContent = Number(stats.total_units).toLocaleString();
            if (elExp) elExp.textContent = "₹" + Number(stats.total_expenses).toLocaleString(undefined, { maximumFractionDigits: 0 });
            if (elBadge) elBadge.textContent = stats.low_stock;
        }
    } catch (e) {
        console.warn("Could not load stats:", e);
    }
}

async function loadCategories() {
    const grid = document.getElementById("category-grid");
    if (!grid) return;

    try {
        const res = await fetch("/api/dashboard/analytics");
        if (res.ok) {
            const data = await res.json();
            const categories = data.categories || [];

            if (categories.length === 0) {
                grid.innerHTML = `
                    <div class="conv-item-empty">
                        No inventory data yet.<br>Upload Excel files in the <strong>Excel Import Hub</strong> to populate.
                    </div>
                `;
                return;
            }

            const icons = ["📦", "📄", "⚙️", "🖥️", "🔋", "🔌", "📊", "🔀", "🚚", "💡"];
            grid.innerHTML = categories.map((cat, idx) => `
                <div class="category-card" onclick="quickAsk('Show all ${escapeHtml(cat.category)}')">
                    <div class="category-icon">${icons[idx % icons.length]}</div>
                    <div class="category-info">
                        <h4>${escapeHtml(cat.category)}</h4>
                        <p>${cat.count} product(s) · ${cat.units} units · ₹${Number(cat.expense).toLocaleString()}</p>
                    </div>
                </div>
            `).join("");
        }
    } catch (e) {
        console.warn("Could not load dynamic categories:", e);
    }
}

// ============================================================
// DASHBOARD ANALYTICS & CHARTS
// ============================================================

async function refreshDashboardData() {
    try {
        const res = await fetch("/api/dashboard/analytics");
        if (res.ok) {
            const data = await res.json();
            await renderMasterTable();
            renderCharts(data);
            renderRecentProcurements(data.recent_procurements || []);
            renderRecentExpenses(data.recent_expenses || []);
        }
    } catch (e) {
        console.error("Error refreshing dashboard data:", e);
    }
}

function renderCharts(data) {
    if (typeof Chart === "undefined") return;

    // 1. Monthly Expenses Trend
    const ctxMonthly = document.getElementById("chart-monthly-expenses");
    if (ctxMonthly) {
        const monthly = data.monthly_expenses || [];
        const labels = monthly.map(m => m.month);
        const values = monthly.map(m => m.amount);

        if (chartMonthly) chartMonthly.destroy();
        chartMonthly = new Chart(ctxMonthly, {
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
                    pointBackgroundColor: "#4f46e5",
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
    const ctxCategory = document.getElementById("chart-category-breakdown");
    if (ctxCategory) {
        const categories = data.categories || [];
        const labels = categories.map(c => c.category);
        const values = categories.map(c => c.units);

        if (chartCategory) chartCategory.destroy();
        chartCategory = new Chart(ctxCategory, {
            type: "doughnut",
            data: {
                labels: labels.length ? labels : ["No Data"],
                datasets: [{
                    data: values.length ? values : [1],
                    backgroundColor: ["#4f46e5", "#3b82f6", "#10b981", "#f59e0b", "#8b5cf6", "#ec4899", "#06b6d4", "#64748b"],
                    borderWidth: 2,
                    borderColor: "#fff",
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: { legend: { position: "right" } }
            }
        });
    }

    // 3. Top Expense Products
    const ctxTopExp = document.getElementById("chart-top-expenses");
    if (ctxTopExp) {
        const topExp = data.top_expenses || [];
        const labels = topExp.map(p => p.name);
        const values = topExp.map(p => p.total_expense);

        if (chartTopExp) chartTopExp.destroy();
        chartTopExp = new Chart(ctxTopExp, {
            type: "bar",
            data: {
                labels: labels.length ? labels : ["No Data"],
                datasets: [{
                    label: "Total Expense (₹)",
                    data: values.length ? values : [0],
                    backgroundColor: "#8b5cf6",
                    borderRadius: 6,
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
    const ctxSupplier = document.getElementById("chart-supplier-distribution");
    if (ctxSupplier) {
        const suppliers = data.suppliers || [];
        const labels = suppliers.map(s => s.supplier);
        const values = suppliers.map(s => s.expense);

        if (chartSupplier) chartSupplier.destroy();
        chartSupplier = new Chart(ctxSupplier, {
            type: "pie",
            data: {
                labels: labels.length ? labels : ["No Data"],
                datasets: [{
                    data: values.length ? values : [1],
                    backgroundColor: ["#10b981", "#3b82f6", "#f59e0b", "#ec4899", "#4f46e5", "#06b6d4"],
                    borderWidth: 2,
                    borderColor: "#fff",
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: { legend: { position: "right" } }
            }
        });
    }
}

function toggleAllCharts() {
    const container = document.getElementById("analytics-charts-container");
    const btn = document.getElementById("btn-toggle-all-charts");
    if (!container) return;

    if (container.style.display === "none") {
        container.style.display = "grid";
        if (btn) btn.classList.add("active");
    } else {
        container.style.display = "none";
        if (btn) btn.classList.remove("active");
    }
}

// ============================================================
// MASTER INVENTORY TABLE & TRANSACTIONS
// ============================================================

async function renderMasterTable() {
    const tbody = document.getElementById("master-table-body");
    const catSelect = document.getElementById("inventory-category-filter");
    if (!tbody) return;

    try {
        const res = await fetch("/api/inventory");
        if (res.ok) {
            masterInventory = await res.json();

            if (catSelect) {
                const uniqueCats = Array.from(new Set(masterInventory.map(i => i.category).filter(Boolean)));
                const currentVal = catSelect.value;
                catSelect.innerHTML = `<option value="">All Categories</option>` + uniqueCats.map(c =>
                    `<option value="${escapeHtml(c)}" ${c === currentVal ? 'selected' : ''}>${escapeHtml(c)}</option>`
                ).join("");
            }

            filterMasterTable();
        }
    } catch (e) {
        console.error("Error loading master inventory table:", e);
    }
}

function filterMasterTable() {
    const tbody = document.getElementById("master-table-body");
    if (!tbody) return;

    const query = (document.getElementById("inventory-table-search")?.value || "").toLowerCase().trim();
    const selectedCat = document.getElementById("inventory-category-filter")?.value || "";

    const filtered = masterInventory.filter(item => {
        const matchesQuery = !query ||
            (item.name && item.name.toLowerCase().includes(query)) ||
            (item.category && item.category.toLowerCase().includes(query)) ||
            (item.sub_category && item.sub_category.toLowerCase().includes(query)) ||
            (item.supplier && item.supplier.toLowerCase().includes(query)) ||
            (item.details && item.details.toLowerCase().includes(query));

        const matchesCat = !selectedCat || (item.category === selectedCat);
        return matchesQuery && matchesCat;
    });

    if (filtered.length === 0) {
        tbody.innerHTML = `<tr><td colspan="10" class="text-center">No matching inventory items found.</td></tr>`;
        return;
    }

    tbody.innerHTML = filtered.map(item => {
        const stockBadge = (typeof getStockBadgeHtml === "function")
            ? getStockBadgeHtml(item.stock, item.min_stock)
            : `<span>${item.stock} units</span>`;

        return `
            <tr>
                <td>
                    <strong>${escapeHtml(item.name)}</strong>
                    ${item.details ? `<br><small class="text-muted">${escapeHtml(item.details)}</small>` : ''}
                </td>
                <td><span class="badge-tag">${escapeHtml(item.category)}</span></td>
                <td><span class="badge-tag" style="background:#f1f5f9; color:#475569;">${escapeHtml(item.sub_category || '-')}</span></td>
                <td>${stockBadge}</td>
                <td>${item.min_stock} units</td>
                <td>₹${Number(item.unit_price).toFixed(2)}</td>
                <td>₹${Number(item.total_expense || 0).toLocaleString()}</td>
                <td>${escapeHtml(item.supplier || 'Standard Vendor')}</td>
                <td>
                    <span class="status-badge ${item.is_low_stock ? 'low' : 'ok'}">
                        ${item.is_low_stock ? '⚠️ Low Stock' : '✓ In Stock'}
                    </span>
                </td>
                <td>
                    <button class="edit-icon-btn" onclick="openEditModal('${item.id}')" title="Edit item">✏️ Edit</button>
                </td>
            </tr>
        `;
    }).join("");
}

function renderRecentProcurements(records) {
    const tbody = document.getElementById("recent-procurements-body");
    if (!tbody) return;

    if (records.length === 0) {
        tbody.innerHTML = `<tr><td colspan="6" class="text-center">No procurement records available.</td></tr>`;
        return;
    }

    tbody.innerHTML = records.map(r => `
        <tr>
            <td><strong>${escapeHtml(r.product_name)}</strong></td>
            <td>${r.quantity}</td>
            <td>₹${Number(r.unit_price).toFixed(2)}</td>
            <td><span class="status-badge ${r.order_status?.toLowerCase() === 'fulfilled' ? 'ok' : 'low'}">${escapeHtml(r.order_status || 'Pending')}</span></td>
            <td>${escapeHtml(r.vendor_name || 'Vendor')}</td>
            <td>${escapeHtml(r.approved_by || '-')}</td>
        </tr>
    `).join("");
}

function renderRecentExpenses(records) {
    const tbody = document.getElementById("recent-expenses-body");
    if (!tbody) return;

    if (records.length === 0) {
        tbody.innerHTML = `<tr><td colspan="6" class="text-center">No expense records available.</td></tr>`;
        return;
    }

    tbody.innerHTML = records.map(e => `
        <tr>
            <td><strong>${escapeHtml(e.product_name)}</strong></td>
            <td>${e.quantity}</td>
            <td>₹${Number(e.amount).toLocaleString()}</td>
            <td><span class="badge-tag">${escapeHtml(e.expense_month || '-')}</span></td>
            <td><span class="status-badge ok">${escapeHtml(e.status || 'Paid')}</span></td>
            <td><small>${escapeHtml(e.remark || '-')}</small></td>
        </tr>
    `).join("");
}

// ============================================================
// KPI DRILL-DOWN MODAL
// ============================================================

async function openKPIModal(kpiType) {
    const modal = document.getElementById("kpi-modal");
    const titleEl = document.getElementById("kpi-modal-title");
    const subtitleEl = document.getElementById("kpi-modal-subtitle");
    const bodyEl = document.getElementById("kpi-modal-body");

    if (!modal || !bodyEl) return;

    modal.classList.add("active");
    bodyEl.innerHTML = `<div class="loading-state">Loading metric details...</div>`;

    try {
        if (kpiType === "total") {
            titleEl.textContent = "📦 Total Registered Products";
            subtitleEl.textContent = "All products currently managed in the inventory";
            const res = await fetch("/api/inventory");
            const prods = await res.json();
            bodyEl.innerHTML = `
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
                            ${prods.map(p => `
                                <tr>
                                    <td><strong>${escapeHtml(p.name)}</strong></td>
                                    <td>${escapeHtml(p.category)}</td>
                                    <td>${escapeHtml(p.sub_category || '-')}</td>
                                    <td>${getStockBadgeHtml(p.stock, p.min_stock)}</td>
                                    <td>${p.min_stock}</td>
                                    <td>₹${Number(p.unit_price).toFixed(2)}</td>
                                    <td>${escapeHtml(p.supplier)}</td>
                                    <td><span class="status-badge ${p.is_low_stock ? 'low' : 'ok'}">${p.is_low_stock ? 'Low Stock' : 'In Stock'}</span></td>
                                </tr>
                            `).join("")}
                        </tbody>
                    </table>
                </div>
            `;
        } else if (kpiType === "low_stock") {
            titleEl.textContent = "⚠️ Low Stock Alert Items";
            subtitleEl.textContent = "Components requiring immediate procurement attention";
            const res = await fetch("/api/inventory/low-stock");
            const lowProds = await res.json();
            bodyEl.innerHTML = lowProds.length === 0 ? `<div class="conv-item-empty">✅ All products have healthy stock levels!</div>` : `
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
                            ${lowProds.map(p => `
                                <tr>
                                    <td><strong>${escapeHtml(p.name)}</strong></td>
                                    <td>${getStockBadgeHtml(p.stock, p.min_stock)}</td>
                                    <td>${p.min_stock} units</td>
                                    <td>${escapeHtml(p.supplier)}</td>
                                    <td><button class="mini-btn primary" onclick="closeKPIModal(); quickAsk('Reorder 10 ${escapeHtml(p.name)}')">📦 Reorder</button></td>
                                </tr>
                            `).join("")}
                        </tbody>
                    </table>
                </div>
            `;
        } else if (kpiType === "units") {
            titleEl.textContent = "🚚 Total Stock Units Distribution";
            subtitleEl.textContent = "Product unit counts across categories";
            const res = await fetch("/api/dashboard/analytics");
            const data = await res.json();
            bodyEl.innerHTML = `
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
                            ${(data.categories || []).map(c => `
                                <tr>
                                    <td><strong>${escapeHtml(c.category)}</strong></td>
                                    <td>${c.count}</td>
                                    <td>${c.units} units</td>
                                    <td>₹${Number(c.expense).toLocaleString()}</td>
                                </tr>
                            `).join("")}
                        </tbody>
                    </table>
                </div>
            `;
        } else if (kpiType === "expenses") {
            titleEl.textContent = "💰 Expense Breakdown by Supplier & Month";
            subtitleEl.textContent = "Procurement spend across vendors";
            const res = await fetch("/api/dashboard/analytics");
            const data = await res.json();
            bodyEl.innerHTML = `
                <div class="table-responsive">
                    <table class="styled-table compact">
                        <thead>
                            <tr>
                                <th>Supplier</th>
                                <th>Products Supplied</th>
                                <th>Total Spend</th>
                            </tr>
                        </thead>
                        <tbody>
                            ${(data.suppliers || []).map(s => `
                                <tr>
                                    <td><strong>${escapeHtml(s.supplier)}</strong></td>
                                    <td>${s.count} items (${s.units} units)</td>
                                    <td><strong>₹${Number(s.expense).toLocaleString()}</strong></td>
                                </tr>
                            `).join("")}
                        </tbody>
                    </table>
                </div>
            `;
        }
    } catch (e) {
        console.error("Error opening KPI modal:", e);
        bodyEl.innerHTML = `<div class="conv-item-empty">Failed to load details.</div>`;
    }
}

function closeKPIModal() {
    const modal = document.getElementById("kpi-modal");
    if (modal) modal.classList.remove("active");
}

// ============================================================
// MASTER SHEET EXCEL EXPORT
// ============================================================

async function downloadMasterSheet() {
    const token = getToken();
    try {
        const res = await fetch("/api/inventory/master-sheet/download", {
            headers: token ? { "Authorization": `Bearer ${token}` } : {}
        });
        if (!res.ok) {
            alert("Failed to generate master sheet.");
            return;
        }
        const blob = await res.blob();
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement("a");
        a.href = url;
        a.download = `Master_Inventory_Sheet_${new Date().toISOString().slice(0, 10)}.xlsx`;
        document.body.appendChild(a);
        a.click();
        a.remove();
        window.URL.revokeObjectURL(url);
    } catch (e) {
        console.error("Error downloading master sheet:", e);
        alert("Error generating master sheet.");
    }
}
