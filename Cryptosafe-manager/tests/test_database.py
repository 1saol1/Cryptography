import sqlite3
from src.database.db import Database


def test_database_initialization():
    # используем временную БД в памяти
    db = Database(":memory:")
    db.initialize()

    conn = db.connect()
    cursor = conn.cursor()

    # проверяем, что таблицы созданы
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
    tables = cursor.fetchall()

    assert len(tables) > 0