import sqlite3
from .key_derivation import KeyManager


class AuthenticationService:
    def __init__(self, db_path):
        self.db_path = db_path
        self.key_manager = KeyManager()
        self.failed_attempts = 0

    def _connect(self):
        return sqlite3.connect(self.db_path)

    # Проверяем, есть ли уже мастер-пароль
    def is_initialized(self):
        conn = self._connect()
        cursor = conn.execute(
            "SELECT COUNT(*) FROM key_store WHERE key_type = 'auth_hash'"
        )
        result = cursor.fetchone()[0]
        conn.close()
        return result > 0

    # Первичная регистрация мастер-пароля
    def register(self, password: str):
        auth_hash = self.key_manager.create_auth_hash(password)
        salt = self.key_manager.generate_salt()

        conn = self._connect()

        conn.execute(
            "INSERT INTO key_store (key_type, key_data, version) VALUES (?, ?, ?)",
            ("auth_hash", auth_hash.encode(), 1)
        )

        conn.execute(
            "INSERT INTO key_store (key_type, key_data, version) VALUES (?, ?, ?)",
            ("enc_salt", salt, 1)
        )

        conn.commit()
        conn.close()

    # Логин
    def login(self, password: str):
        conn = self._connect()

        cursor = conn.execute(
            "SELECT key_data FROM key_store WHERE key_type = 'auth_hash'"
        )
        stored_hash = cursor.fetchone()[0].decode()

        cursor = conn.execute(
            "SELECT key_data FROM key_store WHERE key_type = 'enc_salt'"
        )
        salt = cursor.fetchone()[0]

        conn.close()

        if not self.key_manager.verify_password(password, stored_hash):
            self.failed_attempts += 1
            return None

        self.failed_attempts = 0

        # Генерируем ключ шифрования
        encryption_key = self.key_manager.derive_encryption_key(password, salt)

        return encryption_key