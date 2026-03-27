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
            id TEXT PRIMARY KEY,
            encrypted_data BLOB NOT NULL,
            created_at TIMESTAMP NOT NULL,
            updated_at TIMESTAMP NOT NULL,
            deleted_at TIMESTAMP,
            tags TEXT DEFAULT '[]',
            totp_secret TEXT,
            share_metadata TEXT
        )
    """)

    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_vault_created_at 
        ON vault_entries(created_at)
    """)

    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_vault_updated_at 
        ON vault_entries(updated_at)
    """)

    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_vault_deleted_at 
        ON vault_entries(deleted_at)
    """)

    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_vault_tags 
        ON vault_entries(tags)
    """)

    cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_vault_totp 
            ON vault_entries(totp_secret)
        """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS audit_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            action TEXT NOT NULL,
            timestamp TEXT DEFAULT CURRENT_TIMESTAMP,
            entry_id TEXT,
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

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS settings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL,
            value TEXT NOT NULL,
            description TEXT,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS deleted_entries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            original_id TEXT NOT NULL,
            encrypted_data BLOB NOT NULL,
            deleted_at TIMESTAMP NOT NULL,
            expires_at TIMESTAMP NOT NULL
        )
    """)

    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_deleted_original_id 
        ON deleted_entries(original_id)
    """)

    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_deleted_expires_at 
        ON deleted_entries(expires_at)
    """)

    cursor.execute("SELECT COUNT(*) FROM settings")
    if cursor.fetchone()[0] == 0:
        default_settings = [
            ('password_min_length', '12', 'Минимальная длина пароля'),
            ('password_require_upper', 'true', 'Требовать заглавные буквы'),
            ('password_require_lower', 'true', 'Требовать строчные буквы'),
            ('password_require_digit', 'true', 'Требовать цифры'),
            ('password_require_special', 'true', 'Требовать спецсимволы'),
            ('argon2_time_cost', '3', 'Количество итераций Argon2'),
            ('argon2_memory_cost', '65536', 'Используемая память Argon2 (KB)'),
            ('argon2_parallelism', '4', 'Количество потоков Argon2'),
            ('pbkdf2_iterations', '600000', 'Количество итераций PBKDF2'),
            ('auto_lock_timeout', '60', 'Таймаут авто-блокировки (минуты)'),
            ('session_timeout', '60', 'Максимальное время сессии (минуты)'),
            ('clipboard_clear_timeout', '30', 'Время очистки буфера обмена (секунды)'),
            ('theme', 'system', 'Тема оформления (system/light/dark)'),
            ('language', 'ru', 'Язык интерфейса'),
            ('trash_retention_days', '30', 'Сколько дней хранить удаленные записи'),
            ('default_password_length', '16', 'Длина пароля по умолчанию'),
            ('password_exclude_ambiguous', 'true', 'Исключать неоднозначные символы')
        ]

        for name, value, description in default_settings:
            cursor.execute(
                "INSERT INTO settings (name, value, description) VALUES (?, ?, ?)",
                (name, value, description)
            )
        logger.info(f"Добавлено {len(default_settings)} настроек по умолчанию")

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


def update_setting(conn, name: str, value: str) -> bool:
    cursor = conn.cursor()
    cursor.execute(
        "UPDATE settings SET value = ?, updated_at = CURRENT_TIMESTAMP WHERE name = ?",
        (value, name)
    )
    conn.commit()
    if cursor.rowcount > 0:
        logger.info(f"Обновлена настройка {name} = {value}")
        return True
    return False


def update_settings(conn, settings_dict: dict) -> int:
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
    logger.info(f"Обновлено {success_count} настроек")
    return success_count


def reset_setting_to_default(conn, name: str) -> bool:
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
        'language': 'ru',
        'trash_retention_days': '30',
        'default_password_length': '16',
        'password_exclude_ambiguous': 'true'
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
    rows = cursor.fetchall()
    return {row[0]: row[1] for row in rows}


def clean_expired_trash(conn):
    cursor = conn.cursor()
    cursor.execute(
        "DELETE FROM deleted_entries WHERE expires_at <= datetime('now')"
    )
    deleted_count = cursor.rowcount
    conn.commit()
    if deleted_count > 0:
        logger.info(f"Очищено {deleted_count} записей из корзины")
    return deleted_count


def get_trash_entries(conn) -> list:
    cursor = conn.cursor()
    cursor.execute(
        "SELECT original_id, deleted_at, expires_at FROM deleted_entries ORDER BY deleted_at DESC"
    )
    return cursor.fetchall()


def restore_from_trash(conn, original_id: str) -> bool:
    cursor = conn.cursor()

    cursor.execute(
        "SELECT encrypted_data FROM deleted_entries WHERE original_id = ?",
        (original_id,)
    )
    row = cursor.fetchone()

    if not row:
        return False

    cursor.execute(
        "UPDATE vault_entries SET deleted_at = NULL WHERE id = ?",
        (original_id,)
    )

    cursor.execute(
        "DELETE FROM deleted_entries WHERE original_id = ?",
        (original_id,)
    )

    conn.commit()
    logger.info(f"Запись {original_id} восстановлена из корзины")
    return True