import os
import json
import logging
import time
from typing import Optional, Dict
from pathlib import Path

try:
    import keyring
    from keyring.errors import KeyringError

    KEYRING_AVAILABLE = True
except ImportError:
    KEYRING_AVAILABLE = False
    logging.warning("keyring не установлен, будет использовано только файловое хранилище")

logger = logging.getLogger(__name__)


class KeyStorage:

    def __init__(self, app_name: str = "CryptoSafe", use_cache: bool = True, cache_ttl: int = 3600):
        self.app_name = app_name
        self.use_cache = use_cache
        self.cache_ttl = cache_ttl

        self.cache_dir = Path.home() / ".cache" / app_name.lower()
        self.cache_file = self.cache_dir / "key_cache.json"

        self.cache_dir.mkdir(mode=0o700, parents=True, exist_ok=True)

        self._memory_cache: Dict[str, Dict] = {}
        self._load_cache()

    # сохраняет ключ в keyring
    def store_key(self, service: str, key: bytes) -> bool:
        success = False

        if KEYRING_AVAILABLE:
            try:
                keyring.set_password(self.app_name, service, key.hex())
                logger.info(f"Ключ {service} сохранен в keyring")
                success = True
            except Exception as e:
                logger.warning(f"Ошибка keyring: {e}")
                success = False
        else:
            success = False

        if self.use_cache and (not success or self.cache_ttl > 0):
            self._update_cache(service, key)
            logger.info(f"Ключ {service} сохранен в кэш")

        return success or (self.use_cache and self._get_cached_key(service) is not None)

    def get_key(self, service: str) -> Optional[bytes]:
        key = None

        if service in self._memory_cache:
            cached = self._memory_cache[service]
            if self.cache_ttl == 0 or time.time() - cached['timestamp'] < self.cache_ttl:
                key = cached['key']
                logger.debug(f"Ключ {service} получен из memory cache")
                return key
            else:
                del self._memory_cache[service]

        if KEYRING_AVAILABLE:
            try:
                key_hex = keyring.get_password(self.app_name, service)
                if key_hex:
                    key = bytes.fromhex(key_hex)
                    logger.info(f"Ключ {service} получен из keyring")

                    if self.use_cache:
                        self._update_cache(service, key)

                    return key
            except Exception as e:
                logger.warning(f"Ошибка keyring: {e}")

        if self.use_cache:
            key = self._get_cached_key(service)
            if key:
                logger.info(f"Ключ {service} получен из файлового кэша")
                return key

        return None

    def delete_key(self, service: str) -> bool:
        success = True

        if KEYRING_AVAILABLE:
            try:
                keyring.delete_password(self.app_name, service)
                logger.info(f"Ключ {service} удален из keyring")
            except Exception as e:
                logger.warning(f"Ошибка удаления из keyring: {e}")
                success = False

        self._delete_from_cache(service)

        return success

    def _update_cache(self, service: str, key: bytes):
        self._memory_cache[service] = {
            'key': key,
            'timestamp': time.time()
        }

        try:
            cache_data = self._load_cache_file()
            cache_data[service] = {
                'key': key.hex(),
                'timestamp': time.time()
            }

            with open(self.cache_file, 'w') as f:
                json.dump(cache_data, f)

            os.chmod(self.cache_file, 0o600)

        except Exception as e:
            logger.error(f"Ошибка сохранения файлового кэша: {e}")

    def _get_cached_key(self, service: str) -> Optional[bytes]:
        if service in self._memory_cache:
            cached = self._memory_cache[service]
            if self.cache_ttl == 0 or time.time() - cached['timestamp'] < self.cache_ttl:
                return cached['key']

        try:
            cache_data = self._load_cache_file()
            if service in cache_data:
                entry = cache_data[service]
                if self.cache_ttl == 0 or time.time() - entry['timestamp'] < self.cache_ttl:
                    key = bytes.fromhex(entry['key'])

                    self._memory_cache[service] = {
                        'key': key,
                        'timestamp': entry['timestamp']
                    }

                    return key
        except Exception as e:
            logger.error(f"Ошибка чтения файлового кэша: {e}")

        return None

    def _delete_from_cache(self, service: str):
        if service in self._memory_cache:
            del self._memory_cache[service]

        try:
            cache_data = self._load_cache_file()
            if service in cache_data:
                del cache_data[service]
                with open(self.cache_file, 'w') as f:
                    json.dump(cache_data, f)
        except Exception as e:
            logger.error(f"Ошибка удаления из файлового кэша: {e}")

    def _load_cache_file(self) -> dict:
        if self.cache_file.exists():
            try:
                with open(self.cache_file, 'r') as f:
                    return json.load(f)
            except:
                pass
        return {}

    # загружает кэш в память при инициализации
    def _load_cache(self):
        cache_data = self._load_cache_file()
        for service, entry in cache_data.items():
            if self.cache_ttl == 0 or time.time() - entry['timestamp'] < self.cache_ttl:
                try:
                    self._memory_cache[service] = {
                        'key': bytes.fromhex(entry['key']),
                        'timestamp': entry['timestamp']
                    }
                except:
                    pass

    def clear_cache(self):
        self._memory_cache.clear()
        if self.cache_file.exists():
            self.cache_file.unlink()