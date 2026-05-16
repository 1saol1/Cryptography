from abc import ABC, abstractmethod
import os
import json
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.backends import default_backend

from src.core.crypto.key_manager import KeyManager


class EncryptionService(ABC):

    def __init__(self, key_manager: KeyManager):
        self.key_manager = key_manager

    @abstractmethod
    def encrypt(self, data: bytes) -> bytes:
        pass

    @abstractmethod
    def decrypt(self, data: bytes) -> bytes:
        pass

    def _get_key(self) -> bytes:
        key = self.key_manager.get_cached_key()
        if key is None:
            raise ValueError("Ключ шифрования не доступен. Сначала выполните вход.")
        return key


class VaultEncryptionService(EncryptionService):

    def encrypt(self, data: bytes) -> bytes:
        key = self._get_key()
        nonce = os.urandom(12)
        aesgcm = AESGCM(key)
        ciphertext = aesgcm.encrypt(nonce, data, None)
        return nonce + ciphertext

    def decrypt(self, data: bytes) -> bytes:
        key = self._get_key()
        nonce = data[:12]
        ciphertext = data[12:]
        aesgcm = AESGCM(key)
        plaintext = aesgcm.decrypt(nonce, ciphertext, None)
        return plaintext


class AuditLogEncryptionService(EncryptionService):
    def __init__(self, password: str = None, salt: bytes = None):
        self._password = password
        self._salt = salt or os.urandom(16)
        self._key = None
        self._temp_key_manager = None

        if password:
            self._derive_key()

    def _derive_key(self):
        if not self._password:
            raise ValueError("Пароль не установлен")

        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=self._salt,
            iterations=100000,
            backend=default_backend()
        )
        key_material = kdf.derive(self._password.encode())

        self._temp_key_manager = KeyManager()
        self._temp_key_manager.cache_key(key_material)
        self._key = key_material

    def set_password(self, password: str, salt: bytes = None):
        self._password = password
        if salt:
            self._salt = salt
        self._derive_key()

    def get_salt(self) -> bytes:
        return self._salt

    def _get_key(self) -> bytes:
        if self._key is None:
            raise ValueError("Пароль не установлен. Вызовите set_password() перед шифрованием.")
        return self._key

    def encrypt(self, data: bytes) -> bytes:
        key = self._get_key()
        nonce = os.urandom(12)
        aesgcm = AESGCM(key)
        ciphertext = aesgcm.encrypt(nonce, data, None)
        return nonce + ciphertext

    def decrypt(self, data: bytes) -> bytes:
        key = self._get_key()
        nonce = data[:12]
        ciphertext = data[12:]
        aesgcm = AESGCM(key)
        plaintext = aesgcm.decrypt(nonce, ciphertext, None)
        return plaintext

    def encrypt_to_dict(self, data: dict) -> dict:
        json_str = json.dumps(data, indent=2, ensure_ascii=False, default=str)
        encrypted = self.encrypt(json_str.encode('utf-8'))

        return {
            'salt': self._salt.hex(),
            'ciphertext': encrypted.hex()
        }

    def decrypt_from_dict(self, data_dict: dict) -> dict:
        salt = bytes.fromhex(data_dict['salt'])
        ciphertext = bytes.fromhex(data_dict['ciphertext'])

        self._salt = salt
        self._derive_key()

        decrypted = self.decrypt(ciphertext)
        return json.loads(decrypted.decode('utf-8'))

    def clear(self):
        if self._temp_key_manager:
            self._temp_key_manager.clear_cache()
        self._key = None
        self._password = None