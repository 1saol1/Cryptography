import sqlite3
import base64
from src.core.crypto.abstract import VaultEncryptionService


class ConfigManager:

    def __init__(self, db_path: str, key_manager=None):
        self.db_path = db_path
        self.key_manager = key_manager
        self._encryption_service = None
        self._ensure_settings_table()

        if key_manager:
            self._init_encryption()

    def _init_encryption(self):
        try:
            self._encryption_service = VaultEncryptionService(self.key_manager)
        except Exception as e:
            print(f"ConfigManager: Ошибка инициализации шифрования: {e}")
            self._encryption_service = None

    def _get_connection(self):
        return sqlite3.connect(self.db_path)

    def _ensure_settings_table(self):
        with self._get_connection() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS settings (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    setting_key TEXT UNIQUE,
                    setting_value TEXT,
                    encrypted INTEGER DEFAULT 0
                )
            """)
            conn.commit()

    def _encrypt_value(self, value: str) -> str:
        if not self._encryption_service:
            return value
        try:
            encrypted_bytes = self._encryption_service.encrypt(value.encode('utf-8'))
            return base64.b64encode(encrypted_bytes).decode('ascii')
        except Exception as e:
            print(f"ConfigManager: Ошибка шифрования: {e}")
            return value

    def _decrypt_value(self, value: str) -> str:
        if not self._encryption_service:
            return value
        try:
            encrypted_bytes = base64.b64decode(value.encode('ascii'))
            decrypted_bytes = self._encryption_service.decrypt(encrypted_bytes)
            return decrypted_bytes.decode('utf-8')
        except Exception as e:
            print(f"ConfigManager: Ошибка дешифрования: {e}")
            return value

    def set(self, key: str, value: str, encrypted: bool = False):
        with self._get_connection() as conn:
            if encrypted:
                value = self._encrypt_value(value)

            conn.execute("""
                INSERT OR REPLACE INTO settings
                (setting_key, setting_value, encrypted)
                VALUES (?, ?, ?)
            """, (key, value, 1 if encrypted else 0))

    def get(self, key: str, default=None):
        with self._get_connection() as conn:
            cur = conn.execute("""
                SELECT setting_value, encrypted FROM settings
                WHERE setting_key = ?
            """, (key,))
            row = cur.fetchone()

            if row is None:
                return default

            value, is_encrypted = row

            if is_encrypted:
                value = self._decrypt_value(value)

            return value

    def set_encrypted(self, key: str, value: str):
        self.set(key, value, encrypted=True)

    def get_encrypted(self, key: str, default=None):
        return self.get(key, default)

    def update_key_manager(self, key_manager):
        self.key_manager = key_manager
        self._init_encryption()