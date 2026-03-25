import os
import pytest
from src.core.vault.encryption_service import EncryptionService
from src.core.crypto.key_manager import KeyManager


class MockKeyManager:
    def get_cached_key(self):
        return os.urandom(32)


def test_encryption_cycle():
    original_data = {
        'title': 'Тестовая запись',
        'username': 'test@example.com',
        'password': 'secret123',
        'url': 'https://test.com',
        'notes': 'Это тест',
        'category': 'Тест',
        'id': 'test-123',
        'created_at': '2024-01-01T00:00:00',
        'version': 1
    }

    key_manager = MockKeyManager()
    encryption_service = EncryptionService(key_manager)

    encrypted_blob = encryption_service.encrypt(original_data)

    encrypted_str = str(encrypted_blob)
    assert 'Тестовая запись' not in encrypted_str
    assert 'secret123' not in encrypted_str
    assert 'test@example.com' not in encrypted_str

    decrypted_data = encryption_service.decrypt(encrypted_blob)

    assert decrypted_data == original_data

    print("Цикл шифрования/расшифрования работает")


if __name__ == "__main__":
    test_encryption_cycle()