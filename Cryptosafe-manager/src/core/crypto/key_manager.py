from argon2 import PasswordHasher, Type
from argon2.exceptions import VerificationError
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.backends import default_backend
from .secure_memory import SecureMemory
import os
import secrets
import time
from typing import Optional
import logging

logger = logging.getLogger(__name__)


class KeyManager:

    def __init__(self):
        # Настройки Argon2 (из задания HASH-2)
        self.argon2_hasher = PasswordHasher(
            time_cost=3,  # 3 итерации
            memory_cost=64 * 1024,  # 64 МБ
            parallelism=4,  # 4 потока
            hash_len=32,  # 32 байта
            salt_len=16,
            type=Type.ID
        )

        # Настройки PBKDF2 (из задания KEY-2)
        self.pbkdf2_iterations = 100000  # минимум 100000
        self.secure_memory = SecureMemory()

        # Кэш для ключа шифрования
        self._cached_key = None
        self._last_activity = time.time()
        self._session_start = None

        logger.info("KeyManager инициализирован")

    def create_auth_hash(self, password: str) -> str:
        try:
            return self.argon2_hasher.hash(password)
        except Exception as e:
            logger.error(f"Ошибка создания хэша: {e}")
            raise

    def verify_password(self, password: str, stored_hash: str) -> bool:
        try:
            # Argon2 сам делает сравнение за константное время
            result = self.argon2_hasher.verify(stored_hash, password)
            self._update_activity()
            return result
        except VerificationError:
            # Заглушка для константного времени
            secrets.compare_digest(b'dummy', b'dummy')
            return False
        except Exception:
            return False

    def generate_salt(self) -> bytes:
        return os.urandom(16)

    def derive_encryption_key(self, password: str, salt: bytes) -> bytes:
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,  # 32 байта = AES-256
            salt=salt,
            iterations=self.pbkdf2_iterations,
            backend=default_backend()
        )
        key = kdf.derive(password.encode())
        self._update_activity()
        return key

    def cache_key(self, key: bytes) -> None:
        # Очищаем старый ключ
        self.clear_cache()

        # Сохраняем новый
        self._cached_key = self.secure_memory.secure_store(key)
        self._session_start = time.time()
        self._last_activity = time.time()
        logger.debug("Ключ закэширован")

    def get_cached_key(self) -> Optional[bytes]:
        if self._cached_key is None:
            return None

        # Проверяем время бездействия (1 час - из задания CACHE-2)
        idle_time = time.time() - self._last_activity
        if idle_time > 3600:  # 1 час в секундах
            logger.debug("Ключ удален из-за неактивности")
            self.clear_cache()
            return None

        # Проверяем общее время сессии (тоже 1 час)
        if self._session_start:
            session_time = time.time() - self._session_start
            if session_time > 3600:
                logger.debug("Ключ удален из-за истечения сессии")
                self.clear_cache()
                return None

        return self._cached_key

    def clear_cache(self) -> None:
        if self._cached_key:
            self.secure_memory.secure_clear(self._cached_key)
            self._cached_key = None
            self._session_start = None
            logger.debug("Кэш очищен")

    def _update_activity(self) -> None:
        self._last_activity = time.time()

    def on_app_minimize(self) -> None:
        logger.debug("Приложение свернуто - чистим ключи")
        self.clear_cache()