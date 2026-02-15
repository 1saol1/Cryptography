import secrets

class KeyManager:
    """
    Заглушка менеджера ключей.
    Реальная криптография будет в Sprint 2.
    """

    def derive_key(self, password: str, salt: bytes) -> bytes:
        """
        В Sprint 1 просто преобразуем пароль в байты.
        """
        return password.encode("utf-8")

    def store_key(self, key: bytes):
        """
        Заглушка: в будущем будет безопасное хранилище.
        """
        self._key = key

    def load_key(self) -> bytes:
        """
        Возвращает сохранённый ключ (Sprint 1).
        """
        return getattr(self, "_key", None)
