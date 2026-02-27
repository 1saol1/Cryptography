import sqlite3
from .models import create_tables


class Database:
    def __init__(self, db_path):
        self.db_path = db_path
        self._connection = None  # Сохраняем соединение, если нужно

    def connect(self):
        if self._connection is None:
            self._connection = sqlite3.connect(self.db_path)
        return self._connection

    def close(self):
        """Явно закрывает соединение с базой данных"""
        if self._connection:
            self._connection.close()
            self._connection = None

    def initialize(self):
        with self.connect() as conn:
            create_tables(conn)
            conn.execute("PRAGMA user_version = 1")

    def get_user_version(self):
        with self.connect() as conn:
            cursor = conn.execute("PRAGMA user_version")
            return cursor.fetchone()[0]

    # Добавляем поддержку контекстного менеджера
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()