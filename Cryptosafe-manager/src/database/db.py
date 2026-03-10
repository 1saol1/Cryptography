import sqlite3
import logging
from .models import create_tables
from .migrations import MigrationManager

logger = logging.getLogger(__name__)


class Database:
    def __init__(self, db_path):
        self.db_path = db_path
        self._connection = None  # Сохраняем соединение, если нужно
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
        with self.connect() as conn:
            # Сначала создаем базовые таблицы
            create_tables(conn)

            # Проверяем и применяем миграции
            current_version = self.get_user_version()
            logger.info(f"Текущая версия БД: {current_version}")

            # Запускаем миграции
            success = self._migrator.migrate()
            if success:
                # Обновляем PRAGMA user_version до текущей версии
                from .migrations import CURRENT_DB_VERSION
                conn.execute(f"PRAGMA user_version = {CURRENT_DB_VERSION}")
                logger.info(f"БД обновлена до версии {CURRENT_DB_VERSION}")
            else:
                logger.error("Ошибка при миграции базы данных")

            conn.commit()

    def get_user_version(self):
        with self.connect() as conn:
            cursor = conn.execute("PRAGMA user_version")
            return cursor.fetchone()[0]

    def get_db_version(self):
        try:
            with self.connect() as conn:
                cursor = conn.execute(
                    "SELECT version FROM db_version WHERE id = 1"
                )
                row = cursor.fetchone()
                if row:
                    return row[0]
        except sqlite3.OperationalError:
            # Таблица db_version еще не создана
            pass

        # Возвращаем из PRAGMA как запасной вариант
        return self.get_user_version()

    def execute(self, query: str, params: tuple = ()):
        with self.connect() as conn:
            cursor = conn.cursor()
            cursor.execute(query, params)
            conn.commit()
            return cursor.fetchall()

    def execute_many(self, query: str, params_list: list):
        with self.connect() as conn:
            cursor = conn.cursor()
            cursor.executemany(query, params_list)
            conn.commit()

    # Добавляем поддержку контекстного менеджера
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()