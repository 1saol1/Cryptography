import logging

logger = logging.getLogger(__name__)


def create_tables(conn):
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS db_version (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            version INTEGER NOT NULL,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)

    cursor.execute("SELECT COUNT(*) FROM db_version")
    if cursor.fetchone()[0] == 0:
        cursor.execute("INSERT INTO db_version (id, version) VALUES (1, 1)")
        logger.info("Установлена начальная версия БД 1")

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
            value TEXT NOT NULL,
            description TEXT,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # настройки по умолчанию при первом запуске
    cursor.execute("SELECT COUNT(*) FROM settings")
    if cursor.fetchone()[0] == 0:
        default_settings = [
            # конфигурация политики паролей
            ('password_min_length', '12', 'Минимальная длина пароля'),
            ('password_require_upper', 'true', 'Требовать заглавные буквы'),
            ('password_require_lower', 'true', 'Требовать строчные буквы'),
            ('password_require_digit', 'true', 'Требовать цифры'),
            ('password_require_special', 'true', 'Требовать спецсимволы'),

            # параметры формирования ключей
            ('argon2_time_cost', '3', 'Количество итераций Argon2'),
            ('argon2_memory_cost', '65536', 'Используемая память Argon2 (KB)'),
            ('argon2_parallelism', '4', 'Количество потоков Argon2'),
            ('pbkdf2_iterations', '600000', 'Количество итераций PBKDF2'),

            # таймаут авто-блокировки
            ('auto_lock_timeout', '60', 'Таймаут авто-блокировки (минуты)'),
            ('session_timeout', '60', 'Максимальное время сессии (минуты)'),

            ('clipboard_clear_timeout', '30', 'Время очистки буфера обмена (секунды)'),
            ('theme', 'system', 'Тема оформления (system/light/dark)'),
            ('language', 'ru', 'Язык интерфейса')
        ]

        for name, value, description in default_settings:
            cursor.execute(
                "INSERT INTO settings (name, value, description) VALUES (?, ?, ?)",
                (name, value, description)
            )
        logger.info(f"DB-2: Добавлено {len(default_settings)} настроек по умолчанию")

    conn.commit()
    logger.info("Все таблицы успешно созданы")


def get_db_version(conn) -> int:
    cursor = conn.cursor()
    cursor.execute("SELECT version FROM db_version WHERE id = 1")
    result = cursor.fetchone()
    return result[0] if result else 1


def update_db_version(conn, new_version: int):
    cursor = conn.cursor()
    cursor.execute(
        "UPDATE db_version SET version = ?, updated_at = CURRENT_TIMESTAMP WHERE id = 1",
        (new_version,)
    )
    conn.commit()
    logger.info(f"Версия БД обновлена до {new_version}")


# функции для работы с настройками

def get_setting(conn, name: str, default=None):

    cursor = conn.cursor()
    cursor.execute("SELECT value FROM settings WHERE name = ?", (name,))
    result = cursor.fetchone()
    return result[0] if result else default


def get_all_settings(conn) -> dict:

    cursor = conn.cursor()
    cursor.execute("SELECT name, value, description FROM settings ORDER BY name")
    rows = cursor.fetchall()

    settings = {
        'values': {row[0]: row[1] for row in rows},
        'descriptions': {row[0]: row[2] for row in rows}
    }
    return settings


def update_setting(conn, name: str, value: str):

    cursor = conn.cursor()
    cursor.execute(
        "UPDATE settings SET value = ?, updated_at = CURRENT_TIMESTAMP WHERE name = ?",
        (value, name)
    )
    conn.commit()
    logger.info(f"DB-2: Обновлена настройка {name} = {value}")
    return cursor.rowcount > 0


def update_settings(conn, settings_dict: dict):

    cursor = conn.cursor()
    success_count = 0

    for name, value in settings_dict.items():
        cursor.execute(
            "UPDATE settings SET value = ?, updated_at = CURRENT_TIMESTAMP WHERE name = ?",
            (value, name)
        )
        if cursor.rowcount > 0:
            success_count += 1

    conn.commit()
    logger.info(f"DB-2: Обновлено {success_count} настроек")
    return success_count


def reset_setting_to_default(conn, name: str):
    defaults = {
        'password_min_length': '12',
        'password_require_upper': 'true',
        'password_require_lower': 'true',
        'password_require_digit': 'true',
        'password_require_special': 'true',
        'argon2_time_cost': '3',
        'argon2_memory_cost': '65536',
        'argon2_parallelism': '4',
        'pbkdf2_iterations': '600000',
        'auto_lock_timeout': '60',
        'session_timeout': '60',
        'clipboard_clear_timeout': '30',
        'theme': 'system',
        'language': 'ru'
    }

    if name in defaults:
        return update_setting(conn, name, defaults[name])
    return False


def get_settings_group(conn, group_prefix: str) -> dict:
    cursor = conn.cursor()
    cursor.execute(
        "SELECT name, value FROM settings WHERE name LIKE ? ORDER BY name",
        (f"{group_prefix}%",)
    )
    return {row[0]: row[1] for row in rows}