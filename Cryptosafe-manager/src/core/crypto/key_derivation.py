from argon2 import PasswordHasher, Type
from argon2.exceptions import VerificationError
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.backends import default_backend
import os
import secrets
import logging
from typing import Optional, Dict

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

    def create_auth_hash(self, password: str) -> str:
        try:
            return self.argon2_hasher.hash(password)
        except Exception as e:
            logger.error(f"Ошибка создания хэша: {e}")
            raise

    def verify_password(self, password: str, stored_hash: str) -> bool:
        try:
            return self.argon2_hasher.verify(stored_hash, password)
        except VerificationError:
            secrets.compare_digest(b'dummy', b'dummy')
            return False
        except Exception:
            return False

    def generate_salt(self) -> bytes:
        return os.urandom(16)

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