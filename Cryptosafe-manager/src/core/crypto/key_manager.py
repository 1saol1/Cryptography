from .key_derivation import KeyDerivation
from .secure_memory import SecureMemory
import time
from typing import Optional
import logging

logger = logging.getLogger(__name__)


class KeyManager:

    def __init__(self):
        self.derivation = KeyDerivation()
        self.secure_memory = SecureMemory()

        # Кэш
        self._cached_key = None
        self._last_activity = time.time()
        self._session_start = None

    def create_auth_hash(self, password: str) -> str:
        return self.derivation.create_auth_hash(password)

    def verify_password(self, password: str, stored_hash: str) -> bool:
        return self.derivation.verify_password(password, stored_hash)

    def generate_salt(self) -> bytes:
        return self.derivation.generate_salt()

    def derive_encryption_key(self, password: str, salt: bytes) -> bytes:
        return self.derivation.derive_encryption_key(password, salt)

    def cache_key(self, key: bytes) -> None:
        self.clear_cache()
        self._cached_key = self.secure_memory.secure_store(key)
        self._session_start = time.time()
        self._last_activity = time.time()
        logger.debug("Ключ закэширован")

    def get_cached_key(self) -> Optional[bytes]:
        if self._cached_key is None:
            return None

        # Проверяем время бездействия (1 час)
        if time.time() - self._last_activity > 3600:
            self.clear_cache()
            return None

        # Проверяем время сессии (1 час)
        if self._session_start and time.time() - self._session_start > 3600:
            self.clear_cache()
            return None

        return self._cached_key

    def clear_cache(self) -> None:
        if self._cached_key:
            self.secure_memory.secure_clear(self._cached_key)
            self._cached_key = None
            self._session_start = None
            logger.debug("Кэш очищен")

    def update_activity(self) -> None:
        self._last_activity = time.time()

    def on_app_minimize(self) -> None:
        logger.debug("Приложение свернуто - очищаем ключи")
        self.clear_cache()

    def get_params(self) -> dict:
        return self.derivation.get_params()