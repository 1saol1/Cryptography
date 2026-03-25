import sqlite3
import logging
import threading
from queue import Queue
from .models import create_tables
from .migrations import MigrationManager

logger = logging.getLogger(__name__)


class ConnectionPool:

    def __init__(self, db_path: str, max_connections: int = 5):
        self.db_path = db_path
        self.max_connections = max_connections
        self._pool = Queue(maxsize=max_connections)
        self._lock = threading.Lock()
        self._created = 0

        self._initialize_pool()

    def _initialize_pool(self):
        for _ in range(self.max_connections):
            self._create_connection()

    def _create_connection(self):
        conn = sqlite3.connect(
            self.db_path,
            check_same_thread=False,
            timeout=10.0
        )
        conn.row_factory = sqlite3.Row
        self._pool.put(conn)
        self._created += 1

    def get_connection(self):
        try:
            conn = self._pool.get(timeout=5)
            return conn
        except:
            logger.error("Таймаут при получении соединения из пула")
            raise

    def return_connection(self, conn):
        self._pool.put(conn)

    def close_all(self):
        while not self._pool.empty():
            try:
                conn = self._pool.get_nowait()
                conn.close()
            except:
                pass


class Database:
    def __init__(self, db_path):
        self.db_path = db_path
        self._pool = ConnectionPool(db_path)
        self._migrator = MigrationManager(db_path)
        self._local = threading.local()

    def get_connection(self):
        if not hasattr(self._local, 'connection'):
            self._local.connection = self._pool.get_connection()
        return self._local.connection

    def return_connection(self):
        if hasattr(self._local, 'connection'):
            self._pool.return_connection(self._local.connection)
            delattr(self._local, 'connection')

    def initialize(self):
        conn = self.get_connection()

        create_tables(conn)
        conn.commit()

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
        self.return_connection()
        logger.info("База данных инициализирована")

    def get_user_version(self):
        try:
            conn = self.get_connection()
            cursor = conn.execute("PRAGMA user_version")
            version = cursor.fetchone()[0]
            self.return_connection()
            return version
        except Exception:
            return 0

    def get_db_version(self):
        try:
            conn = self.get_connection()
            cursor = conn.execute("SELECT version FROM db_version WHERE id = 1")
            row = cursor.fetchone()
            self.return_connection()
            if row:
                return row[0]
        except sqlite3.OperationalError:
            pass
        return self.get_user_version()

    def execute(self, query: str, params: tuple = ()):
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute(query, params)
        conn.commit()
        self.return_connection()
        return cursor

    def execute_many(self, query: str, params_list: list):
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.executemany(query, params_list)
        conn.commit()
        self.return_connection()

    def close(self):
        self._pool.close_all()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()