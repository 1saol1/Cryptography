import sys
import os
import time
import threading
import random
import psutil

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.core.events import EventBus
from src.core.state_manager import StateManager
from src.core.config import ConfigManager
from src.core.clipboard.clipboard_service import ClipboardService


class MockStateManager:
    def __init__(self):
        self.is_locked = False
        self.logged_in = True

    def is_active(self):
        return True


def test_rapid_copy_operations():

    event_bus = EventBus()
    state_manager = MockStateManager()
    config_manager = ConfigManager(":memory:")

    clipboard_service = ClipboardService(
        event_bus=event_bus,
        state_manager=state_manager,
        config_manager=config_manager,
        clipboard_settings=None
    )

    clipboard_service.set_timeout(0)

    copied_items = []
    copied_events = []

    def on_copied(data):
        copied_events.append(data)

    event_bus.subscribe("ClipboardCopied", on_copied)

    num_operations = 100
    start_time = time.time()

    for i in range(num_operations):
        test_data = f"CONCURRENT_TEST_{i}_{random.randint(1, 1000000)}"
        clipboard_service.copy_to_clipboard(test_data, "test")
        copied_items.append(test_data)

    end_time = time.time()
    total_time = end_time - start_time

    print(f"  Операций: {num_operations}")
    print(f"  Время: {total_time:.3f} сек")
    print(f"  Среднее: {total_time / num_operations * 1000:.1f} мс/операцию")

    last_copied = copied_items[-1] if copied_items else None
    current = clipboard_service.get_current_data_preview(reveal=True)

    is_last_in_buffer = (current == last_copied)
    print(f"  Последнее скопированное в буфере: {'✓' if is_last_in_buffer else '✗'}")

    events_received = len(copied_events)
    print(f"  Событий получено: {events_received}/{num_operations}")

    clipboard_service.shutdown()

    return is_last_in_buffer and events_received == num_operations


def test_parallel_copy_operations():

    event_bus = EventBus()
    state_manager = MockStateManager()
    config_manager = ConfigManager(":memory:")

    clipboard_service = ClipboardService(
        event_bus=event_bus,
        state_manager=state_manager,
        config_manager=config_manager,
        clipboard_settings=None
    )

    clipboard_service.set_timeout(0)

    results = []
    errors = []
    lock = threading.Lock()

    def copy_worker(thread_id, data):
        try:
            success = clipboard_service.copy_to_clipboard(data, "test")
            with lock:
                results.append({
                    'thread': thread_id,
                    'data': data,
                    'success': success
                })
        except Exception as e:
            with lock:
                errors.append(str(e))

    threads = []
    num_threads = 20

    for i in range(num_threads):
        test_data = f"PARALLEL_TEST_{i}_{int(time.time() * 1000)}"
        thread = threading.Thread(target=copy_worker, args=(i, test_data))
        threads.append(thread)
        thread.start()

    for thread in threads:
        thread.join()

    successful = sum(1 for r in results if r['success'])
    print(f"  Потоков: {num_threads}")
    print(f"  Успешных операций: {successful}/{num_threads}")
    print(f"  Ошибок: {len(errors)}")

    current_item = getattr(clipboard_service, '_current_item', None)
    print(f"  Активный элемент: {'есть' if current_item else 'нет'}")

    clipboard_service.shutdown()

    return successful == num_threads and len(errors) == 0


def test_memory_leak():

    event_bus = EventBus()
    state_manager = MockStateManager()
    config_manager = ConfigManager(":memory:")

    clipboard_service = ClipboardService(
        event_bus=event_bus,
        state_manager=state_manager,
        config_manager=config_manager,
        clipboard_settings=None
    )

    process = psutil.Process()

    memory_before = process.memory_info().rss

    num_operations = 500

    for i in range(num_operations):
        test_data = f"MEMORY_LEAK_TEST_{i}_" + "X" * 100
        clipboard_service.copy_to_clipboard(test_data, "test")

        if i % 50 == 0:
            clipboard_service.clear_clipboard()

    memory_after = process.memory_info().rss
    memory_diff = memory_after - memory_before

    print(f"  Операций: {num_operations}")
    print(f"  Память до: {memory_before / 1024 / 1024:.2f} МБ")
    print(f"  Память после: {memory_after / 1024 / 1024:.2f} МБ")
    print(f"  Разница: {memory_diff / 1024 / 1024:.2f} МБ")

    has_leak = memory_diff > 5 * 1024 * 1024
    print(f"  Утечек памяти: {'Есть' if has_leak else 'Нет'}")

    clipboard_service.shutdown()

    return not has_leak


def test_data_leakage():

    event_bus = EventBus()
    state_manager = MockStateManager()
    config_manager = ConfigManager(":memory:")

    clipboard_service = ClipboardService(
        event_bus=event_bus,
        state_manager=state_manager,
        config_manager=config_manager,
        clipboard_settings=None
    )

    clipboard_service.set_timeout(0)

    password1 = "FIRST_SECRET_PASSWORD_123"
    clipboard_service.copy_to_clipboard(password1, "password")

    password2 = "SECOND_SECRET_PASSWORD_456"
    clipboard_service.copy_to_clipboard(password2, "password")

    current = clipboard_service.get_current_data_preview(reveal=True)
    is_second = current == password2

    current_item = getattr(clipboard_service, '_current_item', None)
    first_leaked = False

    if current_item:
        try:
            data = current_item.get_data()
            if data == password1:
                first_leaked = True
        except:
            pass

    print(f"  В буфере второй пароль: {'Да' if is_second else 'Нет'}")
    print(f"  Первый пароль не остался: {'Да' if not first_leaked else 'Нет'}")

    clipboard_service.shutdown()

    return is_second and not first_leaked


def run_concurrency_test():
    print("Concurrency test")

    results = {}

    results['rapid_copy'] = test_rapid_copy_operations()

    results['parallel_copy'] = test_parallel_copy_operations()

    results['memory_leak'] = test_memory_leak()

    results['data_leakage'] = test_data_leakage()

    print("Итог теста:")

    all_passed = True
    for test_name, passed in results.items():
        if not passed:
            all_passed = False

    print(f"\nРезультат: {'Все тесты пройдены' if all_passed else 'Есть ошибки'}")

    return all_passed


if __name__ == "__main__":
    success = run_concurrency_test()
    sys.exit(0 if success else 1)