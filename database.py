import sqlite3

DATABASE = "inventory.db"

def get_connection():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS components (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL,
            category TEXT NOT NULL,
            stock INTEGER NOT NULL,
            min_stock INTEGER NOT NULL,
            supplier TEXT NOT NULL,
            last_updated TEXT NOT NULL
        )
        """
    )

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS reorder_requests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            component_name TEXT NOT NULL,
            supplier TEXT NOT NULL,
            quantity INTEGER NOT NULL,
            status TEXT NOT NULL
        )
        """
    )

    conn.commit()
    conn.close()

init_db()