import sqlite3
from .models import create_tables


class Database:
    def __init__(self, db_path):
        self.db_path = db_path

    def connect(self):

        return sqlite3.connect(self.db_path)

    def initialize(self):

        conn = self.connect()

        create_tables(conn)

        conn.execute("PRAGMA user_version = 1")

        conn.commit()
        conn.close()

    def get_user_version(self):

        conn = self.connect()
        cursor = conn.execute("PRAGMA user_version")
        version = cursor.fetchone()[0]
        conn.close()
        return version