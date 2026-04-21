from typing import Optional
import hashlib
import hmac
import logging

logger = logging.getLogger(__name__)
try:
    from cryptography.hazmat.primitives.asymmetric import ed25519
    from cryptography.hazmat.primitives import serialization

    CRYPTOGRAPHY_AVAILABLE = True
except ImportError:
    CRYPTOGRAPHY_AVAILABLE = False
    logger.warning("cryptography library not available, using HMAC-SHA256 fallback")


class AuditLogSigner:
    def __init__(self, key_manager):
        self.key_manager = key_manager
        self._use_ed25519 = CRYPTOGRAPHY_AVAILABLE
        self._private_key = None
        self._public_key = None
        self._hmac_key = None
        self._key_derived = False

    def _ensure_keys_derived(self):
        if self._key_derived:
            return

        try:
            if self._use_ed25519:
                self._init_ed25519_keys()
            else:
                self._init_hmac_key()

            self._key_derived = True

        except ValueError as e:
            logger.error(f"Failed to derive signing key: {e}")
            raise RuntimeError("Cannot derive signing key: master password not cached") from e

    def _init_ed25519_keys(self):
        key_material = self.key_manager.derive_key(
            purpose="audit-signing",
            length=32
        )
        self._private_key = ed25519.Ed25519PrivateKey.from_private_bytes(key_material)
        self._public_key = self._private_key.public_key()
        logger.info("AuditLogSigner initialized with Ed25519")

    def _init_hmac_key(self):
        key_material = self.key_manager.derive_key(
            purpose="audit-signing-hmac",
            length=32
        )
        self._hmac_key = key_material
        logger.info("AuditLogSigner initialized with HMAC-SHA256 (fallback)")

    def sign(self, data: bytes) -> bytes:
        self._ensure_keys_derived()
        if self._use_ed25519 and self._private_key:
            return self._private_key.sign(data)
        else:
            return hmac.new(self._hmac_key, data, hashlib.sha256).digest()

    def verify(self, data: bytes, signature: bytes) -> bool:
        self._ensure_keys_derived()
        try:
            if self._use_ed25519 and self._public_key:
                self._public_key.verify(signature, data)
                return True
            else:
                expected = hmac.new(self._hmac_key, data, hashlib.sha256).digest()
                return hmac.compare_digest(signature, expected)
        except Exception as e:
            logger.error(f"Signature verification failed: {e}")
            return False

    def get_public_key_bytes(self) -> Optional[bytes]:
        self._ensure_keys_derived()
        if self._use_ed25519 and self._public_key:
            return self._public_key.public_bytes(
                encoding=serialization.Encoding.Raw,
                format=serialization.PublicFormat.Raw
            )
        return None

    def get_algorithm_name(self) -> str:
        return "Ed25519" if self._use_ed25519 else "HMAC-SHA256"

    def get_signature_size(self) -> int:
        return 64 if self._use_ed25519 else 32

    def clear(self):
        self._private_key = None
        self._public_key = None
        self._hmac_key = None
        self._key_derived = False
        logger.debug("Signing keys cleared from memory")