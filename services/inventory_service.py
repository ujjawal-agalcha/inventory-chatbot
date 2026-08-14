from database import get_connection

# Get all inventory items
def get_all_inventory(_db=None):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM components ORDER BY name")
    rows = cursor.fetchall()
    conn.close()
    return rows

# Get one component by exact name
def get_component(_db=None, name=None):
    if name is None:
        name = _db
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT * FROM components WHERE LOWER(name)=LOWER(?)",
        (name,),
    )
    row = cursor.fetchone()
    conn.close()
    return row

# Search inventory
def search_inventory(_db=None, query=None):
    if query is None:
        query = _db
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT * FROM components
        WHERE LOWER(name) LIKE LOWER(?)
           OR LOWER(category) LIKE LOWER(?)
           OR LOWER(supplier) LIKE LOWER(?)
        ORDER BY name
        """,
        (f"%{query}%", f"%{query}%", f"%{query}%")
    )
    rows = cursor.fetchall()
    conn.close()
    return rows

# Low stock items
def get_low_stock_items(_db=None):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT * FROM components WHERE stock <= min_stock ORDER BY stock ASC"
    )
    rows = cursor.fetchall()
    conn.close()
    return rows

# Inventory statistics
def get_inventory_stats(_db=None):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT COUNT(*) FROM components")
    total_components = cursor.fetchone()[0]

    cursor.execute("SELECT SUM(stock) FROM components")
    total_units = cursor.fetchone()[0] or 0

    cursor.execute("SELECT COUNT(*) FROM components WHERE stock <= min_stock")
    low_stock = cursor.fetchone()[0]

    conn.close()

    return {
        "total_components": total_components,
        "total_units": total_units,
        "low_stock": low_stock,
    }

# Create reorder request
def create_reorder_request(_db=None, component_name=None, quantity=None):
    if quantity is None:
        quantity = component_name
        component_name = _db

    component = get_component(component_name)

    if not component:
        return False

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        INSERT INTO reorder_requests
        (component_name, supplier, quantity, status)
        VALUES (?, ?, ?, ?)
        """,
        (
            component["name"],
            component["supplier"],
            quantity,
            "Pending",
        ),
    )

    conn.commit()
    conn.close()

    return True

# Get reorder requests
def get_reorder_requests(_db=None):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM reorder_requests ORDER BY id DESC")
    rows = cursor.fetchall()
    conn.close()
    return rows

# Update stock
def update_stock(_db=None, component_name=None, new_stock=None):
    if new_stock is None:
        new_stock = component_name
        component_name = _db

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        "UPDATE components SET stock=? WHERE LOWER(name)=LOWER(?)",
        (new_stock, component_name),
    )

    conn.commit()
    updated = cursor.rowcount > 0
    conn.close()

    return updated