def create_tables(conn):
    cursor = conn.cursor()

    # Таблица с записями хранилища паролей
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS vault_entries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            username TEXT,
            encrypted_password BLOB NOT NULL,
            url TEXT,
            notes TEXT,
            tags TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)


    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_vault_title
        ON vault_entries(title)
    """)

    # Таблица аудита действий
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS audit_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            action TEXT NOT NULL,
            timestamp TEXT DEFAULT CURRENT_TIMESTAMP,
            entry_id INTEGER,
            details TEXT,
            signature TEXT
        )
    """)


    cursor.execute("""
           CREATE TABLE IF NOT EXISTS key_store (
               id INTEGER PRIMARY KEY,
               key_type TEXT NOT NULL,
               key_data BLOB NOT NULL,
               version INTEGER NOT NULL,
               created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
           )
       """)


    cursor.execute("""
           CREATE TABLE IF NOT EXISTS settings (
               id INTEGER PRIMARY KEY,
               name TEXT UNIQUE NOT NULL,
               value TEXT NOT NULL
           )
       """)

    conn.commit()