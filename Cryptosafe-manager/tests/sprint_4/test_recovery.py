import sys
import os
import subprocess
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.core.events import EventBus
from src.core.state_manager import StateManager
from src.core.config import ConfigManager
from src.core.clipboard.clipboard_service import ClipboardService

from src.core.clipboard.platform_adapter import get_platform_adapter


def test_cleanup_on_crash():

    crash_script = tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False)
    crash_script.write("""
import sys
import os
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.core.events import EventBus
from src.core.state_manager import StateManager
from src.core.config import ConfigManager
from src.core.clipboard.clipboard_service import ClipboardService
from src.core.clipboard.platform_adapter import get_platform_adapter


class MockStateManager:
    def __init__(self):
        self.is_locked = False
        self.logged_in = True
    def is_active(self):
        return True


def crash_test():
    event_bus = EventBus()
    state_manager = MockStateManager()
    config_manager = ConfigManager(":memory:")

    clipboard_service = ClipboardService(
        event_bus=event_bus,
        state_manager=state_manager,
        config_manager=config_manager,
        clipboard_settings=None
    )

    clipboard_service.copy_to_clipboard("CRASH_TEST_SECRET_DATA", "password")

    print("DATA_COPIED")
    sys.stdout.flush()

    time.sleep(1)

    print("ABOUT_TO_CRASH")
    sys.stdout.flush()

    os._exit(1)


if __name__ == "__main__":
    crash_test()
""")
    crash_script.close()

    print("  Запуск скрипта, который упадёт...")
    process = subprocess.Popen(
        [sys.executable, crash_script.name],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True
    )

    stdout, stderr = process.communicate(timeout=10)

    print(f"  Скрипт завершился с кодом: {process.returncode}")

    check_script = tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False)
    check_script.write("""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.core.clipboard.platform_adapter import get_platform_adapter

adapter = get_platform_adapter()
content = adapter.get_clipboard_content()
if content and "CRASH_TEST_SECRET_DATA" in content:
    print("FOUND")
else:
    print("NOT_FOUND")
""")
    check_script.close()

    check_process = subprocess.Popen(
        [sys.executable, check_script.name],
        stdout=subprocess.PIPE,
        text=True
    )
    check_stdout, _ = check_process.communicate(timeout=5)

    is_cleared = "NOT_FOUND" in check_stdout
    print(f"  Данные в буфере: {'✗ Найдены' if not is_cleared else '✓ Не найдены'}")

    os.unlink(crash_script.name)
    os.unlink(check_script.name)

    return is_cleared


def test_shutdown_cleanup():

    shutdown_script = tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False)
    shutdown_script.write("""
import sys
import os

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


def shutdown_test():
    event_bus = EventBus()
    state_manager = MockStateManager()
    config_manager = ConfigManager(":memory:")

    clipboard_service = ClipboardService(
        event_bus=event_bus,
        state_manager=state_manager,
        config_manager=config_manager,
        clipboard_settings=None
    )

    clipboard_service.copy_to_clipboard("SHUTDOWN_TEST_SECRET", "password")
    print("DATA_COPIED")

    # Штатное завершение
    clipboard_service.shutdown()
    print("SHUTDOWN_COMPLETE")


if __name__ == "__main__":
    shutdown_test()
""")
    shutdown_script.close()

    process = subprocess.Popen(
        [sys.executable, shutdown_script.name],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True
    )
    stdout, _ = process.communicate(timeout=10)

    print(f"  Вывод: {stdout.strip()}")

    adapter = get_platform_adapter()
    content = adapter.get_clipboard_content()

    is_cleared = content is None or "SHUTDOWN_TEST_SECRET" not in str(content)
    print(f"  Данные в буфере: {'Найдены' if not is_cleared else 'Не найдены'}")

    os.unlink(shutdown_script.name)

    return is_cleared


def test_exception_handling():

    class MockStateManager:
        def __init__(self):
            self.is_locked = False
            self.logged_in = True

        def is_active(self):
            return True

    event_bus = EventBus()
    state_manager = MockStateManager()
    config_manager = ConfigManager(":memory:")

    clipboard_service = ClipboardService(
        event_bus=event_bus,
        state_manager=state_manager,
        config_manager=config_manager,
        clipboard_settings=None
    )

    # Имитируем ошибку
    error_occurred = False
    try:
        # Передаём None вместо строки
        clipboard_service.copy_to_clipboard(None, "test")
    except Exception as e:
        error_occurred = True
        print(f"  Исключение поймано: {type(e).__name__}")

    try:
        clipboard_service.copy_to_clipboard("test_after_error", "test")
        print("  Сервис продолжает работать: ✓")
        service_ok = True
    except:
        service_ok = False

    clipboard_service.shutdown()

    return error_occurred and service_ok


def run_recovery_test():

    print("Recovery test")

    results = {}

    results['crash'] = test_cleanup_on_crash()

    results['shutdown'] = test_shutdown_cleanup()

    results['exceptions'] = test_exception_handling()

    print("Итоги теста:")

    all_passed = True
    for test_name, passed in results.items():
        if not passed:
            all_passed = False

    print(f"\nРезультат: {'Все тесты пройдены' if all_passed else 'Есть ошибки'}")

    return all_passed


if __name__ == "__main__":
    success = run_recovery_test()
    sys.exit(0 if success else 1)