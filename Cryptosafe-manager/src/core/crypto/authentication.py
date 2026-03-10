import sqlite3
import time
from typing import Optional

from .key_manager import KeyManager
import logging

logger = logging.getLogger(__name__)


class AuthenticationService:

    def __init__(self, db_path):
        self.db_path = db_path
        self.key_manager = KeyManager()

        # Для задержек при неудачных попытках (AUTH-3)
        self.failed_attempts = 0
        self.last_failed_time = 0

        # Информация о сессии (AUTH-4)
        self.logged_in = False
        self.login_time = None
        self.last_activity = None

    def _connect(self):
        return sqlite3.connect(self.db_path)

    def _get_delay(self) -> float:
        if self.failed_attempts <= 2:
            return 1
        elif self.failed_attempts <= 4:
            return 5
        else:
            return 30

    def _apply_delay(self):
        if self.failed_attempts > 0:
            delay = self._get_delay()
            logger.debug(f"Задержка {delay}с перед следующей попыткой")
            time.sleep(delay)

    def is_initialized(self) -> bool:
        conn = self._connect()
        cursor = conn.execute(
            "SELECT COUNT(*) FROM key_store WHERE key_type = 'auth_hash'"
        )
        result = cursor.fetchone()[0] > 0
        conn.close()
        return result

    def register(self, password: str) -> bool:
        # Проверяем надежность пароля (HASH-4)
        is_strong, errors = self._check_password_strength(password)
        if not is_strong:
            logger.warning(f"Пароль слишком слабый: {errors}")
            return False

        try:
            # Создаем хэш пароля и соль
            auth_hash = self.key_manager.create_auth_hash(password)
            salt = self.key_manager.generate_salt()

            conn = self._connect()

            # Сохраняем хэш пароля
            conn.execute(
                "INSERT INTO key_store (key_type, key_data, version) VALUES (?, ?, ?)",
                ("auth_hash", auth_hash.encode(), 1)
            )

            # Сохраняем соль
            conn.execute(
                "INSERT INTO key_store (key_type, key_data, version) VALUES (?, ?, ?)",
                ("enc_salt", salt, 1)
            )

            # Сохраняем параметры (для будущих обновлений)
            import json
            params = json.dumps(self.key_manager.get_parameters())
            conn.execute(
                "INSERT INTO key_store (key_type, key_data, version) VALUES (?, ?, ?)",
                ("params", params.encode(), 1)
            )

            conn.commit()
            conn.close()

            logger.info("Мастер-пароль успешно зарегистрирован")
            return True

        except Exception as e:
            logger.error(f"Ошибка при регистрации: {e}")
            return False

    def login(self, password: str) -> Optional[bytes]:
        # Применяем задержку при неудачах
        self._apply_delay()

        conn = self._connect()

        # Получаем хэш пароля
        cursor = conn.execute(
            "SELECT key_data FROM key_store WHERE key_type = 'auth_hash'"
        )
        row = cursor.fetchone()
        if not row:
            conn.close()
            return None
        stored_hash = row[0].decode()

        # Получаем соль
        cursor = conn.execute(
            "SELECT key_data FROM key_store WHERE key_type = 'enc_salt'"
        )
        row = cursor.fetchone()
        if not row:
            conn.close()
            return None
        salt = row[0]

        conn.close()

        # Проверяем пароль
        if not self.key_manager.verify_password(password, stored_hash):
            self.failed_attempts += 1
            self.last_failed_time = time.time()
            logger.warning(f"Неудачная попытка входа #{self.failed_attempts}")
            return None

        # Успешный вход
        self.failed_attempts = 0
        self.logged_in = True
        self.login_time = time.time()
        self.last_activity = time.time()

        # Создаем ключ шифрования
        encryption_key = self.key_manager.derive_encryption_key(password, salt)

        # Кэшируем ключ
        self.key_manager.cache_key(encryption_key)

        logger.info("Успешный вход в систему")
        return encryption_key

    def logout(self):
        self.key_manager.clear_cache()
        self.logged_in = False
        self.login_time = None
        self.last_activity = None
        logger.info("Выход из системы")

    def update_activity(self):
        self.last_activity = time.time()
        if self.key_manager:
            self.key_manager._update_activity()

    def _check_password_strength(self, password: str) -> tuple:
        errors = []

        # Минимальная длина 12 символов
        if len(password) < 12:
            errors.append("Пароль должен быть минимум 12 символов")

        # Проверяем разнообразие символов
        has_upper = any(c.isupper() for c in password)
        has_lower = any(c.islower() for c in password)
        has_digit = any(c.isdigit() for c in password)
        has_special = any(not c.isalnum() for c in password)

        if not has_upper:
            errors.append("Нужна хотя бы одна заглавная буква")
        if not has_lower:
            errors.append("Нужна хотя бы одна строчная буква")
        if not has_digit:
            errors.append("Нужна хотя бы одна цифра")
        if not has_special:
            errors.append("Нужен хотя бы один спецсимвол")

        # Проверяем простые пароли
        simple_passwords = ["password123", "qwerty123", "12345678", "password"]
        if password.lower() in simple_passwords:
            errors.append("Слишком простой пароль")

        return len(errors) == 0, errors

    def get_session_info(self) -> dict:
        return {
            "logged_in": self.logged_in,
            "login_time": self.login_time,
            "last_activity": self.last_activity,
            "failed_attempts": self.failed_attempts
        }