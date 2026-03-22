import os
import json
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

class EncryptionService:
    def __init__(self, encryption_key):
        self._key = encryption_key
        self._aesgcm = AESGCM(encryption_key)

    def encrypt(self, data_dict: dict) -> bytes:
        nonce = os.urandom(12)

        plaintext = json.dumps(data_dict).encode('utf-8')

        # является тегом аутентификации
        ciphertext = self._aesgcm.encrypt(nonce, plaintext, None)

        encrypted_blob = nonce + ciphertext

        return encrypted_blob

    def decrypt(self, encrypted_blob: bytes) -> dict:

        nonce = encrypted_blob[:12]
        ciphertext = encrypted_blob[12:]

        # расшифровываем с проверкой аутентификации
        plaintext = self._aesgcm.decrypt(nonce, ciphertext, None)

        data_dict = json.loads(plaintext.decode('utf-8'))

        return data_dict

