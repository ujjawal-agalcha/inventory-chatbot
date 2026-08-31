// ============================================================
// CONVERSATIONS MANAGEMENT JAVASCRIPT
// ============================================================

let activeConversationId = localStorage.getItem("active_conversation_id") || null;
let conversations = [];

function getToken() {
    return localStorage.getItem("access_token") || getCookie("access_token");
}

function getCookie(name) {
    const value = `; ${document.cookie}`;
    const parts = value.split(`; ${name}=`);
    if (parts.length === 2) return parts.pop().split(";").shift();
    return null;
}

function escapeHtml(text) {
    if (!text) return "";
    return String(text)
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#039;");
}

async function loadConversations() {
    const listEl = document.getElementById("conversation-list");
    if (!listEl) return;

    try {
        const token = getToken();
        const res = await fetch("/api/conversations", {
            headers: token ? { "Authorization": `Bearer ${token}` } : {}
        });

        if (res.ok) {
            conversations = await res.json();
            renderConversationsList();

            if (activeConversationId) {
                const exists = conversations.find(c => c.id === activeConversationId);
                if (exists) {
                    await selectConversation(activeConversationId, false);
                } else if (conversations.length > 0) {
                    await selectConversation(conversations[0].id, false);
                }
            } else if (conversations.length > 0) {
                await selectConversation(conversations[0].id, false);
            }
        }
    } catch (e) {
        console.error("Error loading conversations:", e);
        listEl.innerHTML = `<div class="conv-item-empty">Failed to load conversations.</div>`;
    }
}

function renderConversationsList() {
    const listEl = document.getElementById("conversation-list");
    if (!listEl) return;

    if (conversations.length === 0) {
        listEl.innerHTML = `
            <div class="conv-item-empty">
                No past chats yet.<br>Click <strong>+ New Chat</strong> to start.
            </div>
        `;
        return;
    }

    listEl.innerHTML = conversations.map(c => `
        <div class="conv-item ${c.id === activeConversationId ? 'active' : ''}" onclick="selectConversation('${c.id}')" title="${escapeHtml(c.title)}">
            <span class="conv-icon">💬</span>
            <span class="conv-title">${escapeHtml(c.title || 'New Chat')}</span>
        </div>
    `).join("");
}

async function selectConversation(convId, switchToChatTab = true) {
    activeConversationId = convId;
    localStorage.setItem("active_conversation_id", convId);
    renderConversationsList();

    if (switchToChatTab && typeof switchMainTab === "function") {
        switchMainTab("chat");
    }

    const conv = conversations.find(c => c.id === convId);
    const titleEl = document.getElementById("active-chat-title");
    const subtitleEl = document.getElementById("active-chat-subtitle");

    if (titleEl) titleEl.textContent = conv ? conv.title : "Inventory Assistant";
    if (subtitleEl) subtitleEl.textContent = conv ? `Updated: ${new Date(conv.updated_at).toLocaleString()}` : "Real-time stock assistance & intelligent procurement reasoning";

    // Load message history
    try {
        const token = getToken();
        const res = await fetch(`/api/conversations/${convId}`, {
            headers: token ? { "Authorization": `Bearer ${token}` } : {}
        });

        if (res.ok) {
            const data = await res.json();
            const messages = data.messages || [];
            const convContainer = document.getElementById("conversation");

            if (convContainer) {
                if (messages.length === 0) {
                    convContainer.innerHTML = `
                        <div class="bot-message" id="welcome-message">
                            <strong>👋 Welcome to the Inventory Assistant!</strong><br><br>
                            How can I help you with your inventory, stock levels, or procurement today?
                        </div>
                    `;
                } else {
                    convContainer.innerHTML = "";
                    messages.forEach(m => {
                        if (typeof renderHistoryMessage === "function") {
                            renderHistoryMessage(m);
                        }
                    });
                    convContainer.scrollTop = convContainer.scrollHeight;
                }
            }
        }
    } catch (e) {
        console.error("Error loading conversation messages:", e);
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
            await selectConversation(newConv.id);
            const input = document.getElementById("message-input");
            if (input) input.focus();
        }
    } catch (e) {
        console.error("Error creating new conversation:", e);
    }
}

async function renameCurrentConversation() {
    if (!activeConversationId) return;
    const currentConv = conversations.find(c => c.id === activeConversationId);
    const newTitle = prompt("Enter new title for this conversation:", currentConv ? currentConv.title : "");
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
            if (idx !== -1) conversations[idx] = updated;
            renderConversationsList();
            const titleEl = document.getElementById("active-chat-title");
            if (titleEl) titleEl.textContent = updated.title;
        }
    } catch (e) {
        console.error("Error renaming conversation:", e);
    }
}

async function deleteCurrentConversation() {
    if (!activeConversationId) return;
    if (!confirm("Are you sure you want to delete this entire conversation?")) return;

    try {
        const token = getToken();
        const res = await fetch(`/api/conversations/${activeConversationId}`, {
            method: "DELETE",
            headers: token ? { "Authorization": `Bearer ${token}` } : {}
        });

        if (res.ok) {
            conversations = conversations.filter(c => c.id !== activeConversationId);
            activeConversationId = conversations.length > 0 ? conversations[0].id : null;
            localStorage.setItem("active_conversation_id", activeConversationId || "");
            renderConversationsList();

            if (activeConversationId) {
                await selectConversation(activeConversationId);
            } else {
                const convContainer = document.getElementById("conversation");
                if (convContainer) {
                    convContainer.innerHTML = `
                        <div class="bot-message">
                            <strong>👋 Welcome to the Inventory Assistant!</strong><br><br>
                            Click <strong>+ New Chat</strong> to begin a new conversation.
                        </div>
                    `;
                }
            }
        }
    } catch (e) {
        console.error("Error deleting conversation:", e);
    }
}
