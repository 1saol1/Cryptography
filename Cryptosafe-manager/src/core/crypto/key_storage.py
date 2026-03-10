import os
import json
import logging
from typing import Optional

try:
    import keyring
    from keyring.errors import KeyringError

    KEYRING_AVAILABLE = True
except ImportError:
    KEYRING_AVAILABLE = False
    logging.warning("keyring не установлен, будет использовано только файловое хранилище")

logger = logging.getLogger(__name__)


class KeyStorage:

    def __init__(self, app_name: str = "CryptoSafe"):
        self.app_name = app_name
        self.fallback_dir = os.path.expanduser("~/.cryptosafe")
        self.fallback_file = os.path.join(self.fallback_dir, "key_storage.json")

        # Создаем папку для файлового хранилища
        os.makedirs(self.fallback_dir, exist_ok=True)

    def store_key(self, service: str, key: bytes) -> bool:
        # Пробуем keyring если доступен
        if KEYRING_AVAILABLE:
            try:
                keyring.set_password(
                    self.app_name,
                    service,
                    key.hex()
                )
                logger.info(f"Ключ {service} сохранен в keyring")
                return True
            except Exception as e:
                logger.warning(f"Ошибка keyring: {e}. Использую файл.")

        # Резервное файловое хранилище
        return self._store_key_file(service, key)

    def get_key(self, service: str) -> Optional[bytes]:
        # Пробуем keyring
        if KEYRING_AVAILABLE:
            try:
                key_hex = keyring.get_password(self.app_name, service)
                if key_hex:
                    return bytes.fromhex(key_hex)
            except Exception as e:
                logger.warning(f"Ошибка keyring: {e}")

        # Пробуем файл
        return self._get_key_file(service)

    def delete_key(self, service: str) -> bool:
        # Удаляем из keyring
        if KEYRING_AVAILABLE:
            try:
                keyring.delete_password(self.app_name, service)
            except:
                pass

        # Удаляем из файла
        return self._delete_key_file(service)

    def _store_key_file(self, service: str, key: bytes) -> bool:
        try:
            # Загружаем существующие ключи
            keys = self._load_keys_file()
            keys[service] = key.hex()

            # Сохраняем
            with open(self.fallback_file, 'w') as f:
                json.dump(keys, f)

            # Устанавливаем права только для владельца
            os.chmod(self.fallback_file, 0o600)

            logger.info(f"Ключ {service} сохранен в файл")
            return True
        except Exception as e:
            logger.error(f"Ошибка сохранения в файл: {e}")
            return False

    def _get_key_file(self, service: str) -> Optional[bytes]:
        try:
            keys = self._load_keys_file()
            if service in keys:
                return bytes.fromhex(keys[service])
        except Exception as e:
            logger.error(f"Ошибка чтения из файла: {e}")
        return None

    def _delete_key_file(self, service: str) -> bool:
        try:
            keys = self._load_keys_file()
            if service in keys:
                del keys[service]
                with open(self.fallback_file, 'w') as f:
                    json.dump(keys, f)
                return True
        except Exception as e:
            logger.error(f"Ошибка удаления из файла: {e}")
        return False

    def _load_keys_file(self) -> dict:
        if os.path.exists(self.fallback_file):
            try:
                with open(self.fallback_file, 'r') as f:
                    return json.load(f)
            except:
                pass
        return {}