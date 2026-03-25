import time
import os
import tempfile
import psutil
from src.core.vault.entry_manager import EntryManager
from src.core.crypto.key_manager import KeyManager
from src.database.db import Database


class MockKeyManager:

    def __init__(self):
        self._key = os.urandom(32)

    def get_cached_key(self):
        return self._key

    def update_activity(self):
        pass


def create_test_entries(entry_manager, count=1000):
    entries = []
    for i in range(count):
        data = {
            'title': f'Тестовая запись {i}',
            'username': f'user{i}@example.com',
            'password': f'P@ssw0rd{i}!',
            'url': f'https://example{i}.com/page?q=test&id={i}',
            'notes': f'Это очень длинная заметка для тестовой записи номер {i}. ' * 10,
            'category': 'Тест' if i % 3 == 0 else 'Работа' if i % 3 == 1 else 'Личное',
            'tags': ['тест', f'тег{i % 10}']
        }
        entry_id = entry_manager.create_entry(data)
        entries.append(entry_id)
    return entries


def test_load_1000_entries():
    print("Тест загрузки 1000 записей")

    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as tmp:
        db_path = tmp.name

    try:
        db = Database(db_path)
        db.initialize()

        key_manager = MockKeyManager()
        entry_manager = EntryManager(db, key_manager)

        print("Создание 1000 тестовых записей")
        create_start = time.time()
        create_test_entries(entry_manager, 1000)
        create_end = time.time()
        print(f"Создание заняло: {create_end - create_start:.2f} сек")

        print("\nЗагрузка 1000 записей...")
        load_start = time.time()
        entries = entry_manager.get_all_entries()
        load_end = time.time()
        load_time = load_end - load_start

        print(f"\nРезультат:")
        print(f"   Загружено записей: {len(entries)}")
        print(f"   Время загрузки: {load_time:.3f} сек")

        if load_time < 2:
            print(f"Тест выполнен {load_time:.3f} сек < 2 сек")
        else:
            print(f"Тест не выполнен: {load_time:.3f} сек >= 2 сек")

        assert load_time < 2, f"Загрузка 1000 записей заняла {load_time:.3f} сек (должно быть < 2 сек)"

    finally:
        os.unlink(db_path)


def test_search_1000_entries():
    print("Тест поиска среди 1000 записей")

    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as tmp:
        db_path = tmp.name

    try:
        db = Database(db_path)
        db.initialize()

        key_manager = MockKeyManager()
        entry_manager = EntryManager(db, key_manager)

        print("Создание 1000 тестовых записей...")
        create_test_entries(entry_manager, 1000)

        test_queries = [
            ('title:Тестовая', 'поиск по заголовку'),
            ('username:user', 'поиск по логину'),
            ('url:example', 'поиск по URL'),
            ('category:Работа', 'поиск по категории'),
            ('P@ssw0rd', 'поиск по паролю'),
        ]

        print("\nПоиск среди 1000 записей:")
        results = []

        for query, description in test_queries:
            search_start = time.time()
            found = entry_manager.search_entries(query)
            search_end = time.time()
            search_time = (search_end - search_start) * 1000

            results.append((description, len(found), search_time))
            print(f"   {description}: {len(found)} найдено, время: {search_time:.2f} мс")

        max_time = max(r[2] for r in results)
        print(f"\nРезультат:")
        print(f"   Максимальное время поиска: {max_time:.2f} мс")

        if max_time < 200:
            print(f"Тест выполнен: {max_time:.2f} мс < 200 мс")
        else:
            print(f"Тест не выполнен: {max_time:.2f} мс >= 200 мс")

        assert max_time < 200, f"Поиск занял {max_time:.2f} мс (должно быть < 200 мс)"

    finally:
        os.unlink(db_path)


def test_memory_usage_1000_entries():
    print("Тест использования памяти для 1000 записей")

    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as tmp:
        db_path = tmp.name

    try:
        process = psutil.Process()
        initial_memory = process.memory_info().rss / (1024 * 1024)  # в МБ

        print(f"Начальное использование памяти: {initial_memory:.2f} МБ")

        db = Database(db_path)
        db.initialize()

        key_manager = MockKeyManager()
        entry_manager = EntryManager(db, key_manager)

        print("Создание 1000 тестовых записей...")
        create_test_entries(entry_manager, 1000)

        print("Загрузка всех записей...")
        entries = entry_manager.get_all_entries()

        after_memory = process.memory_info().rss / (1024 * 1024)
        memory_used = after_memory - initial_memory

        print(f"\nРезультат:")
        print(f"Память после загрузки: {after_memory:.2f} МБ")
        print(f"Использовано памяти: {memory_used:.2f} МБ")
        print(f"Количество записей: {len(entries)}")

        if memory_used < 50:
            print(f"Тест выполнен: {memory_used:.2f} МБ < 50 МБ")
        else:
            print(f"Тест не выполнен: {memory_used:.2f} МБ >= 50 МБ")

        assert memory_used < 50, f"Использовано {memory_used:.2f} МБ (должно быть < 50 МБ)"

    finally:
        os.unlink(db_path)


def test_all_performance():
    test_load_1000_entries()
    test_search_1000_entries()
    test_memory_usage_1000_entries()


if __name__ == "__main__":
    test_all_performance()