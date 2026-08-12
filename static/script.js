let inventory = [];

const $ = (id) => document.getElementById(id);

function escapeHtml(value) {
  const div = document.createElement("div");
  div.textContent = value == null ? "" : String(value);
  return div.innerHTML;
}

async function api(url, options = {}) {
  const response = await fetch(url, {
    ...options,
    headers: {"Accept": "application/json", "Content-Type": "application/json", ...(options.headers || {})}
  });
  if (!response.ok) {
    let detail = `Request failed (${response.status})`;
    try { const body = await response.json(); detail = body.detail || body.message || detail; } catch {}
    throw new Error(detail);
  }
  return response.json();
}

function addUserMessage(text) {
  const el = document.createElement("div");
  el.className = "user-message";
  el.textContent = text;
  $("conversation").appendChild(el);
  scrollChat();
}

function addBotMessage(text, source = "") {
  const el = document.createElement("div");
  el.className = "bot-message";
  const safe = escapeHtml(text).replace(/\n/g, "<br>");
  el.innerHTML = safe + (source ? `<div class="source">Source: ${escapeHtml(source)}</div>` : "");
  $("conversation").appendChild(el);
  scrollChat();
}

function scrollChat() {
  const c = $("conversation");
  c.scrollTop = c.scrollHeight;
}

function status(item) {
  return Number(item.stock) <= Number(item.min_stock) ? "low" : "ok";
}

function itemHtml(item) {
  const low = status(item) === "low";
  return `<div class="item ${low ? "low" : ""}">
    <div class="item-top">
      <span class="item-name">${escapeHtml(item.name)}</span>
      <span class="stock ${low ? "low" : "ok"}">${item.stock} units</span>
    </div>
    <div class="meta">${escapeHtml(item.category)} · minimum ${item.min_stock} · ${escapeHtml(item.supplier)}</div>
    <div class="actions">
      <button class="reorder" onclick="reorder(${item.id}, '${escapeHtml(item.name).replaceAll("'", "\\'")}')">Reorder</button>
    </div>
  </div>`;
}

function renderInventory(items, target = $("inventory-list")) {
  if (!items.length) {
    target.innerHTML = `<div class="muted">No matching inventory items.</div>`;
    return;
  }
  target.innerHTML = items.map(itemHtml).join("");
}

function updateStats() {
  $("total-products").textContent = inventory.length;
  $("low-stock-count").textContent = inventory.filter(i => status(i) === "low").length;
  $("supplier-count").textContent = new Set(inventory.map(i => i.supplier).filter(Boolean)).size;
  $("category-count").textContent = new Set(inventory.map(i => i.category).filter(Boolean)).size;
}

async function loadInventory() {
  try {
    inventory = await api("/api/inventory");
    updateStats();
    renderInventory(inventory);
    await loadLowStock();
  } catch (e) {
    $("inventory-list").innerHTML = `<div class="muted">${escapeHtml(e.message)}</div>`;
  }
}

async function loadLowStock() {
  const list = $("low-stock-list");
  list.innerHTML = `<div class="muted">Loading…</div>`;
  try {
    const items = await api("/api/inventory/low-stock");
    renderInventory(items, list);
  } catch (e) {
    list.innerHTML = `<div class="muted">${escapeHtml(e.message)}</div>`;
  }
}

async function sendMessage(text = $("message-input").value.trim()) {
  if (!text) return;
  $("message-input").value = "";
  addUserMessage(text);
  const send = $("send-button");
  send.disabled = true;
  const typing = document.createElement("div");
  typing.className = "bot-message typing";
  typing.textContent = "Thinking…";
  $("conversation").appendChild(typing);
  scrollChat();

  try {
    const result = await api("/api/chat", {
      method: "POST",
      body: JSON.stringify({message: text})
    });
    typing.remove();

    if (result.data?.length) {
      const intro = result.answer || "Here are the matching inventory items:";
      addBotMessage(intro, result.sources?.join(", "));
      const box = document.createElement("div");
      box.className = "bot-message";
      box.innerHTML = result.data.slice(0, 10).map(itemHtml).join("");
      $("conversation").appendChild(box);
      scrollChat();
    } else {
      addBotMessage(result.answer || "I couldn't find an answer.", result.sources?.join(", "));
    }
  } catch (e) {
    typing.remove();
    addBotMessage(`Sorry, I couldn't process that request: ${e.message}`);
  } finally {
    send.disabled = false;
    $("message-input").focus();
  }
}

async function reorder(itemId, itemName) {
  const quantity = prompt(`How many "${itemName}" units should be reordered?`, "10");
  if (quantity === null) return;
  const q = Number(quantity);
  if (!Number.isInteger(q) || q <= 0) {
    alert("Enter a positive whole number.");
    return;
  }
  try {
    await api("/api/reorders", {
      method: "POST",
      body: JSON.stringify({item_id: itemId, quantity: q})
    });
    addBotMessage(`Reorder request created for ${q} units of ${itemName}.`);
  } catch (e) {
    addBotMessage(`Could not create reorder request: ${e.message}`);
  }
}

$("chat-form").addEventListener("submit", (e) => {
  e.preventDefault();
  sendMessage();
});

$("clear-chat").addEventListener("click", () => {
  $("conversation").innerHTML = `<div class="bot-message"><strong>Chat cleared.</strong><p>What would you like to know about the inventory?</p></div>`;
});

$("refresh-low").addEventListener("click", loadLowStock);

$("inventory-search").addEventListener("input", async (e) => {
  const q = e.target.value.trim();
  if (!q) return renderInventory(inventory);
  try {
    const items = await api(`/api/inventory/search?q=${encodeURIComponent(q)}`);
    renderInventory(items);
  } catch {}
});

document.querySelectorAll(".chips button").forEach(btn => {
  btn.addEventListener("click", () => sendMessage(btn.dataset.q));
});

document.addEventListener("DOMContentLoaded", loadInventory);