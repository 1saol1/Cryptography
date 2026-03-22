import sqlite3
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

CURRENT_DB_VERSION = 3  # обновляем до 3


class MigrationManager:
    def __init__(self, db_path: str):
        self.db_path = db_path

    def get_current_version(self) -> int:
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.execute("PRAGMA user_version")
            version = cursor.fetchone()[0]
            conn.close()
            return version
        except Exception as e:
            logger.error(f"Ошибка получения версии БД: {e}")
            return 0

    def migrate(self) -> bool:
        current_version = self.get_current_version()

        if current_version >= CURRENT_DB_VERSION:
            logger.info(f"БД уже актуальна (версия {current_version})")
            return True

        logger.info(f"Миграция БД с версии {current_version} на {CURRENT_DB_VERSION}")

        for version in range(current_version + 1, CURRENT_DB_VERSION + 1):
            if not self._apply_migration(version):
                logger.error(f"Миграция на версию {version} не удалась")
                return False

        return True

    def _apply_migration(self, target_version: int) -> bool:
        conn = None
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row

            logger.info(f"Применяю миграцию на версию {target_version}")

            if target_version == 1:
                self._migrate_to_v1(conn)
            elif target_version == 2:
                self._migrate_to_v2(conn)
            elif target_version == 3:
                self._migrate_to_v3(conn)

            conn.execute(f"PRAGMA user_version = {target_version}")
            conn.commit()

            logger.info(f"БД обновлена до версии {target_version}")
            return True

        except Exception as e:
            logger.error(f"Ошибка миграции на версию {target_version}: {e}")
            if conn:
                conn.rollback()
            return False
        finally:
            if conn:
                conn.close()

    def _migrate_to_v1(self, conn):
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

        logger.info("Таблицы vault_entries и audit_log созданы")

    def _migrate_to_v2(self, conn):
        cursor = conn.cursor()

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
                value TEXT NOT NULL
            )
        """)

        default_settings = [
            ('session_timeout', '60'),
            ('password_min_length', '12'),
            ('auto_lock_enabled', '1'),
            ('argon2_time', '3'),
            ('argon2_memory', '65536'),
            ('argon2_parallelism', '4'),
            ('pbkdf2_iterations', '100000'),
        ]

        for name, value in default_settings:
            cursor.execute("""
                INSERT OR IGNORE INTO settings (name, value)
                VALUES (?, ?)
            """, (name, value))

        cursor.execute("""
            UPDATE db_version SET version = 2, updated_at = CURRENT_TIMESTAMP
            WHERE id = 1
        """)

        logger.info("Таблицы key_store и settings добавлены")

    def _migrate_to_v3(self, conn):

        cursor = conn.cursor()

        logger.info("Начинаю миграцию на версию 3 (Спринт 3)...")


        cursor.execute("""
            CREATE TABLE IF NOT EXISTS vault_entries_new (
                id TEXT PRIMARY KEY,
                encrypted_data BLOB NOT NULL,
                created_at TIMESTAMP NOT NULL,
                updated_at TIMESTAMP NOT NULL,
                deleted_at TIMESTAMP,
                tags TEXT DEFAULT '[]'
            )
        """)

        cursor.execute("SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name='vault_entries'")
        old_table_exists = cursor.fetchone()[0] > 0

        if old_table_exists:
            cursor.execute("SELECT COUNT(*) FROM vault_entries")
            count = cursor.fetchone()[0]
            logger.info(f"Переношу {count} записей из старой таблицы...")


            cursor.execute("""
                SELECT id, title, username, encrypted_password, url, notes, tags, created_at, updated_at
                FROM vault_entries
            """)
            old_entries = cursor.fetchall()

            for entry in old_entries:
                full_data = {
                    'title': entry[1] or '',
                    'username': entry[2] or '',
                    'password': '',  # старый пароль зашифрован отдельно, но мы не можем его расшифровать
                    'url': entry[4] or '',
                    'notes': entry[5] or '',
                    'category': 'Общее',
                    'id': str(entry[0]),  # превращаем INTEGER в TEXT
                    'created_at': entry[7] if entry[7] else datetime.now().isoformat(),
                    'updated_at': entry[8] if entry[8] else datetime.now().isoformat(),
                    'version': 1
                }

                encrypted_blob = entry[3]

                tags = entry[6] if entry[6] else '[]'

                cursor.execute("""
                    INSERT INTO vault_entries_new (id, encrypted_data, created_at, updated_at, tags)
                    VALUES (?, ?, ?, ?, ?)
                """, (str(entry[0]), encrypted_blob, entry[7] or datetime.now(), entry[8] or datetime.now(), tags))

            logger.info(f"Перенесено {len(old_entries)} записей")

            cursor.execute("DROP TABLE IF EXISTS vault_entries_old")
            cursor.execute("ALTER TABLE vault_entries RENAME TO vault_entries_old")
            cursor.execute("ALTER TABLE vault_entries_new RENAME TO vault_entries")

            logger.info("Старая таблица сохранена как vault_entries_old")
        else:
            # Если старой таблицы нет, просто используем новую
            cursor.execute("ALTER TABLE vault_entries_new RENAME TO vault_entries")
            logger.info("Создана новая таблица vault_entries")

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_vault_created_at 
            ON vault_entries(created_at)
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_vault_updated_at 
            ON vault_entries(updated_at)
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

        cursor.execute("""
            UPDATE db_version SET version = 3, updated_at = CURRENT_TIMESTAMP
            WHERE id = 1
        """)

        logger.info("Миграция на версию 3 завершена!")
        logger.info("Добавлены:")
        logger.info("  - Новая структура vault_entries (encrypted_data вместо encrypted_password)")
        logger.info("  - Поле deleted_at для мягкого удаления")
        logger.info("  - Таблица deleted_entries для корзины")

    def backup_before_migration(self) -> str:
        import shutil
        from datetime import datetime

        backup_path = f"{self.db_path}.backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        shutil.copy2(self.db_path, backup_path)
        logger.info(f"Резервная копия создана: {backup_path}")
        return backup_path