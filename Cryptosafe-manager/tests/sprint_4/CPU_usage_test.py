import sys
import os
import time
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


def test_cpu_usage():
    print("CPU usage test (idle)")

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

    process = psutil.Process()

    time.sleep(2)

    cpu_percents = []
    for _ in range(10):
        cpu_percents.append(process.cpu_percent(interval=0.5))

    clipboard_monitor.stop_monitoring()
    clipboard_service.shutdown()

    avg_cpu = sum(cpu_percents) / len(cpu_percents)
    max_cpu = max(cpu_percents)

    print(f"\nСреднее использование CPU: {avg_cpu:.2f}%")
    print(f"Максимальное использование CPU: {max_cpu:.2f}%")

    if avg_cpu < 1 and max_cpu < 1:
        print("\nРезультат: пройден")
        passed = True
    else:
        print("\nРезультат: не пройден")
        passed = False

    return passed


if __name__ == "__main__":
    success = test_cpu_usage()
    sys.exit(0 if success else 1)