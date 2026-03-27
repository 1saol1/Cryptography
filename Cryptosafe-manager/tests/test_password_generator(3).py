import sys
import os

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE_DIR)

from src.core.vault.password_generator import PasswordGenerator


def test_password_generator():
    generator = PasswordGenerator()

    passwords = set()
    weak_count = 0

    for i in range(10000):
        password = generator.generate()

        assert password not in passwords, f"Найден дубликат: {password}"
        passwords.add(password)

        assert 8 <= len(password) <= 64, f"Неправильная длина: {len(password)}"

        strength = generator.check_strength(password)
        if not strength['is_strong']:
            weak_count += 1

    assert len(passwords) == 10000, f"Найдено дубликатов: {10000 - len(passwords)}"
    assert weak_count == 0, f"Найдено слабых паролей среди сгенерированных: {weak_count}"

    print("Генератор паролей работает корректно")


def test_password_strength():
    generator = PasswordGenerator()

    weak = generator.check_strength('123456')
    print(f"Пароль '123456': {weak['strength']} (score: {weak['score']})")
    assert weak['score'] == 0, f"Ожидался score 0, получен {weak['score']}"
    assert weak['is_strong'] is False

    medium = generator.check_strength('Password123')
    print(f"Пароль 'Password123': {medium['strength']} (score: {medium['score']})")
    assert medium['score'] == 0, f"Ожидался score 0 (из-за COMMON_PASSWORDS), получен {medium['score']}"
    assert medium['is_strong'] is False

    strong = generator.check_strength('MyStr0ngP@ssw0rd')
    print(f"Пароль 'MyStr0ngP@ssw0rd!': {strong['strength']} (score: {strong['score']})")
    assert strong['score'] >= 3, f"Ожидался score >= 3, получен {strong['score']}"
    assert strong['is_strong'] is True

    print("Проверка надежности паролей работает")


def test_generated_password_strength():
    generator = PasswordGenerator()

    weak_generated = 0
    for i in range(100):
        password = generator.generate()
        strength = generator.check_strength(password)
        print(f"Пароль {i + 1}: {password} - {strength['strength']} (score: {strength['score']})")

        if not strength['is_strong']:
            weak_generated += 1

    assert weak_generated == 0, f"Сгенерировано {weak_generated} слабых паролей"
    print("Все сгенерированные пароли прошли проверку на надёжность")


if __name__ == "__main__":
    print("Тест генератора паролей\n")

    test_password_generator()
    print()
    test_password_strength()
    print()
    test_generated_password_strength()

    print("\nВсе тесты пройдены успешно")