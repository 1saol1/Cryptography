import os
import tempfile
from src.database.db import Database


def test_database_initialization():
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)

    db = None
    try:
        db = Database(path)
        db.initialize()

        version = db.get_user_version()
        assert version == 1

        # Явно закрываем соединение с БД
        db.close()

    finally:
        # Убеждаемся, что соединение закрыто перед удалением
        if db:
            db.close()
        os.remove(path)