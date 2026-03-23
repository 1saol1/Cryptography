import sqlite3
import logging
from .models import create_tables
from .migrations import MigrationManager

logger = logging.getLogger(__name__)


class Database:
    def __init__(self, db_path):
        self.db_path = db_path
        self._connection = None
        self._migrator = MigrationManager(db_path)

    def connect(self):
        if self._connection is None:
            self._connection = sqlite3.connect(self.db_path)
        return self._connection

    def close(self):
        if self._connection:
            self._connection.close()
            self._connection = None

    def initialize(self):
        conn = self.connect()

        create_tables(conn)
        conn.commit()

        # Получаем текущую версию
        current_version = self.get_user_version()
        logger.info(f"Текущая версия БД: {current_version}")

        if current_version > 0 and current_version < 3:
            logger.info(f"Применяем миграции с версии {current_version} на 3")
            success = self._migrator.migrate()
            if success:
                from .migrations import CURRENT_DB_VERSION
                conn.execute(f"PRAGMA user_version = {CURRENT_DB_VERSION}")
                conn.commit()
                logger.info(f"БД обновлена до версии {CURRENT_DB_VERSION}")
            else:
                logger.error("Ошибка при миграции базы данных")
                raise Exception("Не удалось выполнить миграцию БД")
        else:
            logger.info(f"База данных версии {current_version}, миграции не требуются")

        conn.commit()
        logger.info("База данных инициализирована")

    def get_user_version(self):
        try:
            conn = self.connect()
            cursor = conn.execute("PRAGMA user_version")
            return cursor.fetchone()[0]
        except Exception:
            return 0

    def get_db_version(self):
        try:
            conn = self.connect()
            cursor = conn.execute(
                "SELECT version FROM db_version WHERE id = 1"
            )
            row = cursor.fetchone()
            if row:
                return row[0]
        except sqlite3.OperationalError:
            pass
        return self.get_user_version()

    def execute(self, query: str, params: tuple = ()):
        conn = self.connect()
        cursor = conn.cursor()
        cursor.execute(query, params)
        conn.commit()
        return cursor

    def execute_many(self, query: str, params_list: list):
        conn = self.connect()
        cursor = conn.cursor()
        cursor.executemany(query, params_list)
        conn.commit()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()