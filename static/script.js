// ============================================================
// INVENTORY MANAGEMENT DASHBOARD - script.js
// ============================================================

// ============================================================
// CATEGORY CONFIGURATION
// ============================================================

const categories = [
    {
        name: "ESP Modules",
        icon: "📡",
        description: "ESP32, ESP8266 and wireless modules"
    },
    {
        name: "Arduino Boards",
        icon: "🔌",
        description: "Arduino Uno, Nano and development boards"
    },
    {
        name: "Motor Drivers",
        icon: "⚙️",
        description: "L298N, BTS7960 and motor control modules"
    },
    {
        name: "Motors",
        icon: "🔧",
        description: "DC motors, servo motors and stepper motors"
    },
    {
        name: "Sensors",
        icon: "📊",
        description: "Ultrasonic, IR, temperature and motion sensors"
    },
    {
        name: "Batteries",
        icon: "🔋",
        description: "Li-ion, LiPo and rechargeable battery packs"
    },
    {
        name: "Displays",
        icon: "🖥️",
        description: "LCD, OLED and TFT display modules"
    },
    {
        name: "Relays",
        icon: "🔀",
        description: "Relay modules and switching components"
    },
    {
        name: "Communication",
        icon: "📶",
        description: "Bluetooth, GSM, GPS and communication modules"
    },
    {
        name: "Components",
        icon: "🔩",
        description: "Resistors, capacitors, LEDs and electronic components"
    }
];

// ============================================================
// GLOBAL DATA
// ============================================================

let inventory = [];
let lowStockItems = [];
let reorderRequests = [];

// Prevent repeated browser notification popups
let browserNotificationShown = false;

// ============================================================
// HTML ESCAPE
// ============================================================

function escapeHtml(value) {
    const div = document.createElement("div");

    div.textContent =
        value === null ||
        value === undefined
            ? ""
            : String(value);

    return div.innerHTML;
}

// ============================================================
// API HELPER
// ============================================================

async function apiRequest(url, options = {}) {

    const response = await fetch(url, {
        ...options,

        headers: {
            "Accept": "application/json",
            ...(options.headers || {})
        }
    });

    if (!response.ok) {

        let detail = `HTTP ${response.status}`;

        try {

            const data = await response.json();

            if (data.detail) {
                detail = data.detail;
            }

            if (data.message) {
                detail = data.message;
            }

        } catch (error) {
            // Ignore JSON parsing errors
        }

        throw new Error(detail);
    }

    return await response.json();
}

// ============================================================
// MESSAGE HELPERS
// ============================================================

function addUserMessage(message) {

    const conversation =
        document.getElementById("conversation");

    if (!conversation) {
        return;
    }

    const div =
        document.createElement("div");

    div.className =
        "user-message";

    div.textContent =
        message;

    conversation.appendChild(div);

    conversation.scrollTop =
        conversation.scrollHeight;
}

function addBotMessage(message) {

    const conversation =
        document.getElementById("conversation");

    if (!conversation) {
        return;
    }

    const div =
        document.createElement("div");

    div.className =
        "bot-message";

    div.innerHTML =
        message;

    conversation.appendChild(div);

    conversation.scrollTop =
        conversation.scrollHeight;
}

// ============================================================
// CREATE LOW STOCK NOTIFICATION AREA
// ============================================================

function createNotificationArea() {

    let area =
        document.getElementById(
            "low-stock-notification"
        );

    if (area) {
        return area;
    }

    area =
        document.createElement("div");

    area.id =
        "low-stock-notification";

    area.style.cssText = `
        margin: 15px 0;
        padding: 16px;
        border-radius: 12px;
        border: 1px solid #fecaca;
        background: #fff7ed;
        color: #7f1d1d;
    `;

    const dashboard =
        document.querySelector("main") ||
        document.body;

    dashboard.prepend(area);

    return area;
}

// ============================================================
// SHOW LOW STOCK NOTIFICATION
// ============================================================

function showLowStockNotification() {

    const area =
        createNotificationArea();

    if (!lowStockItems.length) {

        area.style.display =
            "none";

        return;
    }

    area.style.display =
        "block";

    area.innerHTML = `

        <div style="
            display:flex;
            justify-content:space-between;
            align-items:center;
            gap:15px;
            flex-wrap:wrap;
        ">

            <div>

                <strong style="
                    font-size:18px;
                    color:#b91c1c;
                ">
                    ⚠ Low Stock Alert
                </strong>

                <div style="
                    margin-top:5px;
                    color:#7f1d1d;
                ">

                    ${lowStockItems.length}
                    item${lowStockItems.length === 1 ? "" : "s"}
                    need attention.

                </div>

            </div>

            <div style="
                display:flex;
                gap:8px;
                flex-wrap:wrap;
            ">

                <button
                    onclick="showAllLowStock()"
                    style="
                        background:#dc2626;
                        color:white;
                        border:none;
                        padding:9px 14px;
                        border-radius:8px;
                        cursor:pointer;
                        font-weight:600;
                    "
                >
                    View Low Stock
                </button>

                <button
                    onclick="notifyAllLowStock()"
                    style="
                        background:#f59e0b;
                        color:white;
                        border:none;
                        padding:9px 14px;
                        border-radius:8px;
                        cursor:pointer;
                        font-weight:600;
                    "
                >
                    🔔 Notify All
                </button>

            </div>

        </div>

    `;
}

// ============================================================
// BROWSER NOTIFICATION PERMISSION
// ============================================================

async function requestNotificationPermission() {

    if (!("Notification" in window)) {
        return false;
    }

    if (Notification.permission === "granted") {
        return true;
    }

    if (Notification.permission === "denied") {
        return false;
    }

    try {

        const permission =
            await Notification.requestPermission();

        return permission === "granted";

    } catch (error) {

        console.error(
            "Notification permission error:",
            error
        );

        return false;
    }
}

// ============================================================
// SEND LOW STOCK BROWSER NOTIFICATION
// ============================================================

async function sendLowStockBrowserNotification() {

    if (!lowStockItems.length) {
        return;
    }

    if (!("Notification" in window)) {
        return;
    }

    if (Notification.permission !== "granted") {
        return;
    }

    if (browserNotificationShown) {
        return;
    }

    browserNotificationShown = true;

    new Notification(
        "Inventory Low Stock Alert",
        {
            body:
                `${lowStockItems.length} inventory item(s) are below the minimum stock level.`,
            icon:
                "/static/favicon.ico"
        }
    );
}

// ============================================================
// LOAD INVENTORY
// ============================================================

async function loadInventory() {

    const categoryGrid =
        document.getElementById(
            "category-grid"
        );

    try {

        inventory =
            await apiRequest(
                "/api/inventory"
            );

        console.log(
            "Inventory loaded:",
            inventory
        );

        updateStatistics();

        renderCategories();

        await loadLowStockFromServer();

        await loadReorderRequests();

    } catch (error) {

        console.error(
            "Unable to load inventory:",
            error
        );

        if (categoryGrid) {

            categoryGrid.innerHTML = `

                <div class="error-message">

                    Unable to load inventory data.

                    <br>

                    <small>
                        ${escapeHtml(
                            error.message
                        )}
                    </small>

                </div>

            `;
        }
    }
}

// ============================================================
// LOAD LOW STOCK FROM SERVER
// ============================================================

async function loadLowStockFromServer() {

    try {

        lowStockItems =
            await apiRequest(
                "/api/inventory/low-stock"
            );

        showLowStockNotification();

        renderLowStock();

    } catch (error) {

        console.error(
            "Low stock loading error:",
            error
        );

        // Fallback to frontend calculation
        lowStockItems =
            inventory.filter(
                item =>
                    Number(item.stock) <=
                    Number(item.min_stock)
            );

        showLowStockNotification();

        renderLowStock();
    }
}

// ============================================================
// UPDATE DASHBOARD STATISTICS
// ============================================================

function updateStatistics() {

    const totalProducts =
        inventory.length;

    const lowStock =
        inventory.filter(
            item =>
                Number(item.stock) <=
                Number(item.min_stock)
        );

    const suppliers =
        new Set(
            inventory
                .map(
                    item =>
                        item.supplier
                )
                .filter(Boolean)
        );

    const categoriesSet =
        new Set(
            inventory
                .map(
                    item =>
                        item.category
                )
                .filter(Boolean)
        );

    const totalProductsElement =
        document.getElementById(
            "total-products"
        );

    const lowStockElement =
        document.getElementById(
            "low-stock-count"
        );

    const supplierElement =
        document.getElementById(
            "supplier-count"
        );

    const categoryElement =
        document.getElementById(
            "category-count"
        );

    if (totalProductsElement) {
        totalProductsElement.textContent =
            totalProducts;
    }

    if (lowStockElement) {
        lowStockElement.textContent =
            lowStock.length;
    }

    if (supplierElement) {
        supplierElement.textContent =
            suppliers.size;
    }

    if (categoryElement) {
        categoryElement.textContent =
            categoriesSet.size;
    }
}

// ============================================================
// RENDER CATEGORY CARDS
// ============================================================

function renderCategories() {

    const container =
        document.getElementById(
            "category-grid"
        );

    if (!container) {
        return;
    }

    const databaseCategories =
        [
            ...new Set(
                inventory
                    .map(
                        item =>
                            item.category
                    )
                    .filter(Boolean)
            )
        ].sort();

    if (!databaseCategories.length) {

        container.innerHTML = `

            <div class="empty-message">
                No inventory categories found.
            </div>

        `;

        return;
    }

    container.innerHTML = "";

    databaseCategories.forEach(
        category => {

            const items =
                inventory.filter(
                    item =>
                        item.category ===
                        category
                );

            const categoryInfo =
                categories.find(
                    item =>
                        item.name ===
                        category
                );

            const card =
                document.createElement(
                    "div"
                );

            card.className =
                "category-card";

            card.innerHTML = `

                <div class="category-icon">

                    ${
                        categoryInfo
                            ? categoryInfo.icon
                            : "📦"
                    }

                </div>

                <h4>
                    ${escapeHtml(category)}
                </h4>

                <p>

                    ${
                        categoryInfo
                            ? escapeHtml(
                                categoryInfo.description
                            )
                            : `${items.length} component${items.length === 1 ? "" : "s"}`
                    }

                </p>

                <div style="
                    margin-top:8px;
                    font-weight:600;
                    color:#2563eb;
                ">

                    ${items.length}
                    item${items.length === 1 ? "" : "s"}

                </div>

            `;

            card.addEventListener(
                "click",
                () => {

                    document
                        .querySelectorAll(
                            ".category-card"
                        )
                        .forEach(
                            element => {

                                element.classList.remove(
                                    "active"
                                );

                            }
                        );

                    card.classList.add(
                        "active"
                    );

                    showCategory(
                        category
                    );
                }
            );

            container.appendChild(
                card
            );
        }
    );
}

// ============================================================
// SHOW CATEGORY
// ============================================================

function showCategory(category) {

    const results =
        document.getElementById(
            "inventory-results"
        );

    const title =
        document.getElementById(
            "inventory-results-title"
        );

    const list =
        document.getElementById(
            "inventory-list"
        );

    if (!results || !title || !list) {
        return;
    }

    const items =
        inventory.filter(
            item =>
                item.category ===
                category
        );

    results.style.display =
        "block";

    title.textContent =
        `${category} Inventory`;

    renderInventoryItems(
        items,
        list
    );
}

// ============================================================
// RENDER INVENTORY ITEMS
// ============================================================

function renderInventoryItems(
    items,
    container
) {

    if (!container) {
        return;
    }

    if (!items.length) {

        container.innerHTML = `

            <div class="empty-message">
                No inventory items found.
            </div>

        `;

        return;
    }

    container.innerHTML = "";

    items.forEach(
        item => {

            const isLow =
                Number(item.stock) <=
                Number(item.min_stock);

            const element =
                document.createElement(
                    "div"
                );

            element.className =
                "inventory-item";

            element.style.border =
                isLow
                    ? "1px solid #fecaca"
                    : "1px solid #e2e8f0";

            element.innerHTML = `

                <div class="inventory-item-header">

                    <div class="inventory-item-name">

                        ${escapeHtml(
                            item.name
                        )}

                    </div>

                    <div class="${
                        isLow
                            ? "stock-low"
                            : "stock-normal"
                    }">

                        Stock:
                        ${escapeHtml(
                            item.stock
                        )}

                    </div>

                </div>

                <div class="inventory-item-details">

                    Category:
                    ${escapeHtml(
                        item.category ||
                        "N/A"
                    )}

                    <br>

                    Minimum stock:
                    ${escapeHtml(
                        item.min_stock
                    )}

                    <br>

                    Supplier:
                    ${escapeHtml(
                        item.supplier ||
                        "N/A"
                    )}

                </div>

                ${
                    isLow
                        ? `

                        <div style="
                            margin-top:10px;
                            padding:9px;
                            background:#fef2f2;
                            color:#b91c1c;
                            border-radius:8px;
                            font-weight:600;
                        ">

                            ⚠ LOW STOCK

                            <span style="
                                font-weight:400;
                                margin-left:5px;
                            ">

                                Only
                                ${escapeHtml(item.stock)}
                                left

                            </span>

                        </div>

                        `
                        : ""
                }

                <div style="
                    margin-top:12px;
                    display:flex;
                    gap:8px;
                    flex-wrap:wrap;
                ">

                    <button
                        onclick="openComponent(${JSON.stringify(item.name)})"
                        style="
                            padding:9px 13px;
                            border:1px solid #2563eb;
                            background:white;
                            color:#2563eb;
                            border-radius:7px;
                            cursor:pointer;
                        "
                    >
                        View Details
                    </button>

                    <button
                        onclick="reorderComponent(${JSON.stringify(item.name)})"
                        style="
                            padding:9px 13px;
                            border:none;
                            background:${
                                isLow
                                    ? "#dc2626"
                                    : "#2563eb"
                            };
                            color:white;
                            border-radius:7px;
                            cursor:pointer;
                            font-weight:600;
                        "
                    >
                        🔄 Reorder
                    </button>

                    ${
                        isLow
                            ? `

                            <button
                                onclick="notifyLowStock(${JSON.stringify(item.name)})"
                                style="
                                    padding:9px 13px;
                                    border:1px solid #f59e0b;
                                    background:#fffbeb;
                                    color:#92400e;
                                    border-radius:7px;
                                    cursor:pointer;
                                    font-weight:600;
                                "
                            >
                                🔔 Notify
                            </button>

                            `
                            : ""
                    }

                </div>

            `;

            container.appendChild(
                element
            );
        }
    );
}

// ============================================================
// LOW STOCK LIST
// ============================================================

function renderLowStock() {

    const container =
        document.getElementById(
            "low-stock-list"
        );

    if (!container) {
        return;
    }

    const items =
        lowStockItems.length
            ? lowStockItems
            : inventory.filter(
                item =>
                    Number(item.stock) <=
                    Number(item.min_stock)
            );

    if (!items.length) {

        container.innerHTML = `

            <div class="empty-message">

                ✓ No low-stock items.
                Inventory levels look good.

            </div>

        `;

        return;
    }

    renderInventoryItems(
        items,
        container
    );
}

// ============================================================
// SHOW ALL LOW STOCK
// ============================================================

function showAllLowStock() {

    const container =
        document.getElementById(
            "low-stock-list"
        );

    if (!container) {
        return;
    }

    container.scrollIntoView({
        behavior: "smooth",
        block: "start"
    });

    renderLowStock();
}

// ============================================================
// NOTIFY INDIVIDUAL COMPONENT
// ============================================================

async function notifyLowStock(
    componentName
) {

    const item =
        inventory.find(
            component =>
                component.name ===
                componentName
        );

    if (!item) {

        alert(
            "Component not found."
        );

        return;
    }

    const permissionGranted =
        await requestNotificationPermission();

    if (
        permissionGranted &&
        "Notification" in window
    ) {

        new Notification(
            "Low Stock: " +
            item.name,
            {
                body:
                    `Current stock: ${item.stock}. Minimum required: ${item.min_stock}.`,
                icon:
                    "/static/favicon.ico"
            }
        );

    } else {

        alert(
            `LOW STOCK\n\n` +
            `${item.name}\n\n` +
            `Current stock: ${item.stock}\n` +
            `Minimum stock: ${item.min_stock}`
        );
    }
}

// ============================================================
// NOTIFY ALL LOW STOCK
// ============================================================

async function notifyAllLowStock() {

    if (!lowStockItems.length) {

        alert(
            "There are no low-stock items."
        );

        return;
    }

    const permissionGranted =
        await requestNotificationPermission();

    if (!permissionGranted) {

        alert(
            `${lowStockItems.length} low-stock item(s) need attention.`
        );

        return;
    }

    lowStockItems.forEach(
        (item, index) => {

            setTimeout(
                () => {

                    new Notification(
                        "⚠ Low Stock: " +
                        item.name,
                        {
                            body:
                                `Stock: ${item.stock} | Minimum: ${item.min_stock}`,
                            icon:
                                "/static/favicon.ico"
                        }
                    );

                },
                index * 500
            );
        }
    );
}

// ============================================================
// OPEN COMPONENT FROM CHAT
// ============================================================

async function openComponent(
    componentName
) {

    try {

        const component =
            await apiRequest(
                `/api/component?name=${encodeURIComponent(
                    componentName
                )}`
            );

        const lowStock =
            Number(component.stock) <=
            Number(component.min_stock);

        const reorderQuantity =
            Math.max(
                Number(component.min_stock) -
                Number(component.stock),
                1
            );

        addBotMessage(`

            <div style="padding:8px;">

                <div style="
                    display:flex;
                    justify-content:space-between;
                    align-items:center;
                    gap:10px;
                ">

                    <h3 style="
                        margin:0;
                        color:#1e3a8a;
                    ">

                        ${escapeHtml(
                            component.name
                        )}

                    </h3>

                    <span style="
                        color:${
                            lowStock
                                ? "#dc2626"
                                : "#16a34a"
                        };
                        font-weight:600;
                    ">

                        ${
                            lowStock
                                ? "⚠ Low Stock"
                                : "✓ In Stock"
                        }

                    </span>

                </div>

                <hr style="
                    margin:16px 0;
                    border:none;
                    border-top:1px solid #dbeafe;
                ">

                <p>
                    <strong>
                        Current Stock:
                    </strong>

                    ${escapeHtml(
                        component.stock
                    )}
                    units
                </p>

                <p>
                    <strong>
                        Minimum Stock:
                    </strong>

                    ${escapeHtml(
                        component.min_stock
                    )}
                    units
                </p>

                <p>
                    <strong>
                        Supplier:
                    </strong>

                    ${escapeHtml(
                        component.supplier ||
                        "N/A"
                    )}
                </p>

                ${
                    component.last_updated
                        ? `
                            <p>
                                <strong>
                                    Last Updated:
                                </strong>

                                ${escapeHtml(
                                    component.last_updated
                                )}
                            </p>
                        `
                        : ""
                }

                <hr style="
                    margin:16px 0;
                    border:none;
                    border-top:1px solid #dbeafe;
                ">

                ${
                    lowStock
                        ? `

                            <div style="
                                background:#fef2f2;
                                border:1px solid #fecaca;
                                padding:12px;
                                border-radius:10px;
                                margin-bottom:16px;
                            ">

                                <strong style="
                                    color:#b91c1c;
                                ">
                                    ⚠ Low Stock Alert
                                </strong>

                                <br><br>

                                Stock is below the
                                minimum threshold.

                                <br><br>

                                Recommended reorder:

                                <strong>
                                    ${reorderQuantity}
                                    units
                                </strong>

                            </div>

                        `
                        : `

                            <div style="
                                background:#ecfdf5;
                                border:1px solid #bbf7d0;
                                padding:12px;
                                border-radius:10px;
                                margin-bottom:16px;
                            ">

                                <strong style="
                                    color:#166534;
                                ">
                                    ✓ Stock Level is Healthy
                                </strong>

                            </div>

                        `
                }

                <div style="
                    display:flex;
                    gap:10px;
                    flex-wrap:wrap;
                ">

                    <button
                        onclick="reorderComponent(${JSON.stringify(
                            component.name
                        )})"
                        style="
                            background:${
                                lowStock
                                    ? "#dc2626"
                                    : "#2563eb"
                            };
                            color:white;
                            border:none;
                            padding:11px 18px;
                            border-radius:8px;
                            cursor:pointer;
                            font-weight:600;
                        "
                    >
                        🔄 Reorder Now
                    </button>

                    ${
                        lowStock
                            ? `

                                <button
                                    onclick="notifyLowStock(${JSON.stringify(
                                        component.name
                                    )})"
                                    style="
                                        background:#f59e0b;
                                        color:white;
                                        border:none;
                                        padding:11px 18px;
                                        border-radius:8px;
                                        cursor:pointer;
                                        font-weight:600;
                                    "
                                >
                                    🔔 Notify
                                </button>

                            `
                            : ""
                    }

                </div>

            </div>

        `);

    } catch (error) {

        console.error(
            "Component loading error:",
            error
        );

        addBotMessage(
            "Unable to load component details."
        );
    }
}

// ============================================================
// CREATE REORDER REQUEST
// ============================================================

async function reorderComponent(
    componentName
) {

    try {

        const component =
            await apiRequest(
                `/api/component?name=${encodeURIComponent(
                    componentName
                )}`
            );

        const currentStock =
            Number(component.stock);

        const minimumStock =
            Number(component.min_stock);

        const recommendedQuantity =
            Math.max(
                minimumStock -
                currentStock,
                1
            );

        // ----------------------------------------------------
        // ASK USER FOR QUANTITY
        // ----------------------------------------------------

        const enteredQuantity =
            prompt(
                `Reorder ${component.name}\n\n` +
                `Current stock: ${currentStock}\n` +
                `Minimum stock: ${minimumStock}\n\n` +
                `Recommended quantity: ${recommendedQuantity}\n\n` +
                `Enter quantity to order:`,
                String(recommendedQuantity)
            );

        if (
            enteredQuantity === null
        ) {
            return;
        }

        const quantity =
            Number(enteredQuantity);

        if (
            !Number.isInteger(quantity) ||
            quantity <= 0
        ) {

            alert(
                "Please enter a valid quantity greater than 0."
            );

            return;
        }

        // ----------------------------------------------------
        // CONFIRM
        // ----------------------------------------------------

        const confirmed =
            confirm(
                `Create reorder request?\n\n` +
                `Component: ${component.name}\n` +
                `Supplier: ${component.supplier || "N/A"}\n` +
                `Current stock: ${currentStock}\n` +
                `Minimum stock: ${minimumStock}\n` +
                `Quantity to order: ${quantity}`
            );

        if (!confirmed) {
            return;
        }

        // ----------------------------------------------------
        // SEND TO BACKEND
        // ----------------------------------------------------

        const result =
            await apiRequest(
                "/api/reorders",
                {
                    method: "POST",

                    headers: {
                        "Content-Type":
                            "application/json"
                    },

                    body:
                        JSON.stringify({
                            item_id:
                                component.id,
                            quantity:
                                quantity
                        })
                }
            );

        const reorder =
            result.reorder ||
            result;

        if (
            !reorder ||
            !reorder.id
        ) {

            throw new Error(
                "Server returned an unexpected reorder response."
            );
        }

        // ----------------------------------------------------
        // SHOW SUCCESS
        // ----------------------------------------------------

        addBotMessage(`

            <div style="
                padding:16px;
                background:#ecfdf5;
                border:1px solid #bbf7d0;
                border-radius:10px;
            ">

                <strong style="
                    color:#166534;
                    font-size:16px;
                ">

                    ✓ Reorder Request Created

                </strong>

                <br><br>

                <strong>
                    Request ID:
                </strong>

                ${escapeHtml(
                    reorder.id
                )}

                <br>

                <strong>
                    Component:
                </strong>

                ${escapeHtml(
                    reorder.item_name ||
                    component.name
                )}

                <br>

                <strong>
                    Supplier:
                </strong>

                ${escapeHtml(
                    reorder.supplier ||
                    component.supplier ||
                    "N/A"
                )}

                <br>

                <strong>
                    Quantity:
                </strong>

                ${escapeHtml(
                    reorder.quantity ||
                    quantity
                )}
                units

                <br>

                <strong>
                    Status:
                </strong>

                <span style="
                    color:#ca8a04;
                    font-weight:700;
                ">

                    ${escapeHtml(
                        reorder.status ||
                        "Pending"
                    )}

                </span>

                <br><br>

                <small style="
                    color:#64748b;
                ">

                    Created:
                    ${escapeHtml(
                        reorder.created_at ||
                        "Now"
                    )}

                </small>

            </div>

        `);

        // ----------------------------------------------------
        // REFRESH REORDER REQUESTS
        // ----------------------------------------------------

        await loadReorderRequests();

        // Refresh low stock state
        await loadLowStockFromServer();

    } catch (error) {

        console.error(
            "Reorder error:",
            error
        );

        addBotMessage(`

            <div style="
                padding:12px;
                background:#fef2f2;
                border:1px solid #fecaca;
                border-radius:10px;
                color:#b91c1c;
            ">

                <strong>
                    Unable to create reorder request.
                </strong>

                <br><br>

                ${escapeHtml(
                    error.message
                )}

            </div>

        `);
    }
}

// ============================================================
// LOAD REORDER REQUESTS
// ============================================================

async function loadReorderRequests() {

    const container =
        document.getElementById(
            "reorder-list"
        );

    if (!container) {
        return;
    }

    try {

        const result =
            await apiRequest(
                "/api/reorders"
            );

        // Support either:
        // [...]
        // or { reorders: [...] }

        reorderRequests =
            Array.isArray(result)
                ? result
                : (
                    result.reorders ||
                    result.data ||
                    []
                );

        renderReorderRequests();

    } catch (error) {

        console.error(
            "Reorder requests loading error:",
            error
        );

        container.innerHTML = `

            <div class="empty-message">

                No reorder requests available.

                <br>

                <small style="color:#94a3b8;">

                    ${escapeHtml(
                        error.message
                    )}

                </small>

            </div>

        `;
    }
}

// ============================================================
// RENDER REORDER REQUESTS
// ============================================================

function renderReorderRequests() {

    const container =
        document.getElementById(
            "reorder-list"
        );

    if (!container) {
        return;
    }

    if (!reorderRequests.length) {

        container.innerHTML = `

            <div class="empty-message">

                No reorder requests yet.

                <br>

                Click
                <strong>🔄 Reorder</strong>
                on an inventory item to create one.

            </div>

        `;

        return;
    }

    container.innerHTML = "";

    reorderRequests.forEach(
        request => {

            const status =
                request.status ||
                "Pending";

            const statusLower =
                status.toLowerCase();

            let statusColor =
                "#ca8a04";

            let statusBackground =
                "#fefce8";

            if (
                statusLower ===
                "approved"
            ) {

                statusColor =
                    "#2563eb";

                statusBackground =
                    "#eff6ff";

            } else if (
                statusLower ===
                "completed" ||
                statusLower ===
                "received"
            ) {

                statusColor =
                    "#15803d";

                statusBackground =
                    "#f0fdf4";

            } else if (
                statusLower ===
                "cancelled" ||
                statusLower ===
                "rejected"
            ) {

                statusColor =
                    "#dc2626";

                statusBackground =
                    "#fef2f2";
            }

            const itemName =
                request.item_name ||
                request.name ||
                request.item?.name ||
                "Unknown Item";

            const supplier =
                request.supplier ||
                request.item?.supplier ||
                "N/A";

            const element =
                document.createElement(
                    "div"
                );

            element.className =
                "reorder-item";

            element.innerHTML = `

                <div class="reorder-header">

                    <strong>
                        ${escapeHtml(
                            itemName
                        )}
                    </strong>

                    <span style="
                        padding:5px 9px;
                        border-radius:20px;
                        background:${statusBackground};
                        color:${statusColor};
                        font-size:12px;
                        font-weight:700;
                    ">

                        ${escapeHtml(
                            status
                        )}

                    </span>

                </div>

                <div class="reorder-details">

                    <strong>
                        Request ID:
                    </strong>

                    ${escapeHtml(
                        request.id
                    )}

                    <br>

                    <strong>
                        Quantity:
                    </strong>

                    ${escapeHtml(
                        request.quantity
                    )}
                    units

                    <br>

                    <strong>
                        Supplier:
                    </strong>

                    ${escapeHtml(
                        supplier
                    )}

                    ${
                        request.created_at
                            ? `

                                <br>

                                <strong>
                                    Created:
                                </strong>

                                ${escapeHtml(
                                    request.created_at
                                )}

                            `
                            : ""
                    }

                </div>

            `;

            container.appendChild(
                element
            );
        }
    );
}

// ============================================================
// OPEN CATEGORY FROM CHAT
// ============================================================

async function openCategory(
    categoryName
) {

    addUserMessage(
        categoryName
    );

    try {

        const components =
            await apiRequest(
                `/api/components?category=${encodeURIComponent(
                    categoryName
                )}`
            );

        let html = `

            <strong>
                ${escapeHtml(
                    categoryName
                )} Inventory
            </strong>

            <br><br>

        `;

        if (
            !components ||
            components.length === 0
        ) {

            html += `

                <div style="
                    padding:12px;
                    border:1px solid #dbeafe;
                    border-radius:10px;
                ">

                    No inventory items found
                    in this category.

                </div>

            `;

            addBotMessage(html);

            return;
        }

        html += `
            Select a component to view
            stock details.
            <br><br>
        `;

        components.forEach(
            component => {

                const lowStock =
                    Number(component.stock) <=
                    Number(component.min_stock);

                html += `

                    <div
                        style="
                            margin-bottom:12px;
                            padding:12px;
                            border:1px solid ${
                                lowStock
                                    ? "#fecaca"
                                    : "#dbeafe"
                            };
                            border-radius:10px;
                        "
                    >

                        <div style="
                            display:flex;
                            justify-content:space-between;
                            align-items:center;
                            gap:10px;
                        ">

                            <strong>
                                ${escapeHtml(
                                    component.name
                                )}
                            </strong>

                            <span style="
                                color:${
                                    lowStock
                                        ? "#dc2626"
                                        : "#16a34a"
                                };
                                font-weight:600;
                            ">

                                Stock:
                                ${escapeHtml(
                                    component.stock
                                )}

                            </span>

                        </div>

                        <div style="
                            margin-top:6px;
                            color:#64748b;
                        ">

                            ${
                                lowStock
                                    ? "⚠ Low Stock"
                                    : "✓ In Stock"
                            }

                        </div>

                        <div style="
                            margin-top:10px;
                            display:flex;
                            gap:6px;
                            flex-wrap:wrap;
                        ">

                            <button
                                onclick="openComponent(${JSON.stringify(
                                    component.name
                                )})"
                                style="
                                    padding:7px 11px;
                                    border:1px solid #2563eb;
                                    background:white;
                                    color:#2563eb;
                                    border-radius:6px;
                                    cursor:pointer;
                                "
                            >
                                View
                            </button>

                            <button
                                onclick="reorderComponent(${JSON.stringify(
                                    component.name
                                )})"
                                style="
                                    padding:7px 11px;
                                    border:none;
                                    background:${
                                        lowStock
                                            ? "#dc2626"
                                            : "#2563eb"
                                    };
                                    color:white;
                                    border-radius:6px;
                                    cursor:pointer;
                                "
                            >
                                🔄 Reorder
                            </button>

                            ${
                                lowStock
                                    ? `

                                        <button
                                            onclick="notifyLowStock(${JSON.stringify(
                                                component.name
                                            )})"
                                            style="
                                                padding:7px 11px;
                                                border:none;
                                                background:#f59e0b;
                                                color:white;
                                                border-radius:6px;
                                                cursor:pointer;
                                            "
                                        >
                                            🔔 Notify
                                        </button>

                                    `
                                    : ""
                            }

                        </div>

                    </div>

                `;
            }
        );

        addBotMessage(
            html
        );

    } catch (error) {

        console.error(
            "Category loading error:",
            error
        );

        addBotMessage(
            "Unable to load inventory data."
        );
    }
}

// ============================================================
// CHAT / INVENTORY ASSISTANT
// ============================================================

async function sendMessage() {

    const input =
        document.getElementById(
            "message-input"
        );

    if (!input) {
        return;
    }

    const message =
        input.value.trim();

    if (!message) {
        return;
    }

    addUserMessage(
        message
    );

    input.value = "";

    try {

        const result =
            await apiRequest(
                "/api/chat",
                {
                    method: "POST",

                    headers: {
                        "Content-Type":
                            "application/json"
                    },

                    body:
                        JSON.stringify({
                            message:
                                message
                        })
                }
            );

        console.log(
            "Chat response:",
            result
        );

        // ----------------------------------------------------
        // COMPONENT
        // ----------------------------------------------------

        if (
            result.type ===
            "component"
        ) {

            if (
                result.data &&
                result.data.name
            ) {

                await openComponent(
                    result.data.name
                );

            } else {

                addBotMessage(
                    result.message ||
                    "Component information was not found."
                );
            }

            return;
        }

        // ----------------------------------------------------
        // LOW STOCK
        // ----------------------------------------------------

        if (
            result.type ===
            "low_stock"
        ) {

            let html = `

                <strong>
                    ⚠ Low Stock Items
                </strong>

                <br><br>

            `;

            if (
                !result.data ||
                result.data.length === 0
            ) {

                html +=
                    "No low-stock items found.";

                addBotMessage(
                    html
                );

                return;
            }

            result.data.forEach(
                component => {

                    html += `

                        <div style="
                            margin-bottom:12px;
                            padding:12px;
                            border:1px solid #fecaca;
                            border-radius:10px;
                            background:#fffafa;
                        ">

                            <div style="
                                display:flex;
                                justify-content:space-between;
                                gap:10px;
                            ">

                                <strong>
                                    ${escapeHtml(
                                        component.name
                                    )}
                                </strong>

                                <span style="
                                    color:#dc2626;
                                    font-weight:600;
                                ">

                                    Stock:
                                    ${escapeHtml(
                                        component.stock
                                    )}

                                </span>

                            </div>

                            <div>
                                Minimum:
                                ${escapeHtml(
                                    component.min_stock
                                )}
                                units
                            </div>

                            <div>
                                Supplier:
                                ${escapeHtml(
                                    component.supplier
                                )}
                            </div>

                            <br>

                            <button
                                onclick="reorderComponent(${JSON.stringify(
                                    component.name
                                )})"
                                style="
                                    background:#dc2626;
                                    color:white;
                                    border:none;
                                    padding:8px 12px;
                                    border-radius:7px;
                                    cursor:pointer;
                                    font-weight:600;
                                "
                            >
                                🔄 Reorder
                            </button>

                            <button
                                onclick="notifyLowStock(${JSON.stringify(
                                    component.name
                                )})"
                                style="
                                    background:#f59e0b;
                                    color:white;
                                    border:none;
                                    padding:8px 12px;
                                    border-radius:7px;
                                    cursor:pointer;
                                    margin-left:5px;
                                    font-weight:600;
                                "
                            >
                                🔔 Notify
                            </button>

                        </div>

                    `;
                }
            );

            addBotMessage(
                html
            );

            return;
        }

        // ----------------------------------------------------
        // CATEGORY
        // ----------------------------------------------------

        if (
            result.type ===
            "category"
        ) {

            let html = `

                <strong>
                    Category Components
                </strong>

                <br><br>

            `;

            if (
                !result.data ||
                result.data.length === 0
            ) {

                html +=
                    "No components found.";

                addBotMessage(
                    html
                );

                return;
            }

            result.data.forEach(
                component => {

                    const lowStock =
                        Number(component.stock) <=
                        Number(component.min_stock);

                    html += `

                        <div style="
                            margin-bottom:10px;
                            padding:10px;
                            border:1px solid #dbeafe;
                            border-radius:8px;
                        ">

                            <strong>
                                ${escapeHtml(
                                    component.name
                                )}
                            </strong>

                            <br>

                            Stock:
                            ${escapeHtml(
                                component.stock
                            )}
                            units

                            <span style="
                                margin-left:8px;
                                color:${
                                    lowStock
                                        ? "#dc2626"
                                        : "#16a34a"
                                };
                                font-weight:600;
                            ">

                                ${
                                    lowStock
                                        ? "⚠ Low Stock"
                                        : "✓ In Stock"
                                }

                            </span>

                            <br><br>

                            <button
                                onclick="openComponent(${JSON.stringify(
                                    component.name
                                )})"
                                style="
                                    padding:7px 11px;
                                    border:1px solid #2563eb;
                                    background:white;
                                    color:#2563eb;
                                    border-radius:6px;
                                    cursor:pointer;
                                "
                            >
                                View
                            </button>

                            <button
                                onclick="reorderComponent(${JSON.stringify(
                                    component.name
                                )})"
                                style="
                                    padding:7px 11px;
                                    border:none;
                                    background:${
                                        lowStock
                                            ? "#dc2626"
                                            : "#2563eb"
                                    };
                                    color:white;
                                    border-radius:6px;
                                    cursor:pointer;
                                    margin-left:5px;
                                "
                            >
                                🔄 Reorder
                            </button>

                            ${
                                lowStock
                                    ? `

                                        <button
                                            onclick="notifyLowStock(${JSON.stringify(
                                                component.name
                                            )})"
                                            style="
                                                padding:7px 11px;
                                                border:none;
                                                background:#f59e0b;
                                                color:white;
                                                border-radius:6px;
                                                cursor:pointer;
                                                margin-left:5px;
                                            "
                                        >
                                            🔔 Notify
                                        </button>

                                    `
                                    : ""
                            }

                        </div>

                    `;
                }
            );

            addBotMessage(
                html
            );

            return;
        }

        // ----------------------------------------------------
        // INVENTORY
        // ----------------------------------------------------

        if (
            result.type ===
            "inventory"
        ) {

            let html = `

                <strong>
                    Inventory
                </strong>

                <br><br>

                ${escapeHtml(
                    result.message || ""
                )}

                <br><br>

            `;

            if (result.data) {

                result.data.forEach(
                    component => {

                        const lowStock =
                            Number(component.stock) <=
                            Number(component.min_stock);

                        html += `

                            <div style="
                                padding:10px;
                                margin-bottom:8px;
                                border:1px solid ${
                                    lowStock
                                        ? "#fecaca"
                                        : "#dbeafe"
                                };
                                border-radius:8px;
                            ">

                                <strong>
                                    ${escapeHtml(
                                        component.name
                                    )}
                                </strong>

                                <br>

                                Stock:
                                ${escapeHtml(
                                    component.stock
                                )}

                                <div style="
                                    margin-top:8px;
                                ">

                                    <button
                                        onclick="reorderComponent(${JSON.stringify(
                                            component.name
                                        )})"
                                        style="
                                            background:${
                                                lowStock
                                                    ? "#dc2626"
                                                    : "#2563eb"
                                            };
                                            color:white;
                                            border:none;
                                            padding:5px 9px;
                                            border-radius:5px;
                                            cursor:pointer;
                                        "
                                    >
                                        🔄 Reorder
                                    </button>

                                    ${
                                        lowStock
                                            ? `

                                                <button
                                                    onclick="notifyLowStock(${JSON.stringify(
                                                        component.name
                                                    )})"
                                                    style="
                                                        background:#f59e0b;
                                                        color:white;
                                                        border:none;
                                                        padding:5px 9px;
                                                        border-radius:5px;
                                                        cursor:pointer;
                                                        margin-left:5px;
                                                    "
                                                >
                                                    🔔 Notify
                                                </button>

                                            `
                                            : ""
                                    }

                                </div>

                            </div>

                        `;
                    }
                );
            }

            addBotMessage(
                html
            );

            return;
        }

        // ----------------------------------------------------
        // DEFAULT
        // ----------------------------------------------------

        addBotMessage(
            result.message ||
            "I couldn't find an answer to that."
        );

    } catch (error) {

        console.error(
            "Chat error:",
            error
        );

        addBotMessage(`

            <div style="
                padding:12px;
                background:#fef2f2;
                border:1px solid #fecaca;
                border-radius:10px;
                color:#b91c1c;
            ">

                Unable to process your request.

                <br><br>

                ${escapeHtml(
                    error.message
                )}

            </div>

        `);
    }
}

// ============================================================
// ENTER KEY
// ============================================================

function setupMessageInput() {

    const input =
        document.getElementById(
            "message-input"
        );

    if (!input) {
        return;
    }

    input.addEventListener(
        "keydown",
        event => {

            if (
                event.key ===
                "Enter"
            ) {

                event.preventDefault();

                sendMessage();
            }
        }
    );
}

// ============================================================
// PAGE INITIALIZATION
// ============================================================

document.addEventListener(
    "DOMContentLoaded",
    async () => {

        console.log(
            "Inventory Dashboard initialized."
        );

        setupMessageInput();

        // Do not automatically ask for permission.
        // Notification permission is requested when
        // the user actually clicks Notify.
        await loadInventory();

        // Load reorder requests separately as well.
        await loadReorderRequests();
    }
);