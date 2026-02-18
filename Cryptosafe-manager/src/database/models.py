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

    # Индекс для ускорения поиска по названию
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

    # Таблица настроек приложения
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS settings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            setting_key TEXT UNIQUE,
            setting_value TEXT,
            encrypted INTEGER DEFAULT 0
        )
    """)

    # Таблица для хранения информации о ключах (Sprint 2)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS key_store (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            key_type TEXT,
            salt BLOB,
            hash BLOB,
            params TEXT
        )
    """)

    conn.commit()