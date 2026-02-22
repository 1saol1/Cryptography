import sqlite3
from .models import create_tables


class Database:
    def __init__(self, db_path):
        self.db_path = db_path
        self.connection = None  # сохраняем соединение

    def connect(self):
        if self.connection is None:
            self.connection = sqlite3.connect(self.db_path)
        return self.connection

    def initialize(self):
        conn = self.connect()
        create_tables(conn)
        conn.execute("PRAGMA user_version = 1")
        conn.commit()

    def get_user_version(self):
        conn = self.connect()
        cursor = conn.execute("PRAGMA user_version")
        version = cursor.fetchone()[0]
        return version