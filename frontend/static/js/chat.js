// ============================================================
// CHATBOT & WEBSOCKET STREAMING JAVASCRIPT
// ============================================================

let chatSocket = null;
let reconnectTimer = null;
let pingInterval = null;
let isGenerating = false;
let currentStreamingBubble = null;
let currentStreamingText = "";

function connectWebSocket() {
    if (chatSocket && (chatSocket.readyState === WebSocket.OPEN || chatSocket.readyState === WebSocket.CONNECTING)) {
        return;
    }

    const wsStatus = document.getElementById("ws-status");
    const statusText = wsStatus ? wsStatus.querySelector(".status-text") : null;

    if (wsStatus) {
        wsStatus.className = "ws-status connecting";
        if (statusText) statusText.textContent = "Connecting...";
    }

    const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
    const token = getToken();
    const tokenParam = token ? `?token=${encodeURIComponent(token)}` : "";
    const wsUrl = `${protocol}//${window.location.host}/ws/chat${tokenParam}`;

    chatSocket = new WebSocket(wsUrl);

    chatSocket.onopen = () => {
        if (wsStatus) {
            wsStatus.className = "ws-status connected";
            if (statusText) statusText.textContent = "Live Assistant";
        }
        if (reconnectTimer) {
            clearTimeout(reconnectTimer);
            reconnectTimer = null;
        }
        // Start ping interval
        if (pingInterval) clearInterval(pingInterval);
        pingInterval = setInterval(() => {
            if (chatSocket && chatSocket.readyState === WebSocket.OPEN) {
                chatSocket.send(JSON.stringify({ type: "ping" }));
            }
        }, 25000);
    };

    chatSocket.onmessage = (event) => {
        try {
            const data = JSON.parse(event.data);
            handleWebSocketEvent(data);
        } catch (err) {
            console.error("[WS] Error parsing message:", err);
        }
    };

    chatSocket.onclose = (event) => {
        if (wsStatus) {
            wsStatus.className = "ws-status disconnected";
            if (statusText) statusText.textContent = "Disconnected";
        }
        if (pingInterval) clearInterval(pingInterval);
        if (!reconnectTimer) {
            reconnectTimer = setTimeout(() => {
                reconnectTimer = null;
                connectWebSocket();
            }, 3000);
        }
    };

    chatSocket.onerror = (err) => {
        console.warn("[WS] Socket error:", err);
    };
}

function handleWebSocketEvent(data) {
    const convContainer = document.getElementById("conversation");
    if (!convContainer) return;

    if (data.type === "pong") return;

    if (data.type === "conversation_created") {
        if (data.conversation && !conversations.some(c => c.id === data.conversation.id)) {
            conversations.unshift(data.conversation);
            activeConversationId = data.conversation.id;
            localStorage.setItem("active_conversation_id", activeConversationId);
            if (typeof renderConversationsList === "function") renderConversationsList();
        }
        return;
    }

    if (data.type === "message_start") {
        currentStreamingText = "";
        currentStreamingBubble = document.createElement("div");
        currentStreamingBubble.className = "bot-message";
        currentStreamingBubble.innerHTML = `
            <div class="message-header">🤖 Assistant</div>
            <div class="message-body"><span class="streaming-cursor"></span></div>
        `;
        convContainer.appendChild(currentStreamingBubble);
        convContainer.scrollTop = convContainer.scrollHeight;
        return;
    }

    if (data.type === "token") {
        if (!currentStreamingBubble) {
            currentStreamingBubble = document.createElement("div");
            currentStreamingBubble.className = "bot-message";
            currentStreamingBubble.innerHTML = `
                <div class="message-header">🤖 Assistant</div>
                <div class="message-body"><span class="streaming-cursor"></span></div>
            `;
            convContainer.appendChild(currentStreamingBubble);
        }

        currentStreamingText += data.content;
        const bodyEl = currentStreamingBubble.querySelector(".message-body");
        if (bodyEl) {
            bodyEl.innerHTML = formatMessageText(currentStreamingText) + '<span class="streaming-cursor"></span>';
        }
        convContainer.scrollTop = convContainer.scrollHeight;
        return;
    }

    if (data.type === "message_end") {
        if (currentStreamingBubble) {
            const bodyEl = currentStreamingBubble.querySelector(".message-body");
            const finalText = data.message || currentStreamingText;
            if (bodyEl) {
                let html = formatMessageText(finalText);
                if (data.data && Array.isArray(data.data) && data.data.length > 0) {
                    html += renderDataCards(data.data, data.data_type);
                } else if (data.data && typeof data.data === "object" && !Array.isArray(data.data)) {
                    html += renderDataCards([data.data], data.data_type);
                }
                bodyEl.innerHTML = html;
            }
        }
        currentStreamingBubble = null;
        currentStreamingText = "";
        isGenerating = false;
        const sendBtn = document.getElementById("send-btn");
        if (sendBtn) sendBtn.disabled = false;
        convContainer.scrollTop = convContainer.scrollHeight;
        return;
    }

    if (data.type === "error") {
        const errorBubble = document.createElement("div");
        errorBubble.className = "bot-message";
        errorBubble.style.borderColor = "#fca5a5";
        errorBubble.innerHTML = `
            <div class="message-header" style="color:#ef4444;">⚠️ Error</div>
            <div class="message-body">${escapeHtml(data.message || 'An error occurred.')}</div>
        `;
        convContainer.appendChild(errorBubble);
        currentStreamingBubble = null;
        currentStreamingText = "";
        isGenerating = false;
        const sendBtn = document.getElementById("send-btn");
        if (sendBtn) sendBtn.disabled = false;
        convContainer.scrollTop = convContainer.scrollHeight;
    }
}

function sendMessage() {
    const input = document.getElementById("message-input");
    if (!input) return;
    const text = input.value.trim();
    if (!text || isGenerating) return;

    if (!chatSocket || chatSocket.readyState !== WebSocket.OPEN) {
        connectWebSocket();
        setTimeout(() => sendMessage(), 500);
        return;
    }

    isGenerating = true;
    input.value = "";

    const sendBtn = document.getElementById("send-btn");
    if (sendBtn) sendBtn.disabled = true;

    // Render User Message immediately
    const convContainer = document.getElementById("conversation");
    if (convContainer) {
        const welcome = document.getElementById("welcome-message");
        if (welcome && convContainer.children.length === 1) welcome.remove();

        const userBubble = document.createElement("div");
        userBubble.className = "user-message";
        userBubble.innerHTML = `
            <div class="message-header">You</div>
            <div class="message-body">${escapeHtml(text)}</div>
        `;
        convContainer.appendChild(userBubble);
        convContainer.scrollTop = convContainer.scrollHeight;
    }

    // Send over WebSocket
    chatSocket.send(JSON.stringify({
        type: "message",
        content: text,
        conversation_id: activeConversationId || null,
    }));
}

function quickAsk(promptText) {
    if (typeof switchMainTab === "function") {
        switchMainTab("chat");
    }
    const input = document.getElementById("message-input");
    if (input) {
        input.value = promptText;
        sendMessage();
    }
}

function renderHistoryMessage(msg) {
    const convContainer = document.getElementById("conversation");
    if (!convContainer) return;

    const isUser = msg.role === "user";
    const bubble = document.createElement("div");
    bubble.className = isUser ? "user-message" : "bot-message";

    let contentHtml = isUser ? escapeHtml(msg.content) : formatMessageText(msg.content);

    if (!isUser && msg.extra_data) {
        let extra = msg.extra_data;
        if (typeof extra === "string") {
            try { extra = JSON.parse(extra); } catch (e) {}
        }
        if (Array.isArray(extra) && extra.length > 0) {
            contentHtml += renderDataCards(extra, "inventory");
        } else if (extra && typeof extra === "object" && !Array.isArray(extra)) {
            contentHtml += renderDataCards([extra], "inventory");
        }
    }

    bubble.innerHTML = `
        <div class="message-header">${isUser ? 'You' : '🤖 Assistant'}</div>
        <div class="message-body">${contentHtml}</div>
    `;
    convContainer.appendChild(bubble);
}

function formatMessageText(text) {
    if (!text) return "";
    let formatted = escapeHtml(text);

    // Bold formatting: **text**
    formatted = formatted.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
    
    // Italic formatting: *text* or _text_
    formatted = formatted.replace(/\*(.*?)\*/g, '<em>$1</em>');
    
    // Inline code: `code`
    formatted = formatted.replace(/`([^`]+)`/g, '<code style="background:#f1f5f9; padding:2px 6px; border-radius:4px; font-size:12px;">$1</code>');

    // Bullet points conversion
    const lines = formatted.split("\n");
    let inList = false;
    let result = [];

    for (let line of lines) {
        const trimmed = line.trim();
        if (trimmed.startsWith("• ") || trimmed.startsWith("- ") || trimmed.startsWith("* ")) {
            if (!inList) {
                result.push("<ul style='margin: 6px 0 6px 20px;'>");
                inList = true;
            }
            result.push(`<li>${trimmed.substring(2)}</li>`);
        } else {
            if (inList) {
                result.push("</ul>");
                inList = false;
            }
            result.push(line);
        }
    }
    if (inList) result.push("</ul>");

    return result.join("<br>").replace(/<br><ul/g, "<ul").replace(/<\/ul><br>/g, "</ul>");
}

function renderDataCards(items, dataType) {
    if (!items || items.length === 0) return "";

    return `
        <div style="margin-top: 12px; display: flex; flex-direction: column; gap: 8px;">
            ${items.slice(0, 5).map(item => `
                <div style="background:#f8fafc; border:1px solid #e2e8f0; border-radius:10px; padding:10px 14px; font-size:12px;">
                    <div style="display:flex; justify-content:space-between; align-items:center;">
                        <strong>${escapeHtml(item.name || item.product_name || 'Item')}</strong>
                        <span style="font-weight:700; color:#4f46e5;">₹${Number(item.unit_price || item.price || 0).toFixed(2)}</span>
                    </div>
                    <div style="color:#64748b; margin-top:3px;">
                        Stock: <strong>${item.current_stock !== undefined ? item.current_stock : (item.stock || 0)} units</strong> | 
                        Supplier: <strong>${escapeHtml(item.supplier || item.vendor_name || 'Standard Vendor')}</strong>
                    </div>
                </div>
            `).join("")}
        </div>
    `;
}
