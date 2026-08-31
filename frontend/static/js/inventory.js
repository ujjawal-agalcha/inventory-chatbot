// ============================================================
// DEDICATED INVENTORY TAB & EDITING JAVASCRIPT
// ============================================================

let inventoryTabData = [];

function getStockBadgeHtml(stock, minStock) {
    const threshold = (minStock !== undefined && minStock !== null && minStock > 0) ? minStock : 15;
    const stockVal = Number(stock || 0);

    if (stockVal < threshold) {
        return `<span class="stock-badge-red" title="Low stock! Below minimum threshold (${threshold})">⚠️ ${stockVal} units</span>`;
    } else if (stockVal === threshold) {
        return `<span class="stock-badge-yellow" title="Stock at exact threshold (${threshold})">⚠️ ${stockVal} units</span>`;
    } else {
        return `<span class="stock-badge-green" title="Healthy stock (> ${threshold})">✓ ${stockVal} units</span>`;
    }
}

async function loadInventoryTabTable() {
    const tbody = document.getElementById("inventory-tab-body");
    const catSelect = document.getElementById("inventory-tab-cat-filter");
    if (!tbody) return;

    try {
        const res = await fetch("/api/inventory");
        if (res.ok) {
            inventoryTabData = await res.json();
            masterInventory = inventoryTabData;

            if (catSelect) {
                const uniqueCats = Array.from(new Set(inventoryTabData.map(i => i.category).filter(Boolean)));
                const currentVal = catSelect.value;
                catSelect.innerHTML = `<option value="">All Categories</option>` + uniqueCats.map(c =>
                    `<option value="${escapeHtml(c)}" ${c === currentVal ? 'selected' : ''}>${escapeHtml(c)}</option>`
                ).join("");
            }

            filterInventoryTabTable();
        }
    } catch (e) {
        console.error("Error loading inventory tab table:", e);
        tbody.innerHTML = `<tr><td colspan="10" class="text-center">Error loading inventory. Please refresh.</td></tr>`;
    }
}

function filterInventoryTabTable() {
    const tbody = document.getElementById("inventory-tab-body");
    if (!tbody) return;

    const query = (document.getElementById("inventory-tab-search")?.value || "").toLowerCase().trim();
    const selectedCat = document.getElementById("inventory-tab-cat-filter")?.value || "";

    const filtered = inventoryTabData.filter(item => {
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
        const stockBadge = getStockBadgeHtml(item.stock, item.min_stock);
        const lastUpdated = item.last_updated ? new Date(item.last_updated).toLocaleString() : "-";

        return `
            <tr>
                <td>
                    <strong>${escapeHtml(item.name)}</strong>
                    ${item.details ? `<br><small class="text-muted">${escapeHtml(item.details)}</small>` : ''}
                </td>
                <td><span class="badge-tag">${escapeHtml(item.category)}</span></td>
                <td><span class="badge-tag" style="background:#f1f5f9; color:#475569;">${escapeHtml(item.sub_category || '-')}</span></td>
                <td>₹${Number(item.unit_price).toFixed(2)}</td>
                <td>${stockBadge}</td>
                <td>${item.min_stock} units</td>
                <td>${escapeHtml(item.supplier || 'Standard Vendor')}</td>
                <td>
                    <span class="status-badge ${item.is_low_stock ? 'low' : 'ok'}">
                        ${item.is_low_stock ? '⚠️ Low Stock' : '✓ In Stock'}
                    </span>
                </td>
                <td><small>${lastUpdated}</small></td>
                <td>
                    <div style="display: flex; gap: 6px;">
                        <button class="edit-icon-btn" onclick="openEditModal('${item.id}')" title="Edit this product">✏️ Edit</button>
                        <button class="mini-btn" onclick="quickReorderPrompt('${escapeHtml(item.name)}')">📦</button>
                    </div>
                </td>
            </tr>
        `;
    }).join("");
}

function openEditModal(productId) {
    const item = masterInventory.find(i => String(i.id) === String(productId)) || inventoryTabData.find(i => String(i.id) === String(productId));
    if (!item) {
        alert("Product not found.");
        return;
    }

    document.getElementById("edit-product-id").value = item.id;
    document.getElementById("edit-name").value = item.name || "";
    document.getElementById("edit-category").value = item.category || "";
    document.getElementById("edit-subcategory").value = item.sub_category || "";
    document.getElementById("edit-stock").value = item.stock !== undefined ? item.stock : (item.current_stock || 0);
    document.getElementById("edit-min-stock").value = item.min_stock !== undefined ? item.min_stock : 15;
    document.getElementById("edit-price").value = item.unit_price || 0;
    document.getElementById("edit-supplier").value = item.supplier || "";
    document.getElementById("edit-market").value = item.market || "Direct";
    document.getElementById("edit-details").value = item.details || "";

    const feedback = document.getElementById("edit-feedback");
    if (feedback) feedback.style.display = "none";

    const modal = document.getElementById("inventory-edit-modal");
    if (modal) modal.classList.add("active");
}

function closeEditModal() {
    const modal = document.getElementById("inventory-edit-modal");
    if (modal) modal.classList.remove("active");
}

async function handleProductEditSubmit(event) {
    event.preventDefault();
    const productId = document.getElementById("edit-product-id").value;
    if (!productId) return;

    const btn = document.getElementById("btn-save-edit");
    const feedback = document.getElementById("edit-feedback");
    const originalText = btn ? btn.textContent : "Save";

    const payload = {
        name: document.getElementById("edit-name").value.trim(),
        category: document.getElementById("edit-category").value.trim(),
        sub_category: document.getElementById("edit-subcategory").value.trim(),
        current_stock: parseInt(document.getElementById("edit-stock").value, 10),
        min_stock: parseInt(document.getElementById("edit-min-stock").value, 10),
        unit_price: parseFloat(document.getElementById("edit-price").value),
        supplier: document.getElementById("edit-supplier").value.trim(),
        market: document.getElementById("edit-market").value.trim(),
        details: document.getElementById("edit-details").value.trim(),
    };

    if (btn) {
        btn.disabled = true;
        btn.textContent = "Saving...";
    }

    try {
        const token = getToken();
        const res = await fetch(`/api/inventory/${productId}`, {
            method: "PUT",
            headers: {
                "Content-Type": "application/json",
                ...(token ? { "Authorization": `Bearer ${token}` } : {})
            },
            body: JSON.stringify(payload)
        });

        const data = await res.json();

        if (res.ok) {
            closeEditModal();
            await loadStats();
            await loadCategories();
            await loadInventoryTabTable();
            if (typeof renderMasterTable === "function") await renderMasterTable();
        } else {
            if (feedback) {
                feedback.style.display = "block";
                feedback.className = "upload-feedback error";
                feedback.textContent = `❌ Update failed: ${data.detail || "Unknown error"}`;
            }
        }
    } catch (e) {
        console.error("Error saving product edit:", e);
        if (feedback) {
            feedback.style.display = "block";
            feedback.className = "upload-feedback error";
            feedback.textContent = `❌ Network or server error: ${e.message}`;
        }
    } finally {
        if (btn) {
            btn.disabled = false;
            btn.textContent = originalText;
        }
    }
}

function quickReorderPrompt(productName) {
    if (typeof quickAsk === "function") {
        quickAsk(`Reorder 10 units of ${productName}`);
    }
}
