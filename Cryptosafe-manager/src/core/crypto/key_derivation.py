from argon2 import PasswordHasher, Type
from argon2.exceptions import VerificationError
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.backends import default_backend
import os
import secrets
import logging

logger = logging.getLogger(__name__)


class KeyDerivation:

    def __init__(self):
        # Argon2 параметры (HASH-2)
        self.argon2_hasher = PasswordHasher(
            time_cost=3,  # 3 итерации
            memory_cost=64 * 1024,  # 64 МБ
            parallelism=4,  # 4 потока
            hash_len=32,  # 32 байта
            salt_len=16,
            type=Type.ID
        )

        # PBKDF2 параметры (KEY-2)
        self.pbkdf2_iterations = 100000  # минимум 100000

    def create_auth_hash(self, password: str) -> str:
        try:
            return self.argon2_hasher.hash(password)
        except Exception as e:
            logger.error(f"Ошибка создания хэша: {e}")
            raise

    def verify_password(self, password: str, stored_hash: str) -> bool:

        try:
            # Argon2 сам делает сравнение за константное время
            return self.argon2_hasher.verify(stored_hash, password)
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
        return kdf.derive(password.encode())

    def get_params(self) -> dict:
        return {
            'argon2_time': self.argon2_hasher.time_cost,
            'argon2_memory': self.argon2_hasher.memory_cost,
            'argon2_parallelism': self.argon2_hasher.parallelism,
            'pbkdf2_iterations': self.pbkdf2_iterations
        }