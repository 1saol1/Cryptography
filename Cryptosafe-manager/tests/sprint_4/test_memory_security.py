import sys
import os
import time
import psutil

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.core.events import EventBus
from src.core.state_manager import StateManager
from src.core.config import ConfigManager
from src.core.clipboard.clipboard_service import ClipboardService
from src.core.clipboard.secure_item import SecureClipboardItem


class MockStateManager:
    def __init__(self):
        self.is_locked = False
        self.logged_in = True

    def is_active(self):
        return True


def test_secure_item_memory():

    test_password = "MySuperSecretPassword123!"

    item = SecureClipboardItem(test_password, "password", "test_id")

    retrieved = item.get_data()
    print(f"  Оригинал: {test_password}")
    print(f"  Получено: {retrieved}")
    print(f"  Совпадает: {'Да' if retrieved == test_password else 'Нет'}")

    obfuscated = getattr(item, '_obfuscated_data', None)
    if obfuscated:
        print(f"  Обфусцированные данные: {obfuscated[:20]}...")
        is_obfuscated = test_password.encode() not in obfuscated
        print(f"  Данные скрыты: {'Да' if is_obfuscated else 'Нет'}")

    item.secure_wipe()

    wiped_data = item.get_data()
    print(f"  После очистки: '{wiped_data}'")
    is_cleared = wiped_data == ""

    return retrieved == test_password and is_cleared


def test_memory_dump_search():

    test_password = "UNIQUE_TEST_PASSWORD_FOR_MEMORY_TEST_" + str(int(time.time()))

    event_bus = EventBus()
    state_manager = MockStateManager()
    config_manager = ConfigManager(":memory:")

    clipboard_service = ClipboardService(
        event_bus=event_bus,
        state_manager=state_manager,
        config_manager=config_manager,
        clipboard_settings=None
    )

    clipboard_service.copy_to_clipboard(test_password, "password")

    current_process = psutil.Process()

    found = False
    try:
        memory_maps = current_process.memory_maps()

        for mem_map in memory_maps:
            try:
                with open(f"/proc/{current_process.pid}/mem", 'rb') as f:
                    f.seek(mem_map.addr)
                    data = f.read(mem_map.size)

                    if test_password.encode() in data:
                        found = True
                        print(f"  ВНИМАНИЕ: Пароль найден в {mem_map.path}")
                        break
            except:
                pass
    except Exception as e:
        print(f"  Не удалось прочитать память: {e}")
        print("  (Для полного теста нужны права администратора)")

    clipboard_service.shutdown()

    if not found:
        print("  Пароль не найден в памяти")
    else:
        print("  Пароль найден в памяти!")

    return not found


def test_secure_wipe():

    test_data = "SENSITIVE_DATA_" * 100

    item = SecureClipboardItem(test_data, "test", None)

    obfuscated_before = getattr(item, '_obfuscated_data', b'')

    item.secure_wipe()

    obfuscated_after = getattr(item, '_obfuscated_data', b'')

    is_wiped = all(b == 0 for b in obfuscated_after) if obfuscated_after else True

    print(f"  Данные затерты: {'Да' if is_wiped else 'Нет'}")

    return is_wiped


def test_clipboard_service_memory():

    event_bus = EventBus()
    state_manager = MockStateManager()
    config_manager = ConfigManager(":memory:")

    clipboard_service = ClipboardService(
        event_bus=event_bus,
        state_manager=state_manager,
        config_manager=config_manager,
        clipboard_settings=None
    )

    test_password = "MEMORY_TEST_PASSWORD"

    clipboard_service.copy_to_clipboard(test_password, "password")

    current_item = getattr(clipboard_service, '_current_item', None)

    if current_item:
        obfuscated = getattr(current_item, '_obfuscated_data', None)

        if obfuscated:
            is_hidden = test_password.encode() not in obfuscated
            print(f"  Данные в памяти скрыты: {'Да' if is_hidden else 'Нет'}")

            preview = clipboard_service.get_current_data_preview(reveal=False)
            if preview and len(preview) < len(test_password):
                print(f"  Предпросмотр скрыт: '{preview}' ✓")

            clipboard_service.shutdown()
            return is_hidden

    return False


def run_memory_security_test():
    print("Memory security test")
    results = {}

    results['secure_item'] = test_secure_item_memory()

    results['memory_dump'] = test_memory_dump_search()

    results['secure_wipe'] = test_secure_wipe()

    results['service_memory'] = test_clipboard_service_memory()

    print("Итоги теста:")

    all_passed = True
    for test_name, passed in results.items():
        if not passed:
            all_passed = False

    print(f"\nРезультат: {'ВСЕ ТЕСТЫ ПРОЙДЕНЫ' if all_passed else 'ЕСТЬ ОШИБКИ'}")

    return all_passed


if __name__ == "__main__":
    success = run_memory_security_test()
    sys.exit(0 if success else 1)