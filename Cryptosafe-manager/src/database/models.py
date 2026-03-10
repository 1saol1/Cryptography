def create_tables(conn):
    cursor = conn.cursor()

    # Таблица для отслеживания версии БД (для миграций)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS db_version (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            version INTEGER NOT NULL,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Если таблица пустая, добавляем версию 1
    cursor.execute("SELECT COUNT(*) FROM db_version")
    if cursor.fetchone()[0] == 0:
        cursor.execute("INSERT INTO db_version (id, version) VALUES (1, 1)")

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

    # Таблица для хранения ключей и параметров
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS key_store (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            key_type TEXT NOT NULL,
            key_data BLOB NOT NULL,
            version INTEGER NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Таблица настроек
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS settings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL,
            value TEXT NOT NULL
        )
    """)

    conn.commit()