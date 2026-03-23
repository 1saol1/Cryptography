from abc import ABC, abstractmethod
from typing import Optional
import os
import json
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

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

    def encrypt(self, data: bytes) -> bytes:
        return data

    def decrypt(self, data: bytes) -> bytes:
        return data