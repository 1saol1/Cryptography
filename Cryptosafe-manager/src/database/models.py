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
            share_metadata TEXT,
            allow_copy INTEGER DEFAULT 1
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
            sequence_number INTEGER NOT NULL UNIQUE,
            previous_hash TEXT NOT NULL,
            event_type TEXT NOT NULL,
            severity TEXT NOT NULL,
            user_id TEXT NOT NULL,
            source TEXT NOT NULL,
            entry_data BLOB NOT NULL,
            entry_hash TEXT NOT NULL,
            signature TEXT NOT NULL,
            timestamp TEXT NOT NULL
        )
    """)

    cursor.execute("CREATE INDEX IF NOT EXISTS idx_audit_log_sequence ON audit_log(sequence_number)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_audit_log_timestamp ON audit_log(timestamp)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_audit_log_event_type ON audit_log(event_type)")

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS audit_public_key (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            public_key TEXT NOT NULL,
            algorithm TEXT NOT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
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

    # QR-3: Таблица публичных ключей контактов
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS contacts (
            contact_id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            email TEXT,
            public_key_pem TEXT NOT NULL DEFAULT '',
            public_key BLOB,
            public_key_fingerprint TEXT,
            algorithm TEXT NOT NULL DEFAULT 'RSA-2048',
            fingerprint TEXT NOT NULL DEFAULT '',
            status TEXT NOT NULL DEFAULT 'active',
            verified INTEGER NOT NULL DEFAULT 0,
            is_active INTEGER NOT NULL DEFAULT 1,
            has_public_key INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now')),
            revoked_at TEXT,
            revocation_reason TEXT,
            rotation_successor_id TEXT,
            last_used_at TEXT
        )
    """)

    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_contacts_status
        ON contacts(status)
    """)

    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_contacts_fingerprint
        ON contacts(fingerprint)
    """)

    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_contacts_name
        ON contacts(name)
    """)

    # DB-1: Таблица шерингов записей
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS shared_entries (
            share_id TEXT PRIMARY KEY,
            original_entry_id TEXT NOT NULL,
            sharer TEXT NOT NULL,
            recipient TEXT,
            encryption_method TEXT NOT NULL,
            permissions TEXT DEFAULT '{}',
            access_type TEXT DEFAULT 'read_only',
            shared_at TIMESTAMP NOT NULL DEFAULT (datetime('now')),
            expires_at TIMESTAMP NOT NULL,
            revoked_at TIMESTAMP,
            is_revoked INTEGER NOT NULL DEFAULT 0
        )
    """)

    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_shared_entries_entry_id
        ON shared_entries(original_entry_id)
    """)

    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_shared_entries_expires_at
        ON shared_entries(expires_at)
    """)

    # DB-2: История операций импорта/экспорта
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS import_export_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            operation_type TEXT NOT NULL,
            format TEXT NOT NULL,
            encryption_used TEXT,
            entry_count INTEGER NOT NULL DEFAULT 0,
            file_size_bytes INTEGER,
            file_path TEXT,
            checksum TEXT,
            checksum_algorithm TEXT DEFAULT 'SHA256',
            verification_status TEXT DEFAULT 'unverified',
            success INTEGER NOT NULL DEFAULT 1,
            error_message TEXT,
            performed_by TEXT,
            performed_at TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """)

    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_ie_history_operation
        ON import_export_history(operation_type)
    """)

    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_ie_history_performed_at
        ON import_export_history(performed_at)
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS settings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            setting_key TEXT UNIQUE,
            setting_value TEXT,
            encrypted INTEGER DEFAULT 0,
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
            ('clipboard_security_level', 'standard', 'Уровень безопасности: standard/secure/paranoid'),
            ('clipboard_monitor_enabled', 'true', 'Включить мониторинг буфера обмена'),
            ('clipboard_monitor_interval', '1', 'Интервал проверки буфера (секунды)'),
            ('clipboard_suspicious_threshold', '3', 'Порог подозрительных действий'),
            ('clipboard_notifications_enabled', 'true', 'Показывать всплывающие уведомления'),
            ('clipboard_warn_before_clear', '5', 'Предупреждение за N секунд до очистки'),
            ('clipboard_whitelist', '[]', 'Белый список приложений (JSON)'),
            ('theme', 'system', 'Тема оформления (system/light/dark)'),
            ('language', 'ru', 'Язык интерфейса'),
            ('trash_retention_days', '30', 'Сколько дней хранить удаленные записи'),
            ('default_password_length', '16', 'Длина пароля по умолчанию'),
            ('password_exclude_ambiguous', 'true', 'Исключать неоднозначные символы')
        ]

        for setting_key, setting_value, description in default_settings:
            cursor.execute(
                "INSERT INTO settings (setting_key, setting_value, description) VALUES (?, ?, ?)",
                (setting_key, setting_value, description)
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
    cursor.execute("SELECT setting_value FROM settings WHERE setting_key = ?", (name,))
    result = cursor.fetchone()
    return result[0] if result else default


def get_all_settings(conn) -> dict:
    cursor = conn.cursor()
    cursor.execute("SELECT setting_key, setting_value, description FROM settings ORDER BY setting_key")
    rows = cursor.fetchall()

    settings = {
        'values': {row[0]: row[1] for row in rows},
        'descriptions': {row[0]: row[2] for row in rows}
    }
    return settings


def update_setting(conn, name: str, value: str) -> bool:
    cursor = conn.cursor()
    cursor.execute(
        "UPDATE settings SET setting_value = ?, updated_at = CURRENT_TIMESTAMP WHERE setting_key = ?",
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
            "UPDATE settings SET setting_value = ?, updated_at = CURRENT_TIMESTAMP WHERE setting_key = ?",
            (value, name)
        )
        if cursor.rowcount > 0:
            success_count += 1

    conn.commit()
    logger.info(f"Обновлено {success_count} настроек")
    return success_count


def reset_setting_to_default(conn, name: str) -> bool:
    default_settings = {
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
        'clipboard_security_level': 'standard',
        'clipboard_monitor_enabled': 'true',
        'clipboard_monitor_interval': '1',
        'clipboard_suspicious_threshold': '3',
        'clipboard_notifications_enabled': 'true',
        'clipboard_warn_before_clear': '5',
        'clipboard_whitelist': '[]',
        'theme': 'system',
        'language': 'ru',
        'trash_retention_days': '30',
        'default_password_length': '16',
        'password_exclude_ambiguous': 'true'
    }

    if name in default_settings:
        return update_setting(conn, name, default_settings[name])
    return False


def get_settings_group(conn, group_prefix: str) -> dict:
    cursor = conn.cursor()
    cursor.execute(
        "SELECT setting_key, setting_value FROM settings WHERE setting_key LIKE ? ORDER BY setting_key",
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

# ==================== QR-3: ФУНКЦИИ ДЛЯ РАБОТЫ С КОНТАКТАМИ ====================

def get_all_contacts(conn, include_revoked: bool = False) -> list:
    """QR-3: Получение всех контактов из БД."""
    cursor = conn.cursor()
    if include_revoked:
        cursor.execute(
            "SELECT * FROM contacts ORDER BY created_at DESC"
        )
    else:
        cursor.execute(
            "SELECT * FROM contacts WHERE status = 'active' ORDER BY created_at DESC"
        )
    return cursor.fetchall()


def get_contact_by_id(conn, contact_id: str) -> tuple:
    """QR-3: Получение контакта по ID."""
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM contacts WHERE contact_id = ?", (contact_id,))
    return cursor.fetchone()


def get_contact_by_fingerprint(conn, fingerprint: str) -> tuple:
    """QR-3: Поиск контакта по fingerprint ключа."""
    cursor = conn.cursor()
    cursor.execute(
        "SELECT * FROM contacts WHERE fingerprint = ? AND status = 'active'",
        (fingerprint,)
    )
    return cursor.fetchone()


def update_contact_status(conn, contact_id: str, status: str,
                           revoked_at: str = None,
                           revocation_reason: str = None,
                           rotation_successor_id: str = None) -> bool:
    """QR-3: Обновление статуса контакта (revoke / rotate)."""
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE contacts
        SET status = ?,
            revoked_at = ?,
            revocation_reason = ?,
            rotation_successor_id = ?,
            updated_at = datetime('now')
        WHERE contact_id = ?
    """, (status, revoked_at, revocation_reason, rotation_successor_id, contact_id))
    conn.commit()
    if cursor.rowcount > 0:
        logger.info(f"QR-3: Контакт {contact_id} — статус обновлён на '{status}'")
        return True
    return False


def set_contact_verified(conn, contact_id: str, verified: bool = True) -> bool:
    """QR-3: Отметить fingerprint контакта как верифицированный."""
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE contacts
        SET verified = ?, updated_at = datetime('now')
        WHERE contact_id = ?
    """, (int(verified), contact_id))
    conn.commit()
    if cursor.rowcount > 0:
        logger.info(f"QR-3: Контакт {contact_id} — verified={verified}")
        return True
    return False