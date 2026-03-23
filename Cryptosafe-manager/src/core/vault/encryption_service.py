from src.core.crypto.abstract import VaultEncryptionService
import json

class EncryptionService:

    def __init__(self, key_manager):
        self._service = VaultEncryptionService(key_manager)

    def encrypt(self, data_dict: dict) -> bytes:
        plaintext = json.dumps(data_dict).encode('utf-8')
        return self._service.encrypt(plaintext)

    def decrypt(self, encrypted_blob: bytes) -> dict:
        plaintext = self._service.decrypt(encrypted_blob)
        return json.loads(plaintext.decode('utf-8'))