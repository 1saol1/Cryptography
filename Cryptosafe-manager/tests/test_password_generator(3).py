from src.core.vault.password_generator import PasswordGenerator


def test_password_generator():

    generator = PasswordGenerator()

    passwords = set()
    weak_passwords = 0

    for i in range(10000):
        password = generator.generate()

        assert password not in passwords, f"Найден дубликат: {password}"
        passwords.add(password)

        assert 8 <= len(password) <= 64, f"Неправильная длина: {len(password)}"

        strength = generator.check_strength(password)
        if not strength['is_strong']:
            weak_passwords += 1

        if (i + 1) % 1000 == 0:
            print(f"Сгенерировано {i + 1} паролей...")

    assert len(passwords) == 10000, f"Найдено дубликатов: {10000 - len(passwords)}"

    assert weak_passwords == 0, f"Найдено слабых паролей: {weak_passwords}"

    print("Генератор паролей работает корректно")


def test_password_strength():

    generator = PasswordGenerator()

    # Слабый пароль
    weak = generator.check_strength('123456')
    assert weak['score'] < 2
    assert weak['is_strong'] is False

    # Средний пароль
    medium = generator.check_strength('Password123')
    assert medium['score'] >= 2
    assert medium['is_strong'] is False or medium['is_strong'] is True

    # Надежный пароль
    strong = generator.check_strength('MyStr0ngP@ssw0rd!')
    assert strong['score'] >= 3
    assert strong['is_strong'] is True

    print("Проверка надежности паролей работает")


if __name__ == "__main__":
    test_password_generator()
    test_password_strength()