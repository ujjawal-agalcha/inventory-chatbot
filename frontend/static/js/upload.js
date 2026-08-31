// ============================================================
// EXCEL IMPORT HUB & DATA SYNC JAVASCRIPT
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
                    alert("Please select a valid Excel (.xlsx or .xls) file.");
                }
            }
        });
    });
}

function handleFileSelected(type) {
    const input = document.getElementById(`file-input-${type}`);
    if (input && input.files && input.files.length > 0) {
        const file = input.files[0];
        selectedFiles[type] = file;
        updateFileDisplay(type, file.name);
    }
}

function updateFileDisplay(type, filename) {
    const display = document.getElementById(`file-name-${type}`);
    const btn = document.getElementById(`btn-upload-${type}`);
    if (display) display.textContent = `Selected: ${filename}`;
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
        btn.textContent = "Uploading & Ingesting...";
    }
    if (feedback) feedback.style.display = "none";

    const formData = new FormData();
    formData.append("file", file);

    const token = getToken();
    const endpoint = type === "procurement" ? "/api/upload/procurement" : "/api/upload/expenses";

    try {
        const res = await fetch(endpoint, {
            method: "POST",
            headers: token ? { "Authorization": `Bearer ${token}` } : {},
            body: formData,
        });

        const result = await res.json();

        if (res.ok && result.success) {
            if (feedback) {
                feedback.style.display = "block";
                feedback.className = "upload-feedback success";
                feedback.innerHTML = `
                    <strong>✅ ${escapeHtml(result.message)}</strong><br>
                    • Valid Records: ${result.data?.valid_records || 0}<br>
                    • New Master Products: ${result.data?.new_records || 0}<br>
                    • Updated Products: ${result.data?.updated_records || 0}<br>
                    • Duplicates Prevented: ${result.data?.duplicate_records || 0}
                `;
            }

            // Show latest ingestion metrics card
            showImportSummaryCard(result.data);

            // Refresh global data
            if (typeof loadStats === "function") await loadStats();
            if (typeof loadCategories === "function") await loadCategories();
            if (typeof loadInventoryTabTable === "function") await loadInventoryTabTable();
            if (typeof renderMasterTable === "function") await renderMasterTable();
            await loadImportHistory();

        } else {
            if (feedback) {
                feedback.style.display = "block";
                feedback.className = "upload-feedback error";
                feedback.textContent = `❌ ${result.detail || result.message || 'Upload failed.'}`;
            }
        }
    } catch (e) {
        console.error("Upload error:", e);
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

function showImportSummaryCard(data) {
    if (!data) return;
    const card = document.getElementById("import-stats-summary");
    if (!card) return;

    card.style.display = "block";
    const elTot = document.getElementById("metric-total-rows");
    const elVal = document.getElementById("metric-valid-rows");
    const elNew = document.getElementById("metric-new-prods");
    const elUpd = document.getElementById("metric-updated-prods");
    const elDup = document.getElementById("metric-dup-rows");

    if (elTot) elTot.textContent = data.total_rows || 0;
    if (elVal) elVal.textContent = data.valid_records || 0;
    if (elNew) elNew.textContent = data.new_records || 0;
    if (elUpd) elUpd.textContent = data.updated_records || 0;
    if (elDup) elDup.textContent = data.duplicate_records || 0;
}

async function loadImportHistory() {
    const tbody = document.getElementById("import-history-body");
    if (!tbody) return;

    try {
        const token = getToken();
        const res = await fetch("/api/imports", {
            headers: token ? { "Authorization": `Bearer ${token}` } : {}
        });

        if (res.ok) {
            const imports = await res.json();
            if (imports.length === 0) {
                tbody.innerHTML = `<tr><td colspan="10" class="text-center">No files imported yet.</td></tr>`;
                return;
            }

            tbody.innerHTML = imports.map(imp => {
                const ts = imp.upload_timestamp ? new Date(imp.upload_timestamp).toLocaleString() : "-";
                return `
                    <tr>
                        <td><small>${ts}</small></td>
                        <td><strong>${escapeHtml(imp.filename)}</strong></td>
                        <td><span class="badge-tag">${escapeHtml(imp.file_type || 'Excel')}</span></td>
                        <td>${imp.total_rows || 0}</td>
                        <td><strong class="text-success">${imp.valid_records || 0}</strong></td>
                        <td>${imp.new_records || 0}</td>
                        <td>${imp.updated_records || 0}</td>
                        <td><span class="text-warning">${imp.duplicate_records || 0}</span></td>
                        <td><span class="status-badge ok">${escapeHtml(imp.status || 'Completed')}</span></td>
                        <td>
                            <button class="mini-btn" style="color:#ef4444;" onclick="deleteImportBatchPrompt('${imp.id}')" title="Safely delete this import batch">🗑️ Delete</button>
                        </td>
                    </tr>
                `;
            }).join("");
        }
    } catch (e) {
        console.error("Error loading import history:", e);
        tbody.innerHTML = `<tr><td colspan="10" class="text-center">Error loading import history.</td></tr>`;
    }
}

async function deleteImportBatchPrompt(importId) {
    try {
        const token = getToken();
        // 1. Preview deletion first
        const prevRes = await fetch(`/api/admin/imports/${importId}/preview`, {
            headers: token ? { "Authorization": `Bearer ${token}` } : {}
        });
        if (!prevRes.ok) {
            alert("Could not preview import batch deletion.");
            return;
        }
        const preview = await prevRes.json();
        const confirmMsg = `Are you sure you want to delete import batch for '${preview.filename}'?\n\n` +
            `• Procurement records to remove: ${preview.procurement_records_to_delete}\n` +
            `• Expense records to remove: ${preview.expense_records_to_delete}\n` +
            `• Exclusive products to remove: ${preview.products_to_delete_count}\n` +
            `• Permanent/Shared products preserved: ${preview.products_to_preserve_and_update_count}\n\n` +
            `This action cannot be undone.`;

        if (!confirm(confirmMsg)) return;

        // 2. Execute deletion
        const delRes = await fetch(`/api/admin/imports/${importId}`, {
            method: "DELETE",
            headers: token ? { "Authorization": `Bearer ${token}` } : {}
        });

        if (delRes.ok) {
            alert("Import batch removed successfully.");
            if (typeof loadStats === "function") await loadStats();
            if (typeof loadCategories === "function") await loadCategories();
            if (typeof loadInventoryTabTable === "function") await loadInventoryTabTable();
            if (typeof renderMasterTable === "function") await renderMasterTable();
            await loadImportHistory();
        } else {
            const errData = await delRes.json();
            alert(`Failed to delete batch: ${errData.detail || 'Unknown error'}`);
        }
    } catch (e) {
        console.error("Error deleting import batch:", e);
    }
}

async function cleanupSampleDataPrompt() {
    if (!confirm("Clean up any legacy sample Excel imports? Legitimate permanent electronic equipment inventory will be strictly preserved.")) return;

    try {
        const token = getToken();
        const res = await fetch("/api/admin/cleanup-sample-data", {
            method: "POST",
            headers: token ? { "Authorization": `Bearer ${token}` } : {}
        });
        const data = await res.json();
        if (res.ok && data.success) {
            alert(`Sample data cleaned successfully! Permanent electronic equipment preserved (${data.permanent_products_count} items).`);
            if (typeof loadStats === "function") await loadStats();
            if (typeof loadCategories === "function") await loadCategories();
            if (typeof loadInventoryTabTable === "function") await loadInventoryTabTable();
            if (typeof renderMasterTable === "function") await renderMasterTable();
            await loadImportHistory();
        } else {
            alert("Cleanup failed: " + (data.detail || "Unknown error"));
        }
    } catch (e) {
        console.error("Error cleaning sample data:", e);
    }
}
