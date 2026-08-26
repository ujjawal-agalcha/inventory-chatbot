// ============================================================
// INVENTORY INTELLIGENCE & AI ASSISTANT - PRODUCTION JAVASCRIPT
// ============================================================

// Global State
let activeConversationId = localStorage.getItem("active_conversation_id") || null;
let conversations = [];
let masterInventory = [];
let chatSocket = null;
let reconnectTimer = null;
let pingInterval = null;
let isGenerating = false;
let currentStreamingBubble = null;
let currentStreamingText = "";

// Chart instances
let chartMonthly = null;
let chartCategory = null;
let chartTopExp = null;
let chartSupplier = null;

// ============================================================
// INITIALIZATION
// ============================================================

document.addEventListener("DOMContentLoaded", async () => {
    setupDropZones();
    await loadUser();
    await loadStats();
    await loadCategories();
    await loadConversations();
    connectWebSocket();
});

// ============================================================
// NAVIGATION TABS
// ============================================================

function switchMainTab(tabId) {
    const views = ["chat", "analytics", "upload"];
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
        if (pageSubtitle) pageSubtitle.textContent = "Real-time MongoDB stock monitoring, Excel ingestion & AI assistant";
    } else if (tabId === "analytics") {
        if (pageTitle) pageTitle.textContent = "Real-Time Analytical Dashboard";
        if (pageSubtitle) pageSubtitle.textContent = "Interactive spending trends, category breakdown & master inventory table";
        refreshDashboardData();
    } else if (tabId === "upload") {
        if (pageTitle) pageTitle.textContent = "Excel Ingestion & Integration Hub";
        if (pageSubtitle) pageSubtitle.textContent = "Upload procurement & monthly expense workbooks with duplicate prevention";
        loadImportHistory();
    }
}

// ============================================================
// AUTH & USER
// ============================================================

function getToken() {
    return localStorage.getItem("access_token") || getCookie("access_token");
}

function getCookie(name) {
    const value = `; ${document.cookie}`;
    const parts = value.split(`; ${name}=`);
    if (parts.length === 2) return parts.pop().split(';').shift();
    return null;
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
// DASHBOARD STATS & DYNAMIC CATEGORIES
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
// REAL-TIME ANALYTICS DASHBOARD & CHARTS
// ============================================================

async function refreshDashboardData() {
    try {
        const res = await fetch("/api/dashboard/analytics");
        if (!res.ok) return;

        const data = await res.json();
        renderCharts(data);
        renderMasterTable();
        renderRecentTransactions(data);
    } catch (e) {
        console.error("Error refreshing dashboard data:", e);
    }
}

function renderCharts(data) {
    // 1. Monthly Expenses
    const ctxMonthly = document.getElementById("chart-monthly-expenses");
    if (ctxMonthly) {
        const months = data.monthly_expenses || [];
        if (chartMonthly) chartMonthly.destroy();
        chartMonthly = new Chart(ctxMonthly, {
            type: "bar",
            data: {
                labels: months.map(m => m.month),
                datasets: [{
                    label: "Monthly Spend (₹)",
                    data: months.map(m => m.amount),
                    backgroundColor: "rgba(79, 70, 229, 0.8)",
                    borderColor: "rgba(79, 70, 229, 1)",
                    borderWidth: 1,
                    borderRadius: 6,
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: { legend: { display: false } },
                scales: {
                    y: { beginAtZero: true, ticks: { callback: v => "₹" + Number(v).toLocaleString() } }
                }
            }
        });
    }

    // 2. Category Breakdown
    const ctxCat = document.getElementById("chart-category-breakdown");
    if (ctxCat) {
        const cats = data.categories || [];
        if (chartCategory) chartCategory.destroy();
        chartCategory = new Chart(ctxCat, {
            type: "doughnut",
            data: {
                labels: cats.map(c => c.category),
                datasets: [{
                    data: cats.map(c => c.units),
                    backgroundColor: [
                        "#4f46e5", "#06b6d4", "#10b981", "#f59e0b",
                        "#ef4444", "#8b5cf6", "#ec4899", "#64748b"
                    ],
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: { legend: { position: "right", labels: { boxWidth: 12, font: { size: 11 } } } }
            }
        });
    }

    // 3. Top Expense Items
    const ctxTopExp = document.getElementById("chart-top-expenses");
    if (ctxTopExp) {
        const topExp = data.top_expenses || [];
        if (chartTopExp) chartTopExp.destroy();
        chartTopExp = new Chart(ctxTopExp, {
            type: "bar",
            data: {
                labels: topExp.map(p => p.name),
                datasets: [{
                    label: "Total Expense (₹)",
                    data: topExp.map(p => p.total_expense),
                    backgroundColor: "rgba(139, 92, 246, 0.8)",
                    borderRadius: 6,
                }]
            },
            options: {
                indexAxis: "y",
                responsive: true,
                maintainAspectRatio: false,
                plugins: { legend: { display: false } },
                scales: {
                    x: { beginAtZero: true, ticks: { callback: v => "₹" + Number(v).toLocaleString() } }
                }
            }
        });
    }

    // 4. Supplier Distribution
    const ctxSup = document.getElementById("chart-supplier-distribution");
    if (ctxSup) {
        const sups = data.suppliers || [];
        if (chartSupplier) chartSupplier.destroy();
        chartSupplier = new Chart(ctxSup, {
            type: "pie",
            data: {
                labels: sups.map(s => s.supplier),
                datasets: [{
                    data: sups.map(s => s.expense || s.count),
                    backgroundColor: [
                        "#10b981", "#3b82f6", "#f59e0b", "#8b5cf6", "#ec4899", "#14b8a6"
                    ],
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: { legend: { position: "right", labels: { boxWidth: 12, font: { size: 11 } } } }
            }
        });
    }
}

async function renderMasterTable() {
    const tbody = document.getElementById("master-table-body");
    const catSelect = document.getElementById("inventory-category-filter");
    if (!tbody) return;

    try {
        const res = await fetch("/api/inventory");
        if (res.ok) {
            masterInventory = await res.json();

            // Populate category filter dropdown
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
        console.error("Error rendering master table:", e);
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
            (item.supplier && item.supplier.toLowerCase().includes(query)) ||
            (item.details && item.details.toLowerCase().includes(query));

        const matchesCat = !selectedCat || (item.category === selectedCat);
        return matchesQuery && matchesCat;
    });

    if (filtered.length === 0) {
        tbody.innerHTML = `<tr><td colspan="9" class="text-center">No inventory records found.</td></tr>`;
        return;
    }

    tbody.innerHTML = filtered.map(item => `
        <tr>
            <td>
                <strong>${escapeHtml(item.name)}</strong>
                ${item.details ? `<br><small class="text-muted">${escapeHtml(item.details)}</small>` : ''}
            </td>
            <td><span class="badge-tag">${escapeHtml(item.category)}</span></td>
            <td><strong>${item.stock}</strong> units</td>
            <td>${item.min_stock} units</td>
            <td>₹${Number(item.unit_price).toFixed(2)}</td>
            <td>₹${Number(item.total_expense || 0).toLocaleString()}</td>
            <td>${escapeHtml(item.supplier || 'N/A')}</td>
            <td>
                <span class="status-badge ${item.is_low_stock ? 'low' : 'ok'}">
                    ${item.is_low_stock ? '⚠️ Low Stock' : '✓ In Stock'}
                </span>
            </td>
            <td>
                <button class="mini-btn primary" onclick="quickReorderPrompt('${escapeHtml(item.name)}')">Reorder</button>
            </td>
        </tr>
    `).join("");
}

function renderRecentTransactions(data) {
    const procBody = document.getElementById("recent-procurements-body");
    if (procBody) {
        const procs = data.recent_procurements || [];
        if (procs.length === 0) {
            procBody.innerHTML = `<tr><td colspan="6" class="text-center">No procurement records found.</td></tr>`;
        } else {
            procBody.innerHTML = procs.map(p => `
                <tr>
                    <td>${escapeHtml(p.product_name)}</td>
                    <td>${p.quantity}</td>
                    <td>₹${Number(p.amount).toFixed(0)}</td>
                    <td><span class="status-badge ${p.order_status.toLowerCase() === 'fulfilled' ? 'ok' : 'pending'}">${escapeHtml(p.order_status)}</span></td>
                    <td>${escapeHtml(p.vendor_name)}</td>
                    <td>${escapeHtml(p.approved_by || 'Admin')}</td>
                </tr>
            `).join("");
        }
    }

    const expBody = document.getElementById("recent-expenses-body");
    if (expBody) {
        const exps = data.recent_expenses || [];
        if (exps.length === 0) {
            expBody.innerHTML = `<tr><td colspan="6" class="text-center">No expense records found.</td></tr>`;
        } else {
            expBody.innerHTML = exps.map(e => `
                <tr>
                    <td>${escapeHtml(e.product_name)}</td>
                    <td>${e.quantity}</td>
                    <td>₹${Number(e.amount).toFixed(0)}</td>
                    <td>${escapeHtml(e.expense_month)}</td>
                    <td><span class="status-badge ok">${escapeHtml(e.status)}</span></td>
                    <td><small>${escapeHtml(e.remark || '-')}</small></td>
                </tr>
            `).join("");
        }
    }
}

function quickReorderPrompt(itemName) {
    switchMainTab("chat");
    quickAsk(`Reorder 10 units of ${itemName}`);
}

// ============================================================
// EXCEL IMPORT & UPLOAD HUB
// ============================================================

let selectedFiles = {
    procurement: null,
    expenses: null,
};

function setupDropZones() {
    ["procurement", "expenses"].forEach(type => {
        const zone = document.getElementById(`drop-zone-${type}`);
        if (!zone) return;

        zone.addEventListener("dragover", (e) => {
            e.preventDefault();
            zone.classList.add("drag-over");
        });

        zone.addEventListener("dragleave", () => {
            zone.classList.remove("drag-over");
        });

        zone.addEventListener("drop", (e) => {
            e.preventDefault();
            zone.classList.remove("drag-over");
            if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
                const file = e.dataTransfer.files[0];
                if (file.name.endsWith(".xlsx") || file.name.endsWith(".xls")) {
                    selectedFiles[type] = file;
                    updateFileDisplay(type, file.name);
                } else {
                    alert("Please select an Excel (.xlsx or .xls) workbook.");
                }
            }
        });
    });
}

function handleFileSelected(type) {
    const input = document.getElementById(`file-input-${type}`);
    if (input && input.files && input.files[0]) {
        const file = input.files[0];
        selectedFiles[type] = file;
        updateFileDisplay(type, file.name);
    }
}

function updateFileDisplay(type, name) {
    const display = document.getElementById(`file-name-${type}`);
    const btn = document.getElementById(`btn-upload-${type}`);
    if (display) display.textContent = `Selected: ${name}`;
    if (btn) btn.disabled = false;
}

async function uploadExcel(type) {
    const file = selectedFiles[type];
    if (!file) return;

    const btn = document.getElementById(`btn-upload-${type}`);
    const feedback = document.getElementById(`feedback-${type}`);
    const originalText = btn ? btn.textContent : "Upload";

    if (btn) {
        btn.disabled = true;
        btn.textContent = "Processing & Ingesting into MongoDB...";
    }

    if (feedback) {
        feedback.style.display = "block";
        feedback.className = "upload-feedback loading";
        feedback.textContent = "Reading sheets, normalizing data, detecting duplicates, and updating master inventory...";
    }

    const formData = new FormData();
    formData.append("file", file);

    try {
        const endpoint = type === "procurement" ? "/api/upload/procurement" : "/api/upload/expenses";
        const res = await fetch(endpoint, {
            method: "POST",
            body: formData,
        });

        const result = await res.json();

        if (res.ok && result.success) {
            const data = result.data || {};
            if (feedback) {
                feedback.className = "upload-feedback success";
                feedback.innerHTML = `
                    <strong>✅ Import Successful!</strong><br>
                    • Total Rows: ${data.total_rows || 0}<br>
                    • Valid Records: ${data.valid_records || 0}<br>
                    • New Master Products: ${data.new_records || 0}<br>
                    • Updated Master Products: ${data.updated_records || 0}<br>
                    • Duplicates Prevented: ${data.duplicate_records || 0}
                `;
            }

            // Update metrics card
            const summaryCard = document.getElementById("import-stats-summary");
            if (summaryCard) summaryCard.style.display = "block";
            document.getElementById("metric-total-rows").textContent = data.total_rows || 0;
            document.getElementById("metric-valid-rows").textContent = data.valid_records || 0;
            document.getElementById("metric-new-prods").textContent = data.new_records || 0;
            document.getElementById("metric-updated-prods").textContent = data.updated_records || 0;
            document.getElementById("metric-dup-rows").textContent = data.duplicate_records || 0;

            // Refresh live stats & categories
            await loadStats();
            await loadCategories();
            await loadImportHistory();
        } else {
            if (feedback) {
                feedback.className = "upload-feedback error";
                feedback.textContent = `❌ Import Failed: ${result.detail || result.message || "Unknown error occurred."}`;
            }
        }
    } catch (e) {
        console.error("Upload error:", e);
        if (feedback) {
            feedback.className = "upload-feedback error";
            feedback.textContent = `❌ Network/Server Error: ${e.message}`;
        }
    } finally {
        if (btn) {
            btn.disabled = false;
            btn.textContent = originalText;
        }
    }
}

async function loadImportHistory() {
    const tbody = document.getElementById("import-history-body");
    if (!tbody) return;

    try {
        const res = await fetch("/api/imports");
        if (res.ok) {
            const imports = await res.json();
            if (imports.length === 0) {
                tbody.innerHTML = `<tr><td colspan="9" class="text-center">No import history yet. Upload an Excel workbook above!</td></tr>`;
                return;
            }

            tbody.innerHTML = imports.map(imp => `
                <tr>
                    <td><small>${new Date(imp.upload_timestamp).toLocaleString()}</small></td>
                    <td><strong>${escapeHtml(imp.filename)}</strong></td>
                    <td><span class="badge-tag">${escapeHtml(imp.file_type)}</span></td>
                    <td>${imp.total_rows}</td>
                    <td>${imp.valid_records}</td>
                    <td>${imp.new_records}</td>
                    <td>${imp.updated_records}</td>
                    <td>${imp.duplicate_records}</td>
                    <td><span class="status-badge ${imp.status === 'completed' ? 'ok' : 'low'}">${escapeHtml(imp.status)}</span></td>
                </tr>
            `).join("");
        }
    } catch (e) {
        console.warn("Could not load import history:", e);
    }
}

// ============================================================
// WEBSOCKET CHAT CONNECTION
// ============================================================

function updateStatus(state, text) {
    const statusEl = document.getElementById("ws-status");
    if (!statusEl) return;
    statusEl.className = `ws-status ${state}`;
    const textEl = statusEl.querySelector(".status-text");
    if (textEl) textEl.textContent = text;
}

function connectWebSocket() {
    if (chatSocket && (chatSocket.readyState === WebSocket.OPEN || chatSocket.readyState === WebSocket.CONNECTING)) {
        return;
    }

    const token = getToken();
    const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
    let wsUrl = `${protocol}//${window.location.host}/ws/chat`;
    if (token) {
        wsUrl += `?token=${encodeURIComponent(token)}`;
    }

    updateStatus("connecting", "Connecting...");

    try {
        chatSocket = new WebSocket(wsUrl);

        chatSocket.onopen = () => {
            console.log("[WS] Connected to real-time AI assistant");
            updateStatus("connected", "Live Connected");
            if (reconnectTimer) {
                clearTimeout(reconnectTimer);
                reconnectTimer = null;
            }

            if (pingInterval) clearInterval(pingInterval);
            pingInterval = setInterval(() => {
                if (chatSocket && chatSocket.readyState === WebSocket.OPEN) {
                    chatSocket.send(JSON.stringify({ type: "ping" }));
                }
            }, 25000);

            if (activeConversationId) {
                chatSocket.send(JSON.stringify({
                    type: "init",
                    conversation_id: activeConversationId
                }));
            }
        };

        chatSocket.onmessage = (event) => {
            handleWebSocketMessage(event.data);
        };

        chatSocket.onclose = (event) => {
            console.warn("[WS] Closed:", event.code, event.reason);
            updateStatus("disconnected", "Offline (Reconnecting...)");
            if (pingInterval) clearInterval(pingInterval);

            if (!reconnectTimer) {
                reconnectTimer = setTimeout(() => {
                    reconnectTimer = null;
                    connectWebSocket();
                }, 3000);
            }
        };

        chatSocket.onerror = (err) => {
            console.error("[WS Error]:", err);
            updateStatus("disconnected", "Connection Error");
        };

    } catch (e) {
        console.error("Failed to initialize WebSocket:", e);
        updateStatus("disconnected", "Offline");
    }
}

// ============================================================
// WEBSOCKET MESSAGE HANDLER (TOKEN STREAMING)
// ============================================================

function handleWebSocketMessage(raw) {
    try {
        const data = JSON.parse(raw);

        switch (data.type) {
            case "pong":
                break;

            case "conversation_created":
                if (data.conversation) {
                    activeConversationId = data.conversation.id;
                    localStorage.setItem("active_conversation_id", activeConversationId);
                    loadConversations();
                }
                break;

            case "message_start":
                isGenerating = true;
                currentStreamingText = "";
                currentStreamingBubble = createStreamingBubble();
                break;

            case "token":
                if (!currentStreamingBubble) {
                    currentStreamingBubble = createStreamingBubble();
                }
                currentStreamingText += (data.content || "");
                renderStreamingContent(currentStreamingBubble, currentStreamingText);
                scrollToBottom();
                break;

            case "message_end":
                isGenerating = false;
                const finalMsg = data.message || currentStreamingText;
                if (currentStreamingBubble) {
                    finalizeStreamingBubble(currentStreamingBubble, finalMsg, data.data, data.data_type);
                }
                currentStreamingBubble = null;
                currentStreamingText = "";
                scrollToBottom();
                loadStats();
                break;

            case "error":
                isGenerating = false;
                if (currentStreamingBubble) {
                    currentStreamingBubble.remove();
                    currentStreamingBubble = null;
                }
                addErrorMessage(data.message || "An unexpected error occurred.");
                scrollToBottom();
                break;

            default:
                console.log("[WS Event]", data);
        }
    } catch (e) {
        console.error("Error parsing WebSocket message:", e, raw);
    }
}

// ============================================================
// UI MESSAGE RENDERING
// ============================================================

function scrollToBottom() {
    const conv = document.getElementById("conversation");
    if (conv) conv.scrollTop = conv.scrollHeight;
}

function escapeHtml(value) {
    if (value === null || value === undefined) return "";
    const div = document.createElement("div");
    div.textContent = String(value);
    return div.innerHTML;
}

function parseMarkdown(text) {
    if (!text) return "";
    let html = escapeHtml(text);

    // Bold: **text**
    html = html.replace(/\*\*(.*?)\*\*/g, "<strong>$1</strong>");

    // Italic: *text* or _text_
    html = html.replace(/\*(.*?)\*/g, "<em>$1</em>");

    // Bullet points: lines starting with "- " or "* "
    html = html.replace(/(?:^|\n)[-*]\s+(.+)/g, "<br>• $1");

    // Line breaks
    html = html.replace(/\n/g, "<br>");

    return html;
}

function addUserMessage(message) {
    const conv = document.getElementById("conversation");
    if (!conv) return;

    const div = document.createElement("div");
    div.className = "user-message";
    div.textContent = message;
    conv.appendChild(div);
    scrollToBottom();
}

function createStreamingBubble() {
    const conv = document.getElementById("conversation");
    if (!conv) return null;

    const div = document.createElement("div");
    div.className = "bot-message streaming";
    div.innerHTML = `<span class="bot-text"></span><span class="cursor-dot">●</span>`;
    conv.appendChild(div);
    scrollToBottom();
    return div;
}

function renderStreamingContent(bubble, text) {
    const textSpan = bubble.querySelector(".bot-text");
    if (textSpan) {
        textSpan.innerHTML = parseMarkdown(text);
    }
}

function finalizeStreamingBubble(bubble, text, structuredData, dataType) {
    bubble.classList.remove("streaming");
    const cursor = bubble.querySelector(".cursor-dot");
    if (cursor) cursor.remove();

    const textSpan = bubble.querySelector(".bot-text");
    if (textSpan) {
        textSpan.innerHTML = parseMarkdown(text);
    } else {
        bubble.innerHTML = parseMarkdown(text);
    }

    // Render structured component card if present
    if (structuredData) {
        if (Array.isArray(structuredData) && structuredData.length > 0) {
            const card = document.createElement("div");
            card.className = "structured-card";
            card.innerHTML = structuredData.slice(0, 8).map(item => `
                <div class="component-pill ${item.is_low_stock ? 'low-stock' : ''}">
                    <span class="name">${escapeHtml(item.name)}</span>
                    <span class="stock">${item.stock} in stock (min: ${item.min_stock})</span>
                    <span class="supplier">${escapeHtml(item.supplier)}</span>
                </div>
            `).join("");
            bubble.appendChild(card);
        } else if (typeof structuredData === "object" && structuredData.name) {
            const item = structuredData;
            const card = document.createElement("div");
            card.className = "component-card-detail";
            card.innerHTML = `
                <div class="detail-header">
                    <h4>${escapeHtml(item.name)}</h4>
                    <span class="status-badge ${item.is_low_stock ? 'low' : 'ok'}">${item.is_low_stock ? '⚠️ Low Stock' : '✓ In Stock'}</span>
                </div>
                <div class="detail-grid">
                    <div><span>Current Stock:</span> <strong>${item.stock} units</strong></div>
                    <div><span>Min Level:</span> <strong>${item.min_stock} units</strong></div>
                    <div><span>Unit Price:</span> <strong>₹${Number(item.unit_price || 0).toFixed(2)}</strong></div>
                    <div><span>Supplier:</span> <strong>${escapeHtml(item.supplier)}</strong></div>
                </div>
                <div class="detail-actions">
                    <button class="mini-btn primary" onclick="quickAsk('Reorder 10 units of ${escapeHtml(item.name)}')">📦 Reorder</button>
                    <button class="mini-btn" onclick="quickAsk('Who supplies ${escapeHtml(item.name)}?')">🚚 Vendor Info</button>
                    <button class="mini-btn" onclick="quickAsk('How much did we spend on ${escapeHtml(item.name)}?')">💰 Spending</button>
                </div>
            `;
            bubble.appendChild(card);
        }
    }
}

function addErrorMessage(message) {
    const conv = document.getElementById("conversation");
    if (!conv) return;

    const div = document.createElement("div");
    div.className = "bot-message error-msg";
    div.innerHTML = `<strong>Error:</strong> ${escapeHtml(message)}`;
    conv.appendChild(div);
}

// ============================================================
// SEND MESSAGE (WEBSOCKET)
// ============================================================

async function sendMessage() {
    const input = document.getElementById("message-input");
    if (!input) return;

    const text = input.value.trim();
    if (!text || isGenerating) return;

    input.value = "";
    addUserMessage(text);

    if (!chatSocket || chatSocket.readyState !== WebSocket.OPEN) {
        connectWebSocket();
        await new Promise(r => setTimeout(r, 600));
    }

    if (!chatSocket || chatSocket.readyState !== WebSocket.OPEN) {
        addErrorMessage("Unable to connect to WebSocket server. Please check connection.");
        return;
    }

    chatSocket.send(JSON.stringify({
        type: "message",
        content: text,
        conversation_id: activeConversationId
    }));
}

function quickAsk(promptText) {
    switchMainTab("chat");
    const input = document.getElementById("message-input");
    if (input) {
        input.value = promptText;
        sendMessage();
    }
}

// ============================================================
// CONVERSATIONS MANAGEMENT (SIDEBAR)
// ============================================================

async function loadConversations() {
    const listEl = document.getElementById("conversation-list");
    if (!listEl) return;

    try {
        const token = getToken();
        const res = await fetch("/api/conversations", {
            headers: token ? { "Authorization": `Bearer ${token}` } : {}
        });

        if (!res.ok) {
            listEl.innerHTML = `<div class="conv-item-loading">Sign in to view chats</div>`;
            return;
        }

        conversations = await res.json();

        if (conversations.length === 0) {
            listEl.innerHTML = `<div class="conv-item-empty">No conversations yet.<br>Click <strong>+ New Chat</strong> to start!</div>`;
            return;
        }

        if (!activeConversationId && conversations.length > 0) {
            activeConversationId = conversations[0].id;
            localStorage.setItem("active_conversation_id", activeConversationId);
        }

        renderConversationList();

        if (activeConversationId) {
            loadConversationMessages(activeConversationId);
        }

    } catch (e) {
        console.error("Error loading conversations:", e);
        listEl.innerHTML = `<div class="conv-item-loading">Could not load chats.</div>`;
    }
}

function renderConversationList() {
    const listEl = document.getElementById("conversation-list");
    if (!listEl) return;

    listEl.innerHTML = conversations.map(c => `
        <div class="conv-item ${c.id === activeConversationId ? 'active' : ''}" onclick="selectConversation('${c.id}')">
            <span class="conv-icon">💬</span>
            <span class="conv-title">${escapeHtml(c.title || 'New Conversation')}</span>
        </div>
    `).join("");
}

async function selectConversation(id) {
    if (id === activeConversationId) return;
    activeConversationId = id;
    localStorage.setItem("active_conversation_id", id);
    renderConversationList();
    await loadConversationMessages(id);

    if (chatSocket && chatSocket.readyState === WebSocket.OPEN) {
        chatSocket.send(JSON.stringify({
            type: "init",
            conversation_id: id
        }));
    }
}

async function startNewConversation() {
    try {
        const token = getToken();
        const res = await fetch("/api/conversations", {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
                ...(token ? { "Authorization": `Bearer ${token}` } : {})
            },
            body: JSON.stringify({ title: "New Conversation" })
        });

        if (res.ok) {
            const newConv = await res.json();
            conversations.unshift(newConv);
            activeConversationId = newConv.id;
            localStorage.setItem("active_conversation_id", newConv.id);
            renderConversationList();

            const conv = document.getElementById("conversation");
            if (conv) {
                conv.innerHTML = `
                    <div class="bot-message" id="welcome-message">
                        <strong>Inventory AI Assistant</strong><br><br>
                        Started a new conversation! How can I help you with inventory, stock, or procurement today?
                    </div>
                `;
            }

            const titleEl = document.getElementById("active-chat-title");
            if (titleEl) titleEl.textContent = newConv.title;

            if (chatSocket && chatSocket.readyState === WebSocket.OPEN) {
                chatSocket.send(JSON.stringify({
                    type: "init",
                    conversation_id: newConv.id
                }));
            }

            const input = document.getElementById("message-input");
            if (input) input.focus();
        }
    } catch (e) {
        console.error("Error creating new conversation:", e);
    }
}

async function loadConversationMessages(id) {
    const conv = document.getElementById("conversation");
    if (!conv) return;

    try {
        const token = getToken();
        const res = await fetch(`/api/conversations/${id}`, {
            headers: token ? { "Authorization": `Bearer ${token}` } : {}
        });

        if (!res.ok) return;

        const data = await res.json();
        const titleEl = document.getElementById("active-chat-title");
        if (titleEl && data.conversation) {
            titleEl.textContent = data.conversation.title || "Inventory Assistant";
        }

        const messages = data.messages || [];

        if (messages.length === 0) {
            conv.innerHTML = `
                <div class="bot-message" id="welcome-message">
                    <strong>Inventory AI Assistant</strong><br><br>
                    Ask any question about inventory, stock levels, suppliers, or procurement.
                </div>
            `;
            return;
        }

        conv.innerHTML = "";
        messages.forEach(msg => {
            if (msg.role === "user") {
                const userDiv = document.createElement("div");
                userDiv.className = "user-message";
                userDiv.textContent = msg.content;
                conv.appendChild(userDiv);
            } else if (msg.role === "assistant") {
                const botDiv = document.createElement("div");
                botDiv.className = "bot-message";
                finalizeStreamingBubble(botDiv, msg.content, msg.extra_data, "assistant");
                conv.appendChild(botDiv);
            }
        });

        scrollToBottom();

    } catch (e) {
        console.error("Error loading conversation messages:", e);
    }
}

async function renameCurrentConversation() {
    if (!activeConversationId) return;
    const current = conversations.find(c => c.id === activeConversationId);
    const newTitle = prompt("Enter new conversation title:", current ? current.title : "");
    if (!newTitle || !newTitle.trim()) return;

    try {
        const token = getToken();
        const res = await fetch(`/api/conversations/${activeConversationId}`, {
            method: "PATCH",
            headers: {
                "Content-Type": "application/json",
                ...(token ? { "Authorization": `Bearer ${token}` } : {})
            },
            body: JSON.stringify({ title: newTitle.trim() })
        });

        if (res.ok) {
            const updated = await res.json();
            const idx = conversations.findIndex(c => c.id === activeConversationId);
            if (idx !== -1) conversations[idx].title = updated.title;
            renderConversationList();
            const titleEl = document.getElementById("active-chat-title");
            if (titleEl) titleEl.textContent = updated.title;
        }
    } catch (e) {
        console.error("Error renaming conversation:", e);
    }
}

async function deleteCurrentConversation() {
    if (!activeConversationId) return;
    if (!confirm("Are you sure you want to delete this conversation?")) return;

    try {
        const token = getToken();
        const res = await fetch(`/api/conversations/${activeConversationId}`, {
            method: "DELETE",
            headers: token ? { "Authorization": `Bearer ${token}` } : {}
        });

        if (res.ok) {
            conversations = conversations.filter(c => c.id !== activeConversationId);
            if (conversations.length > 0) {
                activeConversationId = conversations[0].id;
                localStorage.setItem("active_conversation_id", activeConversationId);
                renderConversationList();
                loadConversationMessages(activeConversationId);
            } else {
                activeConversationId = null;
                localStorage.removeItem("active_conversation_id");
                startNewConversation();
            }
        }
    } catch (e) {
        console.error("Error deleting conversation:", e);
    }
}