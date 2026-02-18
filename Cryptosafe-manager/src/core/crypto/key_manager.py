import secrets

class KeyManager:

    def derive_key(self, password: str, salt: bytes) -> bytes:

        return password.encode("utf-8")

    def store_key(self, key: bytes):

        self._key = key

    def load_key(self) -> bytes:

        return getattr(self, "_key", None)
