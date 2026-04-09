import sys
import os
import platform
from datetime import datetime
import argparse

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.core.clipboard.platform_adapter import get_platform_adapter


def get_platform_info():
    info = {
        'system': platform.system(),
        'release': platform.release(),
        'version': platform.version(),
        'machine': platform.machine(),
        'processor': platform.processor(),
        'python_version': platform.python_version()
    }

    if info['system'] == 'Linux':
        try:
            with open('/etc/os-release', 'r') as f:
                for line in f:
                    if line.startswith('NAME='):
                        info['distribution'] = line.split('=')[1].strip().strip('"')
                    elif line.startswith('VERSION_ID='):
                        info['version_id'] = line.split('=')[1].strip().strip('"')
        except:
            info['distribution'] = 'Unknown'

    return info


def test_basic_operations(adapter):

    test_cases = [
        ("Simple text", "Hello World"),
        ("Russian text", "Привет мир"),
        ("Numbers", "1234567890"),
        ("Special chars", "!@#$%^&*()_+"),
        ("Mixed", "Hello Привет 123 !@#"),
        ("Empty string", ""),
        ("Newlines", "Line1\nLine2\nLine3"),
        ("Tabs", "Col1\tCol2\tCol3"),
    ]

    results = []

    for name, test_str in test_cases:
        try:
            copy_success = adapter.copy_to_clipboard(test_str)

            result = adapter.get_clipboard_content()

            if test_str == "":
                is_ok = result is None or result == ""
            else:
                is_ok = result == test_str

            results.append({
                'name': name,
                'passed': is_ok,
                'error': None
            })

            status = "Pass" if is_ok else "Didn't pass"
            print(f"    {status} {name}: '{test_str[:30]}'")

        except Exception as e:
            results.append({
                'name': name,
                'passed': False,
                'error': str(e)
            })
            print(f"    {name}: Ошибка - {e}")

    return all(r['passed'] for r in results)


def test_clear_operation(adapter):

    test_data = "TEST_DATA_FOR_CLEAR_" + str(datetime.now().timestamp())

    adapter.copy_to_clipboard(test_data)

    content_before = adapter.get_clipboard_content()
    print(f"    До очистки: {'есть данные' if content_before else 'пусто'}")

    adapter.clear_clipboard()

    content_after = adapter.get_clipboard_content()
    is_cleared = content_after is None or content_after == ""
    print(f"    После очистки: {'пусто' if is_cleared else 'есть данные'}")

    try:
        adapter.clear_clipboard()
        print(f"    Повторная очистка: Пройдён")
    except Exception as e:
        print(f"    Повторная очистка: Ошибка {e}")
        return False

    return is_cleared


def test_large_data(adapter):
    print("\n--- 3. Большие данные ---")

    sizes = [1024, 10240, 102400, 1024 * 1024]

    results = []

    for size in sizes:
        test_data = "A" * size
        size_kb = size / 1024

        try:
            import time
            start = time.time()
            adapter.copy_to_clipboard(test_data)
            copy_time = time.time() - start

            start = time.time()
            result = adapter.get_clipboard_content()
            paste_time = time.time() - start

            is_ok = result == test_data

            results.append(is_ok)
            status = "✓" if is_ok else "✗"
            print(
                f"    {status} {size_kb:.0f} KB: копирование {copy_time * 1000:.0f}мс, вставка {paste_time * 1000:.0f}мс")

        except Exception as e:
            print(f"    ✗ {size_kb:.0f} KB: Ошибка - {e}")
            results.append(False)

    return all(results)


def test_consecutive_operations(adapter):

    test_strings = [
        "First string",
        "Second string with different content",
        "Third string with очень много разных символов !@#$%",
        "Fourth",
        "Fifth and final string"
    ]

    success_count = 0

    for i, test_str in enumerate(test_strings):
        adapter.copy_to_clipboard(test_str)
        result = adapter.get_clipboard_content()

        if result == test_str:
            success_count += 1
            print(f"    Операция {i + 1}: '{test_str[:20]}...'")
        else:
            print(f"    Операция {i + 1}: ожидалось '{test_str[:20]}...', получено '{str(result)[:20]}...'")

    return success_count == len(test_strings)


def run_cross_platform_test():
    print("Cross-platform compatibility test")

    info = get_platform_info()
    print(f"\nИнформация о системе:")
    print(f"  ОС: {info['system']}")
    print(f"  Версия: {info['release']}")
    print(f"  Архитектура: {info['machine']}")
    print(f"  Python: {info['python_version']}")

    if info['system'] == 'Linux' and 'distribution' in info:
        print(f"  Дистрибутив: {info.get('distribution', 'Unknown')}")
        print(f"  Версия дистрибутива: {info.get('version_id', 'Unknown')}")

    adapter = get_platform_adapter()
    print(f"\nАдаптер: {type(adapter).__name__}")

    results = {}

    results['basic_operations'] = test_basic_operations(adapter)

    results['clear_operation'] = test_clear_operation(adapter)

    results['large_data'] = test_large_data(adapter)

    results['consecutive'] = test_consecutive_operations(adapter)

    print("Итоги теста:")

    all_passed = True
    for test_name, passed in results.items():
        status = "Пройден" if passed else "Не пройден"
        print(f"  {status} {test_name}")
        if not passed:
            all_passed = False

    print(f"\nРезультат: {'Все тесты пройдены' if all_passed else 'Есть ошибки'}")

    return all_passed


def run_platform_specific_tests():

    info = get_platform_info()
    adapter = get_platform_adapter()

    if info['system'] == 'Windows':
        print("\nТесты для Windows")

        test_str = "Windows Unicode Test 测试"
        adapter.copy_to_clipboard(test_str)
        result = adapter.get_clipboard_content()
        print(f"  CF_UNICODETEXT: {'Пройден' if result == test_str else 'Ошибка'}")

        if hasattr(adapter, 'copy_to_private_clipboard'):
            adapter.copy_to_private_clipboard(test_str)
            print(f"  Private clipboard: ")

    elif info['system'] == 'Darwin':
        print("\nТесты для macos")

        test_str = "macOS General Pasteboard Test"
        adapter.copy_to_clipboard(test_str, use_private=False)
        result = adapter.get_clipboard_content(from_private=False)
        print(f"  General pasteboard: {'✓' if result == test_str else '✗'}")

        if hasattr(adapter, 'copy_to_clipboard'):
            adapter.copy_to_clipboard(test_str, use_private=True)
            result = adapter.get_clipboard_content(from_private=True)
            print(f"  Private pasteboard: {'✓' if result == test_str else '✗'}")

    elif info['system'] == 'Linux':
        print("\nТесты для Linux")

        test_str = "Linux CLIPBOARD Test"
        adapter.copy_to_clipboard(test_str, use_primary=False)
        result = adapter.get_clipboard_content(from_primary=False)
        print(f"  CLIPBOARD: {'✓' if result == test_str else '✗'}")

        test_str_primary = "Linux PRIMARY Test"
        adapter.copy_to_clipboard(test_str_primary, use_primary=True)
        result = adapter.get_clipboard_content(from_primary=True)
        print(f"  PRIMARY: {'✓' if result == test_str_primary else '✗'}")

        print(f"  Wayland (wl-clipboard): {'✓' if getattr(adapter, '_wayland_available', False) else '✗'}")
        print(f"  xclip: {'✓' if getattr(adapter, '_xclip_available', False) else '✗'}")
        print(f"  xsel: {'✓' if getattr(adapter, '_xsel_available', False) else '✗'}")


if __name__ == "__main__":

    parser = argparse.ArgumentParser()
    parser.add_argument("--platform-specific", action="store_true", help="Запустить платформозависимые тесты")
    args = parser.parse_args()

    success = run_cross_platform_test()

    if args.platform_specific:
        run_platform_specific_tests()

    sys.exit(0 if success else 1)