import sys
import os

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE_DIR)

import pytest
from src.core.vault.encryption_service import EncryptionService
from src.core.crypto.key_manager import KeyManager


class MockKeyManager:
    def __init__(self):
        self._key = os.urandom(32)

    def get_cached_key(self):
        return self._key

    def update_activity(self):
        pass


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
    assert decrypted_data['title'] == 'Тестовая запись'
    assert decrypted_data['password'] == 'secret123'

    print("Цикл шифрования/расшифрования работает")

if __name__ == "__main__":
    test_encryption_cycle()