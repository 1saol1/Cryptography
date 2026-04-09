import sys
import os
import threading
from datetime import datetime

project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, project_root)

from src.core.events import EventBus
from src.core.state_manager import StateManager
from src.core.config import ConfigManager
from src.core.clipboard.clipboard_service import ClipboardService
from src.core.clipboard.clipboard_config import ClipboardSettings

class MockStateManager(StateManager):
    def __init__(self):
        self.is_locked = False
        self.logged_in = True

    def is_active(self):
        return True

class MockConfigManager:
    def __init__(self):
        self.settings = {}

    def get(self, key, default=None):
        return self.settings.get(key, default)

    def set(self, key, value, encrypted=False):
        self.settings[key] = value

def test_auto_clear_timing():
        print("Auto-clear timing test")

        results = []
        timeouts = [5, 10, 15, 30]

        for timeout in timeouts:

            event_bus = EventBus()
            state_manager = MockStateManager()
            config_manager = MockConfigManager()

            clipboard_service = ClipboardService(
                event_bus=event_bus,
                state_manager=state_manager,
                config_manager=config_manager,
                clipboard_settings=None
            )

            clipboard_service.set_timeout(timeout)
            start_time = datetime.now()

            clipboard_service.copy_to_clipboard("test_password_123", "password")

            clear_event = threading.Event()

            def on_clear(data):
                clear_event.set()

            clear_event.wait(timeout + 2)

            end_time = datetime.now()
            actual_time = (end_time - start_time).total_seconds()

            diff = abs(actual_time - timeout)
            is_accurate = diff <= 0.1

            print(f"  Ожидаемое время: {timeout} сек")
            print(f"  Фактическое время: {actual_time:.3f} сек")
            print(f"  Отклонение: {diff * 1000:.1f} мс")
            print(f"  Результат: {'Пройден' if is_accurate else 'Не пройден'}")

            results.append({
                'timeout': timeout,
                'actual': actual_time,
                'diff_ms': diff * 1000,
                'passed': is_accurate
            })

            clipboard_service.shutdown()

        passed_count = sum(1 for r in results if r['passed'])
        print(f"\nРезультат: {passed_count}/{len(results)} тестов пройдено")

        return passed_count

if __name__ == "__main__":
    success = test_auto_clear_timing()
    sys.exit(0 if success else 1)
