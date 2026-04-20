from argon2 import PasswordHasher, Type
from argon2.exceptions import VerificationError
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.backends import default_backend
import os
import secrets
import logging
from typing import Optional, Dict
import hashlib
import hmac

logger = logging.getLogger(__name__)


class KeyDerivation:

    def __init__(self, config: Optional[Dict] = None):
        if config is None:
            config = {}

        # Argon2 параметры с возможностью переопределения через config
        self.argon2_hasher = PasswordHasher(
            time_cost=config.get('argon2_time', 3),
            memory_cost=config.get('argon2_memory', 64 * 1024),
            parallelism=config.get('argon2_parallelism', 4),
            hash_len=32,
            salt_len=16,
            type=Type.ID
        )

        # PBKDF2 параметры
        self.pbkdf2_iterations = config.get('pbkdf2_iterations', 600000)

    # создания хэша для аутентификации
    def create_auth_hash(self, password: str) -> str:
        try:
            return self.argon2_hasher.hash(password)
        except Exception as e:
            logger.error(f"Ошибка создания хэша: {e}")
            raise

    # верификация пароля (извлечение соли из stored_hash)
    def verify_password(self, password: str, stored_hash: str) -> bool:
        try:

            is_valid = self.argon2_hasher.verify(stored_hash, password)

            expected = b"true" if is_valid else b"false"
            actual = b"true"

            return secrets.compare_digest(expected, actual)

        except VerificationError:
            expected = b"false"
            actual = b"true"
            return secrets.compare_digest(expected, actual)
        except Exception:
            return False

    def generate_salt(self) -> bytes:
        return os.urandom(16)

    # создания ключ шифрования из пароля
    def derive_encryption_key(self, password: str, salt: bytes) -> bytes:
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=self.pbkdf2_iterations,
            backend=default_backend()
        )
        return kdf.derive(password.encode())

    def get_params(self) -> dict:
        return {
            'argon2_time': self.argon2_hasher.time_cost,
            'argon2_memory': self.argon2_hasher.memory_cost,
            'argon2_parallelism': self.argon2_hasher.parallelism,
            'pbkdf2_iterations': self.pbkdf2_iterations
        }

    def derive_key_with_hkdf(self, master_key: bytes, context: str, length: int = 32) -> bytes:
        hash_func = hashlib.sha256
        hash_len = 32

        salt = b"cryptosafe-hkdf-v1"

        if isinstance(context, str):
            context = context.encode('utf-8')

        prk = hmac.new(salt, master_key, hash_func).digest()

        output = b""
        counter = 1
        while len(output) < length:
            if counter == 1:
                data = context + bytes([counter])
            else:
                prev_chunk = output[-hash_len:]
                data = prev_chunk + context + bytes([counter])

            chunk = hmac.new(prk, data, hash_func).digest()
            output += chunk
            counter += 1

        return output[:length]