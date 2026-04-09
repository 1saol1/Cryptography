import sys
import os
import psutil

project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, project_root)

from src.core.events import EventBus
from src.core.state_manager import StateManager
from src.core.config import ConfigManager
from src.core.clipboard.clipboard_service import ClipboardService
from src.core.clipboard.clipboard_monitor import ClipboardMonitor


class MockStateManager(StateManager):
    def __init__(self):
        self.is_locked = False
        self.logged_in = True

    def is_active(self):
        return True


class MockConfigManager(ConfigManager):
    def __init__(self):
        self.db_path = ":memory:"
        self.key_manager = None
        self._encryption_service = None
        self._ensure_settings_table()


def test_memory_usage():
    print("Memory overhead test")

    process = psutil.Process()

    memory_before = process.memory_info().rss / 1024 / 1024

    event_bus = EventBus()
    state_manager = MockStateManager()
    config_manager = MockConfigManager()

    clipboard_service = ClipboardService(
        event_bus=event_bus,
        state_manager=state_manager,
        config_manager=config_manager,
        clipboard_settings=None
    )

    clipboard_monitor = ClipboardMonitor(
        clipboard_service=clipboard_service,
        event_bus=event_bus,
        config_manager=config_manager
    )

    clipboard_monitor.start_monitoring()

    memory_after = process.memory_info().rss / 1024 / 1024

    clipboard_monitor.stop_monitoring()
    clipboard_service.shutdown()

    memory_used = memory_after - memory_before

    print(f"\nПамять до: {memory_before:.2f} MB")
    print(f"Память после: {memory_after:.2f} MB")
    print(f"Использовано: {memory_used:.2f} MB")

    if memory_used < 10:
        print("\nРезультат: пройден")
        passed = True
    else:
        print("\nРезультат: не пройден")
        passed = False

    return passed


if __name__ == "__main__":
    success = test_memory_usage()
    sys.exit(0 if success else 1)