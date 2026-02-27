import os
import tempfile
from src.database.db import Database
from src.core.crypto.authentication import AuthenticationService


def test_initial_setup_process():
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)

    # Теперь это будет работать! Соединение закроется автоматически
    with Database(path) as db:
        db.initialize()

        auth = AuthenticationService(path)

        assert auth.is_initialized() is False

        auth.register("testpassword")

        assert auth.is_initialized() is True

    # Файл можно удалить, потому что соединение закрыто
    os.remove(path)