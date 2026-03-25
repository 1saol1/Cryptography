import os
import sqlite3
import pytest
from src.core.vault.entry_manager import EntryManager
from src.core.crypto.key_manager import KeyManager
from src.core.vault.encryption_service import EncryptionService


class MockKeyManager:
    def get_cached_key(self):
        return os.urandom(32)

    def update_activity(self):
        pass


class MockDB:
    def __init__(self):
        self.conn = sqlite3.connect(':memory:')
        self.create_tables()

    def create_tables(self):
        cursor = self.conn.cursor()
        cursor.execute("""
            CREATE TABLE vault_entries (
                id TEXT PRIMARY KEY,
                encrypted_data BLOB NOT NULL,
                created_at TIMESTAMP NOT NULL,
                updated_at TIMESTAMP NOT NULL,
                deleted_at TIMESTAMP,
                tags TEXT DEFAULT '[]'
            )
        """)
        cursor.execute("""
            CREATE TABLE deleted_entries (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                original_id TEXT NOT NULL,
                encrypted_data BLOB NOT NULL,
                deleted_at TIMESTAMP NOT NULL,
                expires_at TIMESTAMP NOT NULL
            )
        """)
        self.conn.commit()

    def execute(self, query, params=None):
        cursor = self.conn.cursor()
        if params:
            cursor.execute(query, params)
        else:
            cursor.execute(query)
        self.conn.commit()
        return cursor

    def commit(self):
        self.conn.commit()

    def rollback(self):
        self.conn.rollback()


def test_crud_integration():

    key_manager = MockKeyManager()
    db = MockDB()
    entry_manager = EntryManager(db, key_manager)

    created_ids = []
    for i in range(100):
        data = {
            'title': f'Запись {i}',
            'username': f'user{i}@example.com',
            'password': f'password{i}',
            'url': f'https://example{i}.com',
            'notes': f'Заметка {i}',
            'category': 'Тест'
        }
        entry_id = entry_manager.create_entry(data)
        created_ids.append(entry_id)

    all_entries = entry_manager.get_all_entries()
    assert len(all_entries) == 100

    for i in range(0, 100, 2):
        entry_id = created_ids[i]
        updated = entry_manager.update_entry(entry_id, {'title': f'Обновлено {i}'})
        assert updated['title'] == f'Обновлено {i}'

    for i in range(0, 100, 2):
        entry = entry_manager.get_entry(created_ids[i])
        assert entry['title'] == f'Обновлено {i}'

    for i in range(0, 100, 3):
        entry_manager.delete_entry(created_ids[i], soft_delete=True)

    all_entries = entry_manager.get_all_entries()
    expected_count = 100 - len(range(0, 100, 3))
    assert len(all_entries) == expected_count

    print("CRUD операции работают корректно")


if __name__ == "__main__":
    test_crud_integration()