import sys
import os
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.core.events import EventBus
from src.core.state_manager import StateManager
from src.core.config import ConfigManager
from src.core.clipboard.clipboard_service import ClipboardService


class MockStateManager(StateManager):
    def __init__(self):
        self.is_locked = False
        self.logged_in = True

    def is_active(self):
        return True


def test_copy_performance():
    print("Copy operation performance test")

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

    test_data = "TestPassword123!"

    times = []
    for _ in range(10):
        start = time.perf_counter()
        clipboard_service.copy_to_clipboard(test_data, "password")
        end = time.perf_counter()
        times.append((end - start) * 1000)

    avg_time = sum(times) / len(times)
    max_time = max(times)

    print(f"\nСреднее время копирования: {avg_time:.2f} мс")
    print(f"Максимальное время: {max_time:.2f} мс")

    if avg_time < 100 and max_time < 100:
        print("\nРезультат: пройден")
        passed = True
    else:
        print("\nРезультат: не пройден")
        passed = False

    clipboard_service.shutdown()
    return passed


if __name__ == "__main__":
    success = test_copy_performance()
    sys.exit(0 if success else 1)