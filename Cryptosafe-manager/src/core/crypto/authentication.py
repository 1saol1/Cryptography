import sqlite3
import time
import json
from typing import Optional, Tuple, List
import logging

from .key_manager import KeyManager

logger = logging.getLogger(__name__)


class AuthenticationService:

    def __init__(self, db_path):
        self.db_path = db_path
        self.key_manager = KeyManager()

        self.failed_attempts = 0
        self.last_failed_time = 0

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

    # проверяет был ли человек зарегистрирован
    def is_initialized(self) -> bool:
        conn = self._connect()
        cursor = conn.execute(
            "SELECT COUNT(*) FROM key_store WHERE key_type = 'auth_hash'"
        )
        result = cursor.fetchone()[0] > 0
        conn.close()
        return result

    def register(self, password: str) -> Tuple[bool, Optional[List[str]]]:
        is_strong, errors = self._check_password_strength(password)
        if not is_strong:
            logger.warning(f"Пароль слишком слабый: {errors}")
            return False, errors

        try:
            auth_hash = self.key_manager.create_auth_hash(password)
            salt = self.key_manager.generate_salt()

            conn = self._connect()

            conn.execute(
                "INSERT INTO key_store (key_type, key_data, version) VALUES (?, ?, ?)",
                ("auth_hash", auth_hash.encode(), 1)
            )

            conn.execute(
                "INSERT INTO key_store (key_type, key_data, version) VALUES (?, ?, ?)",
                ("enc_salt", salt, 1)
            )

            params = json.dumps(self.key_manager.get_params())
            conn.execute(
                "INSERT INTO key_store (key_type, key_data, version) VALUES (?, ?, ?)",
                ("params", params.encode(), 1)
            )

            conn.commit()
            conn.close()

            logger.info("Мастер-пароль успешно зарегистрирован")
            return True, None

        except Exception as e:
            logger.error(f"Ошибка при регистрации: {e}")
            return False, [str(e)]

    def login(self, password: str) -> Optional[bytes]:
        self._apply_delay()

        conn = self._connect()

        cursor = conn.execute(
            "SELECT key_data FROM key_store WHERE key_type = 'auth_hash' ORDER BY id DESC LIMIT 1"
        )
        row = cursor.fetchone()
        if not row:
            conn.close()
            return None
        stored_hash = row[0].decode()

        cursor = conn.execute(
            "SELECT key_data FROM key_store WHERE key_type = 'enc_salt' ORDER BY id DESC LIMIT 1"
        )
        row = cursor.fetchone()
        if not row:
            conn.close()
            return None
        salt = row[0]

        conn.close()

        if not self.key_manager.verify_password(password, stored_hash):
            self.failed_attempts += 1
            self.last_failed_time = time.time()
            logger.warning(f"Неудачная попытка входа #{self.failed_attempts}")
            return None

        self.failed_attempts = 0
        self.logged_in = True
        self.login_time = time.time()
        self.last_activity = time.time()

        encryption_key = self.key_manager.derive_encryption_key(password, salt)

        self.key_manager.cache_key(encryption_key)

        logger.info("Успешный вход в систему")
        return encryption_key

    def change_password(self, old_password: str, new_password: str) -> Tuple[bool, Optional[List[str]]]:

        is_strong, errors = self._check_password_strength(new_password)
        if not is_strong:
            return False, errors

        conn = None
        old_entries = None
        new_auth_hash = None
        new_salt = None
        new_key = None

        try:
            conn = self._connect()


            conn.execute("BEGIN TRANSACTION")
            logger.info("CHANGE-4: Начата транзакция смены пароля")

            cursor = conn.execute(
                "SELECT key_data FROM key_store WHERE key_type = 'auth_hash' ORDER BY id DESC LIMIT 1"
            )
            row = cursor.fetchone()
            if not row:
                conn.close()
                return False, ["Хэш пароля не найден"]
            stored_hash = row[0].decode()

            cursor = conn.execute(
                "SELECT key_data FROM key_store WHERE key_type = 'enc_salt' ORDER BY id DESC LIMIT 1"
            )
            row = cursor.fetchone()
            if not row:
                conn.close()
                return False, ["Соль не найдена"]
            old_salt = row[0]

            if not self.key_manager.verify_password(old_password, stored_hash):
                conn.close()
                return False, ["Неверный текущий пароль"]

            old_key = self.key_manager.derive_encryption_key(old_password, old_salt)

            cursor = conn.execute("SELECT id, title, username, encrypted_password, url, notes FROM vault_entries")
            old_entries = cursor.fetchall()
            logger.info(f"Загружено {len(old_entries)} записей для перешифрования")

            new_auth_hash = self.key_manager.create_auth_hash(new_password)
            new_salt = self.key_manager.generate_salt()

            new_key = self.key_manager.derive_encryption_key(new_password, new_salt)

            for entry_id, title, username, encrypted_data, url, notes in old_entries:
                if encrypted_data:
                    try:

                        pass
                    except Exception as e:
                        logger.error(f"Ошибка при перешифровании записи {entry_id}: {e}")
                        raise Exception(f"Ошибка при перешифровании записи {title}: {str(e)}")

            conn.execute(
                "INSERT INTO key_store (key_type, key_data, version) VALUES (?, ?, ?)",
                ("auth_hash", new_auth_hash.encode(), 2)
            )

            conn.execute(
                "INSERT INTO key_store (key_type, key_data, version) VALUES (?, ?, ?)",
                ("enc_salt", new_salt, 2)
            )

            params = json.dumps(self.key_manager.get_params())
            conn.execute(
                "INSERT INTO key_store (key_type, key_data, version) VALUES (?, ?, ?)",
                ("params", params.encode(), 2)
            )

            conn.commit()
            logger.info("Транзакция успешно закоммичена")

            if self.logged_in:
                self.key_manager.clear_cache()
                self.key_manager.cache_key(new_key)

            logger.info("Пароль успешно изменен, записи перешифрованы")
            return True, None

        except Exception as e:
            if conn:
                conn.rollback()
                logger.info(f"Транзакция откачена из-за ошибки: {e}")

            error_msg = str(e)
            logger.error(f"Ошибка при смене пароля: {error_msg}")

            user_error = ["Не удалось сменить пароль. Операция отменена."]
            if "запись" in error_msg.lower():
                user_error.append("Ошибка при перешифровании записей.")
            else:
                user_error.append("Техническая ошибка. Пожалуйста, попробуйте снова.")

            return False, user_error

        finally:
            if conn:
                conn.close()

    def logout(self):
        self.key_manager.clear_cache()
        self.logged_in = False
        self.login_time = None
        self.last_activity = None
        logger.info("Выход из системы")

    def update_activity(self):
        self.last_activity = time.time()
        if self.key_manager:
            self.key_manager.update_activity()

    def _check_password_strength(self, password: str) -> Tuple[bool, List[str]]:
        errors = []

        if len(password) < 12:
            errors.append(f"Пароль должен быть минимум 12 символов (сейчас {len(password)})")
            return False, errors

        has_upper = any(c.isupper() for c in password)
        has_lower = any(c.islower() for c in password)
        has_digit = any(c.isdigit() for c in password)
        has_special = any(not c.isalnum() for c in password)

        if not has_upper:
            errors.append("Нужна хотя бы одна ЗАГЛАВНАЯ буква")
        if not has_lower:
            errors.append("Нужна хотя бы одна строчная буква")
        if not has_digit:
            errors.append("Нужна хотя бы одна цифра")
        if not has_special:
            errors.append("Нужен хотя бы один спецсимвол (!@#$%^&*)")

        very_simple = ["password", "qwerty", "12345678", "admin", "letmein"]
        if password.lower() in very_simple:
            errors.append("Слишком простой пароль")

        return len(errors) == 0, errors

    def get_password_strength_text(self, password: str) -> Tuple[str, str]:
        if not password:
            return "Введите пароль", "orange"

        if len(password) < 8:
            return "Очень слабый", "red"
        elif len(password) < 12:
            return "Слабый", "orange"

        has_upper = any(c.isupper() for c in password)
        has_lower = any(c.islower() for c in password)
        has_digit = any(c.isdigit() for c in password)
        has_special = any(not c.isalnum() for c in password)

        if has_upper and has_lower and has_digit and has_special:
            return "Надежный", "green"
        else:
            return "Средний", "orange"

    def get_session_info(self) -> dict:
        return {
            "logged_in": self.logged_in,
            "login_time": self.login_time,
            "last_activity": self.last_activity,
            "failed_attempts": self.failed_attempts
        }

    def verify_password(self, password: str) -> bool:
        return self.login(password) is not None