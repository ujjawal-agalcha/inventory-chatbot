// ============================================================
// INVENTORY MANAGEMENT & AI ASSISTANT JAVASCRIPT
// ============================================================

// Categories configuration
const categories = [
    { name: "ESP Modules", icon: "📡", description: "ESP32, ESP8266 & wireless boards" },
    { name: "Arduino Boards", icon: "🔌", description: "Uno R3, Nano, Mega 2560 & Leonardo" },
    { name: "Motor Drivers", icon: "⚙️", description: "L298N, BTS7960 & TB6612FNG" },
    { name: "Motors", icon: "🔧", description: "DC gear motors, servos & steppers" },
    { name: "Sensors", icon: "📊", description: "Ultrasonic, DHT11, PIR & gyroscopes" },
    { name: "Batteries", icon: "🔋", description: "18650 Li-ion, LiPo & 9V rechargeable" },
    { name: "Displays", icon: "🖥️", description: "16x2 LCD, 0.96 OLED & TFT displays" },
    { name: "Relays", icon: "🔀", description: "1-channel & 4-channel relay modules" },
    { name: "Communication", icon: "📶", description: "Bluetooth HC-05, GSM & GPS modules" },
    { name: "Components", icon: "🔩", description: "Resistors, capacitors, LEDs & breadboards" }
];

// Global State
let activeConversationId = localStorage.getItem("active_conversation_id") || null;
let conversations = [];
let chatSocket = null;
let reconnectTimer = null;
let pingInterval = null;
let isGenerating = false;
let currentStreamingBubble = null;
let currentStreamingText = "";

// ============================================================
// INITIALIZATION
// ============================================================

document.addEventListener("DOMContentLoaded", async () => {
    initCategories();
    await loadUser();
    await loadStats();
    await loadConversations();
    connectWebSocket();
});

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
// DASHBOARD STATS & CATEGORIES
// ============================================================

function initCategories() {
    const grid = document.getElementById("category-grid");
    if (!grid) return;

    grid.innerHTML = categories.map(cat => `
        <div class="category-card" onclick="quickAsk('Show all ${cat.name}')">
            <div class="category-icon">${cat.icon}</div>
            <div class="category-info">
                <h4>${escapeHtml(cat.name)}</h4>
                <p>${escapeHtml(cat.description)}</p>
            </div>
        </div>
    `).join("");
}

async function loadStats() {
    try {
        const res = await fetch("/api/inventory/stats");
        if (res.ok) {
            const stats = await res.json();
            const elTotal = document.getElementById("stat-total");
            const elLow = document.getElementById("stat-low");
            const elUnits = document.getElementById("stat-units");
            if (elTotal) elTotal.textContent = stats.total_components;
            if (elLow) elLow.textContent = stats.low_stock;
            if (elUnits) elUnits.textContent = stats.total_units;
        }
    } catch (e) {
        console.warn("Could not load stats:", e);
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
            console.log("[WS] Connected successfully");
            updateStatus("connected", "Live Connected");
            if (reconnectTimer) {
                clearTimeout(reconnectTimer);
                reconnectTimer = null;
            }

            // Start Ping Keepalive
            if (pingInterval) clearInterval(pingInterval);
            pingInterval = setInterval(() => {
                if (chatSocket && chatSocket.readyState === WebSocket.OPEN) {
                    chatSocket.send(JSON.stringify({ type: "ping" }));
                }
            }, 25000);

            // Inform server of active conversation
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

            // Reconnect attempt
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
                console.log("[WS Unknown Event]", data);
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
    if (conv) {
        conv.scrollTop = conv.scrollHeight;
    }
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

    // Remove initial welcome if first message
    const welcome = document.getElementById("welcome-message");
    if (welcome && conv.children.length === 1) {
        // keep welcome or let it stay
    }

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
            // Render items list or table
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
            // Single component card
            const item = structuredData;
            const card = document.createElement("div");
            card.className = "component-card-detail";
            card.innerHTML = `
                <div class="detail-header">
                    <h4>${escapeHtml(item.name)}</h4>
                    <span class="status-badge ${item.is_low_stock ? 'low' : 'ok'}">${item.is_low_stock ? '⚠ Low Stock' : '✓ In Stock'}</span>
                </div>
                <div class="detail-grid">
                    <div><span>Current Stock:</span> <strong>${item.stock} units</strong></div>
                    <div><span>Min Level:</span> <strong>${item.min_stock} units</strong></div>
                    <div><span>Category:</span> <strong>${escapeHtml(item.category)}</strong></div>
                    <div><span>Supplier:</span> <strong>${escapeHtml(item.supplier)}</strong></div>
                </div>
                <div class="detail-actions">
                    <button class="mini-btn primary" onclick="quickAsk('Reorder ${escapeHtml(item.name)}')">📦 Reorder</button>
                    <button class="mini-btn" onclick="quickAsk('Who supplies ${escapeHtml(item.name)}?')">🚚 Supplier Info</button>
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

    // Make sure socket is open
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

        // If no active conversation, pick the first one
        if (!activeConversationId && conversations.length > 0) {
            activeConversationId = conversations[0].id;
            localStorage.setItem("active_conversation_id", activeConversationId);
        }

        renderConversationList();

        // If active conversation exists, load messages
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

    // Notify WebSocket of conversation switch
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

            // Clear chat window and show welcome
            const conv = document.getElementById("conversation");
            if (conv) {
                conv.innerHTML = `
                    <div class="bot-message" id="welcome-message">
                        <strong>Inventory AI Assistant</strong><br><br>
                        Started a new conversation! How can I help you with the inventory today?
                    </div>
                `;
            }

            const titleEl = document.getElementById("active-chat-title");
            if (titleEl) titleEl.textContent = newConv.title;

            // Notify WebSocket
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
                    Ask any question about inventory, stock levels, or components.
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