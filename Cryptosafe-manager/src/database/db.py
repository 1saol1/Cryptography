import sqlite3
from pathlib import Path

Base_Dir = Path(__file__).resolve().parent
DB_PATH = Base_Dir / "cryptosafe.db" # создаёт файл

def get_connection():
    return sqlite3.connect(DB_PATH) # соединяет субд с файлом

def init_db():
    conn = get_connection()
    cursor = conn.cursor() # курсор выполняет функции бд и показывает результат

    cursor.execute("PRAGMA user_version = 1") # прагма специальная настройка, чтобы хранить версии схемы бд
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS vault_entries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            username TEXT,
            encrypted_password BLOB,
            notes BLOB,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS audit_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            event_type TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value BLOB
        )
    """)

    conn.commit()
    conn.close()

if __name__ == "__main__":
    init_db()
    print("Database initialized:", DB_PATH)