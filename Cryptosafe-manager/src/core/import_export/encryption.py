import os
import json
import base64
import hashlib
from datetime import datetime
from typing import Optional, Dict, Any, Union, Tuple
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.backends import default_backend


class ExportEncryptionService:

    def __init__(self, password: Optional[str] = None, public_key: Optional[bytes] = None):

        if password is None and public_key is None:
            raise ValueError("Either password or public_key must be provided")

        self.password = password
        self.public_key = public_key
        self._encryption_method = "password" if password else "public_key"

        self._export_key = None
        self._salt = None
        self._nonce = None
        self._iterations = 100000
        self._encrypted_ephemeral = None

        if password:
            self._derive_export_key(password)

    def _derive_export_key(self, password: str, salt: Optional[bytes] = None) -> None:

        self._salt = salt or os.urandom(16)

        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=self._salt,
            iterations=self._iterations,
            backend=default_backend()
        )
        self._export_key = kdf.derive(password.encode('utf-8'))

    def _encrypt_with_password(self, plaintext: bytes) -> Tuple[bytes, bytes, bytes]:

        self._nonce = os.urandom(12)

        aesgcm = AESGCM(self._export_key)
        ciphertext = aesgcm.encrypt(self._nonce, plaintext, None)

        return self._nonce, ciphertext, None

    def _encrypt_with_public_key(self, plaintext: bytes) -> Tuple[bytes, bytes, bytes, bytes]:

        ephemeral_key = os.urandom(32)

        self._nonce = os.urandom(12)

        aesgcm = AESGCM(ephemeral_key)
        ciphertext = aesgcm.encrypt(self._nonce, plaintext, None)

        pub_key = serialization.load_pem_public_key(self.public_key)
        self._encrypted_ephemeral = pub_key.encrypt(
            ephemeral_key,
            padding.OAEP(
                mgf=padding.MGF1(algorithm=hashes.SHA256()),
                algorithm=hashes.SHA256(),
                label=None
            )
        )

        ephemeral_key = None

        return self._encrypted_ephemeral, self._nonce, ciphertext, None

    def encrypt(self, data: Union[Dict[str, Any], bytes]) -> Dict[str, Any]:

        if isinstance(data, dict):
            plaintext = json.dumps(data, sort_keys=True, default=str).encode('utf-8')
        else:
            plaintext = data

        if self._encryption_method == "password":
            nonce, ciphertext, _ = self._encrypt_with_password(plaintext)
        else:
            encrypted_key, nonce, ciphertext, _ = self._encrypt_with_public_key(plaintext)

        package = {
            "version": "1.0",
            "export_id": self._generate_export_id(),
            "encryption": {
                "method": self._encryption_method,
                "key_purpose": "export",
                "key_separation": True,
                "algorithm": "AES-256-GCM",
                "nonce": base64.b64encode(nonce).decode('ascii'),
                "timestamp": datetime.utcnow().isoformat() + "Z",
                "source": "CryptoSafe Manager"
            },
            "data": base64.b64encode(ciphertext).decode('ascii')
        }

        if self._encryption_method == "password":
            package["encryption"].update({
                "key_derivation": "PBKDF2-HMAC-SHA256",
                "iterations": self._iterations,
                "salt": base64.b64encode(self._salt).decode('ascii')
            })
        else:
            package["encryption"].update({
                "asymmetric_algorithm": "RSA-OAEP",
                "key_size": 2048,
                "encrypted_key": base64.b64encode(self._encrypted_ephemeral).decode('ascii')
            })

        return package

    def _generate_export_id(self) -> str:
        import uuid
        return str(uuid.uuid4())

    def clear_sensitive_data(self) -> None:
        if self._export_key:
            for i in range(len(self._export_key)):
                self._export_key = self._export_key[:i] + b'\x00' + self._export_key[i + 1:]
        self._export_key = None
        self._salt = None
        self._nonce = None
        self._encrypted_ephemeral = None


class ExportDecryptionService:

    def __init__(self, password: Optional[str] = None, private_key: Optional[bytes] = None):

        if password is None and private_key is None:
            raise ValueError("Either password or private_key must be provided")

        self.password = password
        self.private_key = private_key
        self._integrity_verified = False

    def _decrypt_with_password(self, encrypted_data: bytes, salt: bytes,
                               nonce: bytes, iterations: int) -> bytes:

        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=iterations,
            backend=default_backend()
        )
        key = kdf.derive(self.password.encode('utf-8'))

        aesgcm = AESGCM(key)
        plaintext = aesgcm.decrypt(nonce, encrypted_data, None)

        key = None

        return plaintext

    def _decrypt_with_private_key(self, encrypted_data: bytes, encrypted_key: bytes,
                                  nonce: bytes) -> bytes:

        priv_key = serialization.load_pem_private_key(
            self.private_key,
            password=None,
            backend=default_backend()
        )

        ephemeral_key = priv_key.decrypt(
            encrypted_key,
            padding.OAEP(
                mgf=padding.MGF1(algorithm=hashes.SHA256()),
                algorithm=hashes.SHA256(),
                label=None
            )
        )

        aesgcm = AESGCM(ephemeral_key)
        plaintext = aesgcm.decrypt(nonce, encrypted_data, None)

        ephemeral_key = None

        return plaintext

    def decrypt(self, export_package: Dict[str, Any]) -> Dict[str, Any]:

        encryption_info = export_package.get("encryption", {})
        method = encryption_info.get("method")

        if not method:
            raise ValueError("Invalid export package: missing encryption method")

        if not encryption_info.get("key_separation"):
            raise ValueError("Export package must use key separation (ARC-2 compliant)")

        encrypted_data = base64.b64decode(export_package["data"])

        nonce = base64.b64decode(encryption_info["nonce"])

        try:
            if method == "password":
                if not self.password:
                    raise ValueError("Password required for decryption")

                salt = base64.b64decode(encryption_info["salt"])
                iterations = encryption_info.get("iterations", 100000)

                plaintext = self._decrypt_with_password(
                    encrypted_data, salt, nonce, iterations
                )

            elif method == "public_key":
                if not self.private_key:
                    raise ValueError("Private key required for decryption")

                encrypted_key = base64.b64decode(encryption_info["encrypted_key"])
                plaintext = self._decrypt_with_private_key(
                    encrypted_data, encrypted_key, nonce
                )

            else:
                raise ValueError(f"Unknown encryption method: {method}")

        except Exception as e:
            raise ValueError(f"Decryption failed - data may be corrupted or tampered: {e}")

        try:
            return json.loads(plaintext.decode('utf-8'))
        except json.JSONDecodeError as e:
            raise ValueError(f"Failed to parse decrypted data: {e}")

    def verify_integrity(self, export_package: Dict[str, Any], decrypted_data: Dict[str, Any]) -> bool:

        integrity_info = export_package.get("integrity", {})
        expected_hash = integrity_info.get("hash")

        if not expected_hash:
            return False

        calculated_hash = hashlib.sha256(
            json.dumps(decrypted_data, sort_keys=True).encode()
        ).hexdigest()

        self._integrity_verified = (calculated_hash == expected_hash)
        return self._integrity_verified

def create_encrypted_export(data: Dict[str, Any], password: str) -> Dict[str, Any]:

    service = ExportEncryptionService(password=password)
    try:
        package = service.encrypt(data)

        data_hash = hashlib.sha256(
            json.dumps(data, sort_keys=True).encode()
        ).hexdigest()

        package["integrity"] = {
            "hash": data_hash,
            "hash_algorithm": "SHA256"
        }

        return package
    finally:
        service.clear_sensitive_data()


def decrypt_export_package(package: Dict[str, Any], password: str) -> Dict[str, Any]:

    service = ExportDecryptionService(password=password)
    decrypted_data = service.decrypt(package)

    if not service.verify_integrity(package, decrypted_data):
        raise ValueError("Integrity check failed - data may be corrupted")

    return decrypted_data