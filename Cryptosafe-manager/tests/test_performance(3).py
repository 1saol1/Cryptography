import time
import os
import tempfile
import sys
import warnings

warnings.filterwarnings("ignore", category=DeprecationWarning, module="sqlite3")

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE_DIR)

try:
    import psutil
    PSUTIL_AVAILABLE = True
except ImportError:
    PSUTIL_AVAILABLE = False
    print("Модуль psutil не установлен. Тест памяти будет пропущен.")

from src.core.vault.entry_manager import EntryManager
from src.database.db import Database


class MockKeyManager:
    def __init__(self):
        self._key = os.urandom(32)

    def get_cached_key(self):
        return self._key

    def update_activity(self):
        pass


def create_test_entries(entry_manager, count=1000):
    for i in range(count):
        data = {
            'title': f'Тестовая запись {i}',
            'username': f'user{i}@example.com',
            'password': f'P@ssw0rd{i}!',
            'url': f'https://example{i}.com/page?q=test&id={i}',
            'notes': f'Это очень длинная заметка для тестовой записи номер {i}. ' * 5,
            'category': 'Тест' if i % 3 == 0 else 'Работа' if i % 3 == 1 else 'Личное',
            'tags': ['тест', f'тег{i % 10}']
        }
        entry_manager.create_entry(data)


def test_load_1000_entries():
    print("Тест загрузки 1000 записей")

    db_path = None
    db = None
    try:
        # Создаём временный файл
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as tmp:
            db_path = tmp.name

        db = Database(db_path)
        db.initialize()

        key_manager = MockKeyManager()
        entry_manager = EntryManager(db, key_manager)

        print("Создание 1000 тестовых записей...")
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

        assert load_time < 2.0, f"Загрузка заняла {load_time:.3f} сек (должно быть < 2 сек)"
        print(f"Тест пройден ({load_time:.3f} сек < 2 сек)")

    finally:
        # Правильно закрываем все соединения перед удалением файла
        if db is not None:
            try:
                db.close()          # ← Это самое важное!
            except:
                pass

        if db_path and os.path.exists(db_path):
            try:
                os.unlink(db_path)
            except Exception as e:
                print(f"Предупреждение: Не удалось удалить временный файл {db_path}: {e}")


def test_search_1000_entries():
    print("\nТест поиска среди 1000 записей")

    db_path = None
    db = None
    try:
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as tmp:
            db_path = tmp.name

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
        ]

        print("\nВыполняем поиск:")
        max_time = 0

        for query, description in test_queries:
            start = time.time()
            found = entry_manager.search_entries(query)
            elapsed = (time.time() - start) * 1000

            print(f"   {description}: найдено {len(found)} записей за {elapsed:.1f} мс")
            max_time = max(max_time, elapsed)

        assert max_time < 200, f"Поиск занял {max_time:.1f} мс (должно быть < 200 мс)"
        print(f"Тест поиска пройден (макс. {max_time:.1f} мс < 200 мс)")

    finally:
        if db is not None:
            try:
                db.close()
            except:
                pass
        if db_path and os.path.exists(db_path):
            try:
                os.unlink(db_path)
            except Exception as e:
                print(f"Предупреждение: Не удалось удалить {db_path}: {e}")


def test_memory_usage_1000_entries():
    if not PSUTIL_AVAILABLE:
        print("\nТест памяти пропущен (psutil не установлен)")
        return

    print("\nТест использования памяти для 1000 записей")
    db_path = None
    db = None
    try:
        process = psutil.Process()
        initial_memory = process.memory_info().rss / (1024 * 1024)

        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as tmp:
            db_path = tmp.name

        db = Database(db_path)
        db.initialize()

        key_manager = MockKeyManager()
        entry_manager = EntryManager(db, key_manager)

        create_test_entries(entry_manager, 1000)
        entries = entry_manager.get_all_entries()

        after_memory = process.memory_info().rss / (1024 * 1024)
        memory_used = after_memory - initial_memory

        print(f"Использовано памяти: {memory_used:.2f} МБ")
        assert memory_used < 50, f"Использовано {memory_used:.2f} МБ (должно быть < 50 МБ)"
        print(f"Тест памяти пройден ({memory_used:.2f} МБ < 50 МБ)")

    finally:
        if db is not None:
            try:
                db.close()
            except:
                pass
        if db_path and os.path.exists(db_path):
            try:
                os.unlink(db_path)
            except:
                pass


def test_all_performance():
    test_load_1000_entries()
    test_search_1000_entries()
    test_memory_usage_1000_entries()


if __name__ == "__main__":
    print("Тест производительности\n")
    test_all_performance()
    print("\nВсе тесты производительности завершены успешно!")