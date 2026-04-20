from .key_derivation import KeyDerivation
from .secure_memory import SecureMemory
import time
from typing import Optional, Dict
import logging

logger = logging.getLogger(__name__)


class KeyManager:

    def __init__(self, config: Optional[Dict] = None):
        if config is None:
            config = {}

        validated_config = self._validate_config(config)

        self.derivation = KeyDerivation(validated_config)
        self.secure_memory = SecureMemory()

        # кэш
        self._cached_key = None
        self._last_activity = time.time()
        self._session_start = None

    def _validate_config(self, config: Dict) -> Dict:
        validated = {}

        argon2_time = config.get('argon2_time', 3)
        if argon2_time > 10:
            logger.warning(f"Слишком большое значение argon2_time ({argon2_time}), установлено 10")
            validated['argon2_time'] = 10
        elif argon2_time < 1:
            validated['argon2_time'] = 3
        else:
            validated['argon2_time'] = argon2_time

        argon2_memory = config.get('argon2_memory', 64 * 1024)
        if argon2_memory > 1024 * 1024:  # 1 ГБ в килобайтах
            logger.warning(f"Слишком большое значение argon2_memory ({argon2_memory}), установлено 1 ГБ")
            validated['argon2_memory'] = 1024 * 1024
        elif argon2_memory < 8 * 1024:  # минимум 8 МБ
            validated['argon2_memory'] = 64 * 1024
        else:
            validated['argon2_memory'] = argon2_memory

        argon2_parallelism = config.get('argon2_parallelism', 4)
        if argon2_parallelism > 64:
            logger.warning(f"Слишком большое значение argon2_parallelism ({argon2_parallelism}), установлено 64")
            validated['argon2_parallelism'] = 64
        elif argon2_parallelism < 1:
            validated['argon2_parallelism'] = 4
        else:
            validated['argon2_parallelism'] = argon2_parallelism

        pbkdf2_iterations = config.get('pbkdf2_iterations', 600000)
        if pbkdf2_iterations > 10_000_000:  # максимум 10 миллионов
            logger.warning(f"Слишком большое значение pbkdf2_iterations ({pbkdf2_iterations}), установлено 10 млн")
            validated['pbkdf2_iterations'] = 10_000_000
        elif pbkdf2_iterations < 100_000:
            validated['pbkdf2_iterations'] = 600_000
        else:
            validated['pbkdf2_iterations'] = pbkdf2_iterations

        return validated

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

        if time.time() - self._last_activity > 3600:
            self.clear_cache()
            return None

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

    def derive_key(self, purpose: str, length: int = 32) -> bytes:
        cached_key = self.get_cached_key()
        if cached_key is None:
            raise ValueError(
                "No master key cached. User must authenticate first before deriving keys."
            )

        derived_key = self.derivation.derive_key_with_hkdf(
            master_key=cached_key,
            context=f"cryptosafe-{purpose}-v1",
            length=length
        )

        logger.debug(f"Derived {length}-byte key for purpose: {purpose}")
        return derived_key