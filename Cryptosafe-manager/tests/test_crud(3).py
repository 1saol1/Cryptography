import sys
import os
import sqlite3
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE_DIR)

from src.core.vault.entry_manager import EntryManager

sqlite3.register_adapter(datetime, lambda dt: dt.isoformat())

class MockKeyManager:
    def __init__(self):
        self._key = os.urandom(32)

    def get_cached_key(self):
        return self._key

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
        if params is not None:
            cursor.execute(query, params)
        else:
            cursor.execute(query)
        self.conn.commit()
        return cursor

    def fetchall(self, query, params=None):
        cursor = self.conn.cursor()
        if params is not None:
            cursor.execute(query, params)
        else:
            cursor.execute(query)
        return cursor.fetchall()

    def fetchone(self, query, params=None):
        cursor = self.conn.cursor()
        if params is not None:
            cursor.execute(query, params)
        else:
            cursor.execute(query)
        return cursor.fetchone()


def test_crud_integration():
    key_manager = MockKeyManager()
    db = MockDB()

    entry_manager = EntryManager(
        db_connection=db,
        key_manager=key_manager
    )

    created_ids = []

    print("Создаём 100 тестовых записей")

    for i in range(100):
        data = {
            'title': f'Запись {i}',
            'username': f'user{i}@example.com',
            'password': f'P@ssw0rd{i}!Strong',
            'url': f'https://site{i}.com',
            'notes': f'Тестовая заметка номер {i}',
            'category': 'Тест'
        }

        try:
            entry_id = entry_manager.create_entry(data)
            created_ids.append(entry_id)
        except Exception as e:
            print(f"Ошибка создания записи {i}: {e}")

    print(f"Успешно создано: {len(created_ids)} записей")

    all_entries = entry_manager.get_all_entries()
    print(f"get_all_entries() вернуло: {len(all_entries)} записей")

    assert len(all_entries) == 100, f"Ожидалось 100 записей, а получено {len(all_entries)}"

    print("Проверяем обновление записей...")
    for i in range(0, 100, 2):
        entry_id = created_ids[i]
        updated = entry_manager.update_entry(entry_id, {'title': f'Обновлённая запись {i}'})
        assert updated['title'] == f'Обновлённая запись {i}'

    entry = entry_manager.get_entry(created_ids[0])
    assert entry['title'].startswith('Обновлённая запись')

    print("Выполняем мягкое удаление каждой третьей записи...")
    deleted_count = 0
    for i in range(0, 100, 3):
        entry_manager.delete_entry(created_ids[i], soft_delete=True)
        deleted_count += 1

    remaining = entry_manager.get_all_entries()
    expected = 100 - deleted_count
    print(f"После удаления осталось: {len(remaining)} (ожидалось {expected})")

    assert len(remaining) == expected, f"Ожидалось {expected}, осталось {len(remaining)}"

    print("\nВсе CRUD тесты прошли успешно!")


if __name__ == "__main__":
    test_crud_integration()