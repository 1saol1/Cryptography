from typing import Dict, Any, Optional, List, Tuple
from datetime import datetime, timedelta
import json
import base64
import uuid
import logging
from enum import Enum

from src.core.import_export.encryption import ExportEncryptionService, ExportDecryptionService
from src.core.import_export.key_exchange import QRCodeService
import os
import hashlib
import hmac as hmac_stdlib
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec, padding as asym_padding
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.backends import default_backend

logger = logging.getLogger(__name__)

SHARING_PBKDF2_ITERATIONS = 100_000
SHARING_KEY_LENGTH = 32
SHARING_SALT_LENGTH = 16
SHARING_NONCE_LENGTH = 12

SHARING_HMAC_KEY_LENGTH = 32


class SharingMethod:
    PASSWORD = "password"
    PUBLIC_KEY = "public_key"
    TIME_LIMITED = "time_limited"


class Permission:
    READ_ONLY = "read_only"
    READ_WRITE = "read_write"


class ShareWorkflowStep(Enum):
    SELECT_ENTRY = 1
    SELECT_RECIPIENT = 2
    CHOOSE_ENCRYPTION = 3
    SET_EXPIRATION = 4
    GENERATE_PACKAGE = 5
    DELIVER = 6


class RecipientWorkflowStep(Enum):
    RECEIVE_SHARE = 1
    DECRYPT = 2
    REVIEW = 3
    SAVE_OR_USE_TEMPORARY = 4


class SharingService:

    def __init__(self, db_connection, crypto_service, key_manager, audit_logger=None,
                 entry_manager=None):
        self.db = db_connection
        self.crypto = crypto_service
        self.key_manager = key_manager
        self.audit_logger = audit_logger
        self.entry_manager = entry_manager
        self.qr_service = QRCodeService()

        self._share_drafts = {}
        self._temporary_entries = {}

    def get_shareable_entries(self) -> List[Dict[str, Any]]:
        if not self.entry_manager:
            raise ValueError("Entry manager not available")

        all_entries = self.entry_manager.get_all_entries()

        shareable = []
        for entry in all_entries:
            shareable.append({
                "id": entry.get("id"),
                "title": entry.get("title"),
                "username": entry.get("username"),
                "category": entry.get("category", "Общее"),
                "has_password": bool(entry.get("password")),
                "has_notes": bool(entry.get("notes")),
                "has_totp": bool(entry.get("totp_secret"))
            })

        return shareable

    def validate_entry_for_sharing(self, entry_id: str) -> Dict[str, Any]:
        if not self.entry_manager:
            raise ValueError("Entry manager not available")

        try:
            entry = self.entry_manager.get_entry(entry_id)
            active_shares = self._get_active_shares_for_entry(entry_id)

            return {
                "valid": True,
                "entry_id": entry_id,
                "title": entry.get("title"),
                "has_active_shares": len(active_shares) > 0,
                "active_share_count": len(active_shares),
                "can_share": True,
                "message": "Entry is ready for sharing"
            }
        except Exception as e:
            return {
                "valid": False,
                "entry_id": entry_id,
                "can_share": False,
                "message": str(e)
            }

    def _get_active_shares_for_entry(self, entry_id: str) -> List[Dict[str, Any]]:
        cursor = self.db.execute(
            """
            SELECT share_id, recipient, encryption_method, expires_at
            FROM shared_entries
            WHERE original_entry_id = ? AND expires_at > ?
            """,
            (entry_id, datetime.utcnow())
        )
        rows = cursor.fetchall()

        return [
            {
                "share_id": row[0],
                "recipient": row[1],
                "method": row[2],
                "expires_at": row[3]
            }
            for row in rows
        ]

    def get_available_recipients(self) -> List[Dict[str, Any]]:
        try:
            cursor = self.db.execute(
                """
                SELECT contact_id, name, email, public_key_fingerprint, has_public_key
                FROM contacts
                WHERE is_active = 1
                ORDER BY name
                """
            )
            rows = cursor.fetchall()

            return [
                {
                    "id": row[0],
                    "name": row[1],
                    "email": row[2],
                    "public_key_fingerprint": row[3],
                    "has_public_key": bool(row[4])
                }
                for row in rows
            ]
        except Exception as e:
            logger.warning(f"Failed to get recipients: {e}")
            return []

    def add_recipient(self, name: str, email: str = None,
                      public_key: bytes = None) -> Dict[str, Any]:
        import hashlib

        contact_id = str(uuid.uuid4())
        fingerprint = None

        if public_key:
            fingerprint = hashlib.sha256(public_key).hexdigest()[:16]

        self.db.execute(
            """
            INSERT INTO contacts (contact_id, name, email, public_key, public_key_fingerprint, is_active)
            VALUES (?, ?, ?, ?, ?, 1)
            """,
            (contact_id, name, email, public_key, fingerprint)
        )

        if hasattr(self.db, 'commit'):
            self.db.commit()

        return {
            "id": contact_id,
            "name": name,
            "email": email,
            "public_key_fingerprint": fingerprint
        }

    def get_available_methods(self, recipient_id: str = None) -> List[Dict[str, Any]]:
        methods = [
            {
                "method": SharingMethod.PASSWORD,
                "name": "Парольная защита",
                "description": "Зашифровать файл с паролем. Пароль нужно передать отдельно.",
                "requires_recipient_key": False,
                "icon": "🔐",
                "recommended": True
            },
            {
                "method": SharingMethod.PUBLIC_KEY,
                "name": "Публичный ключ",
                "description": "Зашифровать публичным ключом получателя. Самый безопасный метод.",
                "requires_recipient_key": True,
                "icon": "🔑",
                "recommended": True
            },
            {
                "method": SharingMethod.TIME_LIMITED,
                "name": "Ограниченная ссылка",
                "description": "Создать ссылку с ограниченным сроком действия.",
                "requires_recipient_key": False,
                "icon": "⏰",
                "recommended": False
            }
        ]

        if recipient_id and not self._recipient_has_public_key(recipient_id):
            methods = [m for m in methods if m["method"] != SharingMethod.PUBLIC_KEY]

        return methods

    def _recipient_has_public_key(self, recipient_id: str) -> bool:
        cursor = self.db.execute(
            "SELECT public_key FROM contacts WHERE contact_id = ?",
            (recipient_id,)
        )
        row = cursor.fetchone()
        return row and row[0] is not None

    def get_valid_expiration_days(self) -> Dict[str, Any]:
        return {
            "min_days": 1,
            "max_days": 30,
            "presets": [1, 3, 7, 14, 30],
            "default": 7,
            "description": "Срок действия от 1 до 30 дней"
        }

    def validate_expiration(self, expires_in_days: int) -> Tuple[bool, str]:
        if expires_in_days < 1:
            return False, "Срок действия должен быть не менее 1 дня"
        if expires_in_days > 30:
            return False, "Срок действия должен быть не более 30 дней"
        return True, ""

    def _filter_entry_for_sharing(self, entry: Dict[str, Any],
                                   permissions: Dict[str, Any]) -> Dict[str, Any]:
        filtered = {
            "title": entry.get("title", ""),
            "username": entry.get("username", ""),
            "url": entry.get("url", ""),
        }

        if permissions.get("read_notes", True):
            filtered["notes"] = entry.get("notes", "")

        if permissions.get("read_password", True):
            filtered["password"] = entry.get("password", "")

        if permissions.get("read_totp", False):
            filtered["totp_secret"] = entry.get("totp_secret", "")

        if entry.get("category"):
            filtered["category"] = entry.get("category")

        if entry.get("tags"):
            filtered["tags"] = entry.get("tags")

        return filtered

    def _create_share_package(self, entry: Dict[str, Any],
                               share_id: str,
                               sharer: str,
                               permissions: Dict[str, Any],
                               expires_at: datetime) -> Dict[str, Any]:
        filtered_entry = self._filter_entry_for_sharing(entry, permissions)

        share_package = {
            "version": "1.0",
            "share_id": share_id,
            "share_format": "cryptosafe_share_v1",

            "sharer": sharer,
            "sharer_verified": True,

            "created_at": datetime.utcnow().isoformat() + "Z",
            "expires_at": expires_at.isoformat() + "Z",

            "permissions": {
                "access_type": permissions.get("access_type", Permission.READ_ONLY),
                "can_read": permissions.get("read", True),
                "can_edit": permissions.get("edit", False),
                "can_read_password": permissions.get("read_password", True),
                "can_read_notes": permissions.get("read_notes", True),
                "can_read_totp": permissions.get("read_totp", False),
                "can_share": permissions.get("share", False),
            },

            "entry": filtered_entry,
            "entry_id": entry.get("id"),
            "entry_version": entry.get("version", 1)
        }

        return share_package

    def _encrypt_share_package(self, share_package: Dict[str, Any],
                                method: str,
                                password: str = None,
                                public_key: bytes = None) -> Dict[str, Any]:
        plaintext = json.dumps(share_package, sort_keys=True, default=str).encode('utf-8')

        if method == SharingMethod.PASSWORD:
            if not password:
                password = self._generate_share_password()

            salt = os.urandom(SHARING_SALT_LENGTH)
            nonce = os.urandom(SHARING_NONCE_LENGTH)

            kdf = PBKDF2HMAC(
                algorithm=hashes.SHA256(),
                length=SHARING_KEY_LENGTH,
                salt=salt,
                iterations=SHARING_PBKDF2_ITERATIONS,
                backend=default_backend()
            )
            key = kdf.derive(password.encode('utf-8'))

            aesgcm = AESGCM(key)
            ciphertext = aesgcm.encrypt(nonce, plaintext, None)
            key = None

            hmac_salt = os.urandom(SHARING_SALT_LENGTH)
            hmac_kdf = PBKDF2HMAC(
                algorithm=hashes.SHA256(),
                length=SHARING_HMAC_KEY_LENGTH,
                salt=hmac_salt,
                iterations=SHARING_PBKDF2_ITERATIONS,
                backend=default_backend()
            )
            hmac_key = hmac_kdf.derive(password.encode('utf-8'))
            package_hmac = self._compute_hmac(hmac_key, ciphertext, nonce, salt)
            hmac_key = None

            encrypted = {
                "version": "1.0",
                "share_id": share_package["share_id"],
                "share_format": "cryptosafe_share_v1",
                "encryption": {
                    "method": "password",
                    "algorithm": "AES-256-GCM",
                    "key_purpose": "sharing",
                    "key_separation": True,
                    "key_derivation": {
                        "algorithm": "PBKDF2-HMAC-SHA256",
                        "iterations": SHARING_PBKDF2_ITERATIONS,
                        "salt": base64.b64encode(salt).decode('ascii'),
                        "key_length": SHARING_KEY_LENGTH
                    },
                    "nonce": base64.b64encode(nonce).decode('ascii'),
                },
                "data": base64.b64encode(ciphertext).decode('ascii'),
                # CRY-4: HMAC для проверки целостности до расшифровки
                "integrity": {
                    "hmac": package_hmac,
                    "hmac_algorithm": "HMAC-SHA256",
                    "hmac_key_derivation": "PBKDF2-HMAC-SHA256",
                    "hmac_salt": base64.b64encode(hmac_salt).decode('ascii'),
                    "tamper_evident": True
                },
                "share_password": password
            }
            return encrypted

        elif method == SharingMethod.PUBLIC_KEY:
            if not public_key:
                raise ValueError("Public key required")

            recipient_pub = serialization.load_pem_public_key(
                public_key if isinstance(public_key, bytes) else public_key.encode(),
                backend=default_backend()
            )

            if isinstance(recipient_pub, ec.EllipticCurvePublicKey):
                return self._encrypt_ecies(plaintext, recipient_pub, share_package)
            else:

                return self._encrypt_rsa_hybrid(plaintext, recipient_pub, share_package)

        else:
            auto_password = self._generate_share_password()
            enc_service = ExportEncryptionService(password=auto_password)
            try:
                encrypted = enc_service.encrypt(plaintext)
                encrypted["share_id"] = share_package["share_id"]
                encrypted["share_format"] = "cryptosafe_share_v1"
                encrypted["encryption"]["key_purpose"] = "sharing"
                encrypted["encryption"]["key_separation"] = True
                return encrypted
            finally:
                enc_service.clear_sensitive_data()

    def _decrypt_password_share(self, encrypted_package: Dict[str, Any],
                                 password: str) -> Dict[str, Any]:

        enc_info = encrypted_package.get("encryption", {})
        kd = enc_info.get("key_derivation", {})

        if not kd:
            raise ValueError("CRY-1: Отсутствуют параметры деривации ключа в пакете")

        salt = base64.b64decode(kd["salt"])
        iterations = kd.get("iterations", SHARING_PBKDF2_ITERATIONS)
        key_length = kd.get("key_length", SHARING_KEY_LENGTH)
        nonce = base64.b64decode(enc_info["nonce"])
        ciphertext = base64.b64decode(encrypted_package["data"])

        # CRY-4: Проверка HMAC ДО расшифровки (tamper evidence)
        integrity = encrypted_package.get("integrity", {})
        if integrity.get("hmac"):
            hmac_salt_b = base64.b64decode(integrity["hmac_salt"])
            hmac_kdf = PBKDF2HMAC(
                algorithm=hashes.SHA256(),
                length=SHARING_HMAC_KEY_LENGTH,
                salt=hmac_salt_b,
                iterations=SHARING_PBKDF2_ITERATIONS,
                backend=default_backend()
            )
            hmac_key = hmac_kdf.derive(password.encode('utf-8'))
            self._verify_hmac(hmac_key, integrity["hmac"], ciphertext, nonce, salt)
            hmac_key = None

        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=key_length,
            salt=salt,
            iterations=iterations,
            backend=default_backend()
        )
        key = kdf.derive(password.encode('utf-8'))

        try:
            aesgcm = AESGCM(key)
            plaintext = aesgcm.decrypt(nonce, ciphertext, None)
        except Exception:
            raise ValueError("Неверный пароль или повреждённые данные")
        finally:
            key = None

        return json.loads(plaintext.decode('utf-8'))

    def _encrypt_rsa_hybrid(self, plaintext: bytes,
                             recipient_pub_key,
                             share_package: Dict[str, Any],
                             sender_public_key_pem: bytes = None) -> Dict[str, Any]:

        ephemeral_aes_key = os.urandom(32)
        nonce = os.urandom(SHARING_NONCE_LENGTH)

        aesgcm = AESGCM(ephemeral_aes_key)
        ciphertext = aesgcm.encrypt(nonce, plaintext, None)

        encrypted_key = recipient_pub_key.encrypt(
            ephemeral_aes_key,
            asym_padding.OAEP(
                mgf=asym_padding.MGF1(algorithm=hashes.SHA256()),
                algorithm=hashes.SHA256(),
                label=None
            )
        )
        ephemeral_aes_key = None

        hmac_key = self._derive_hmac_key(encrypted_key, b"rsa-hybrid")
        package_hmac = self._compute_hmac(hmac_key, ciphertext, nonce, encrypted_key)
        hmac_key = None

        package = {
            "version": "1.0",
            "share_id": share_package["share_id"],
            "share_format": "cryptosafe_share_v1",
            "encryption": {
                "method": "public_key",
                "scheme": "RSA-OAEP+AES-256-GCM",
                "algorithm": "AES-256-GCM",
                "key_exchange": "RSA-OAEP",
                "key_purpose": "sharing",
                "key_separation": True,
                "nonce": base64.b64encode(nonce).decode('ascii'),
                "encrypted_key": base64.b64encode(encrypted_key).decode('ascii'),
            },
            "data": base64.b64encode(ciphertext).decode('ascii'),
            "integrity": {
                "hmac": package_hmac,
                "hmac_algorithm": "HMAC-SHA256",
                "tamper_evident": True
            }
        }

        if sender_public_key_pem:
            package["sender_public_key"] = (
                sender_public_key_pem.decode('utf-8')
                if isinstance(sender_public_key_pem, bytes)
                else sender_public_key_pem
            )

        return package

    def _encrypt_ecies(self, plaintext: bytes,
                       recipient_pub_key,
                       share_package: Dict[str, Any],
                       sender_private_key_pem: bytes = None) -> Dict[str, Any]:

        ephemeral_private = ec.generate_private_key(
            ec.SECP256R1(),
            backend=default_backend()
        )
        ephemeral_public = ephemeral_private.public_key()

        shared_secret = ephemeral_private.exchange(ec.ECDH(), recipient_pub_key)

        aes_key = HKDF(
            algorithm=hashes.SHA256(),
            length=32,
            salt=None,
            info=b"cryptosafe-ecies-sharing-v1",
            backend=default_backend()
        ).derive(shared_secret)
        shared_secret = None

        nonce = os.urandom(SHARING_NONCE_LENGTH)
        aesgcm = AESGCM(aes_key)
        ciphertext = aesgcm.encrypt(nonce, plaintext, None)
        aes_key = None

        ephemeral_pub_pem = ephemeral_public.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo
        ).decode('utf-8')
        ephemeral_private = None

        hmac_key = self._derive_hmac_key(ephemeral_pub_pem.encode('utf-8'), b"ecies")
        package_hmac = self._compute_hmac(
            hmac_key, ciphertext, nonce, ephemeral_pub_pem.encode('utf-8')
        )
        hmac_key = None

        package = {
            "version": "1.0",
            "share_id": share_package["share_id"],
            "share_format": "cryptosafe_share_v1",
            "encryption": {
                "method": "public_key",
                "scheme": "ECIES-P256+AES-256-GCM",  # CRY-2
                "algorithm": "AES-256-GCM",
                "key_exchange": "ECDH-P256",
                "key_derivation": "HKDF-SHA256",
                "key_purpose": "sharing",
                "key_separation": True,
                "nonce": base64.b64encode(nonce).decode('ascii'),
                "ephemeral_public_key": ephemeral_pub_pem,
            },
            "data": base64.b64encode(ciphertext).decode('ascii'),

            "integrity": {
                "hmac": package_hmac,
                "hmac_algorithm": "HMAC-SHA256",
                "tamper_evident": True
            }
        }

        if sender_private_key_pem:
            sender_priv = serialization.load_pem_private_key(
                sender_private_key_pem if isinstance(sender_private_key_pem, bytes)
                else sender_private_key_pem.encode(),
                password=None,
                backend=default_backend()
            )
            sender_pub_pem = sender_priv.public_key().public_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PublicFormat.SubjectPublicKeyInfo
            ).decode('utf-8')
            package["sender_public_key"] = sender_pub_pem

        return package

    def _decrypt_public_key_share(self, encrypted_package: Dict[str, Any],
                                   private_key_pem: bytes) -> Dict[str, Any]:

        enc_info = encrypted_package.get("encryption", {})
        scheme = enc_info.get("scheme", "")
        nonce = base64.b64decode(enc_info["nonce"])
        ciphertext = base64.b64decode(encrypted_package["data"])

        private_key = serialization.load_pem_private_key(
            private_key_pem if isinstance(private_key_pem, bytes)
            else private_key_pem.encode(),
            password=None,
            backend=default_backend()
        )

        if "RSA-OAEP" in scheme:
            encrypted_key = base64.b64decode(enc_info["encrypted_key"])
            aes_key = private_key.decrypt(
                encrypted_key,
                asym_padding.OAEP(
                    mgf=asym_padding.MGF1(algorithm=hashes.SHA256()),
                    algorithm=hashes.SHA256(),
                    label=None
                )
            )

            integrity = encrypted_package.get("integrity", {})
            if integrity.get("hmac"):
                hmac_key = self._derive_hmac_key(encrypted_key, b"rsa-hybrid")
                self._verify_hmac(hmac_key, integrity["hmac"],
                                  ciphertext, nonce, encrypted_key)
                hmac_key = None

        elif "ECIES" in scheme:
            ephemeral_pub = serialization.load_pem_public_key(
                enc_info["ephemeral_public_key"].encode(),
                backend=default_backend()
            )
            # CRY-4: Проверка HMAC ДО расшифровки
            integrity = encrypted_package.get("integrity", {})
            if integrity.get("hmac"):
                hmac_key = self._derive_hmac_key(
                    enc_info["ephemeral_public_key"].encode('utf-8'), b"ecies"
                )
                self._verify_hmac(
                    hmac_key, integrity["hmac"],
                    ciphertext, nonce, enc_info["ephemeral_public_key"].encode('utf-8')
                )
                hmac_key = None

            shared_secret = private_key.exchange(ec.ECDH(), ephemeral_pub)
            aes_key = HKDF(
                algorithm=hashes.SHA256(),
                length=32,
                salt=None,
                info=b"cryptosafe-ecies-sharing-v1",
                backend=default_backend()
            ).derive(shared_secret)
            shared_secret = None

        else:
            raise ValueError(f"CRY-2: Неизвестная схема шифрования: {scheme}")

        try:
            aesgcm = AESGCM(aes_key)
            plaintext = aesgcm.decrypt(nonce, ciphertext, None)
        except Exception:
            raise ValueError("Неверный ключ или повреждённые данные")
        finally:
            aes_key = None

        return json.loads(plaintext.decode('utf-8'))

    def _compute_hmac(self, hmac_key: bytes, *parts: bytes) -> str:

        h = hmac_stdlib.new(hmac_key, digestmod=hashlib.sha256)
        for part in parts:
            h.update(len(part).to_bytes(4, 'big'))
            h.update(part)
        return h.hexdigest()

    def _verify_hmac(self, hmac_key: bytes, expected: str, *parts: bytes) -> None:

        actual = self._compute_hmac(hmac_key, *parts)
        if not hmac_stdlib.compare_digest(actual, expected):
            raise ValueError("CRY-4: Integrity check failed — package may be tampered")

    def _derive_hmac_key(self, base_key: bytes, context: bytes = b"hmac") -> bytes:
        return HKDF(
            algorithm=hashes.SHA256(),
            length=SHARING_HMAC_KEY_LENGTH,
            salt=None,
            info=b"cryptosafe-sharing-hmac-v1-" + context,
            backend=default_backend()
        ).derive(base_key)

    def _generate_share_password(self, length: int = 16) -> str:
        import secrets
        import string

        alphabet = string.ascii_letters + string.digits
        return ''.join(secrets.choice(alphabet) for _ in range(length))

    def _generate_access_token(self) -> str:
        import secrets
        return secrets.token_urlsafe(32)

    def _create_share_link(self, share_id: str, access_token: str) -> str:
        return f"cryptosafe://share/{share_id}/{access_token}"

    def share_entry(
        self,
        entry_id: str,
        sharer: str,
        recipient_id: Optional[str] = None,
        method: str = SharingMethod.PASSWORD,
        expires_in_days: int = 7,
        permissions: Optional[Dict[str, Any]] = None,
        delivery_channel: str = "file"
    ) -> Dict[str, Any]:
        if self.key_manager.get_cached_key() is None:
            raise ValueError("User must be authenticated to share entries")

        logger.info(f"SHR-3 Step 1: Starting share workflow for entry {entry_id}")

        entry = self._get_entry(entry_id)
        if not entry:
            raise ValueError(f"Entry not found: {entry_id}")

        logger.info(f"SHR-3 Step 1: Entry selected - '{entry.get('title')}'")

        recipient_info = None
        recipient_public_key = None

        if recipient_id:
            recipient_info = self._get_recipient_info(recipient_id)
            if recipient_info:
                recipient_public_key = recipient_info.get("public_key")
                logger.info(f"SHR-3 Step 2: Recipient selected - {recipient_info.get('name')}")

        if method not in [SharingMethod.PASSWORD, SharingMethod.PUBLIC_KEY, SharingMethod.TIME_LIMITED]:
            raise ValueError(f"Unknown sharing method: {method}")

        if method == SharingMethod.PUBLIC_KEY and not recipient_public_key:
            raise ValueError("Public key method requires recipient with public key")

        logger.info(f"SHR-3 Step 2: Encryption method selected - {method}")

        is_valid, error = self.validate_expiration(expires_in_days)
        if not is_valid:
            raise ValueError(error)

        expires_at = datetime.utcnow() + timedelta(days=expires_in_days)
        logger.info(f"SHR-3 Step 3: Expiration set to {expires_at}")

        if permissions is None:
            permissions = {
                "access_type": Permission.READ_ONLY,
                "read": True,
                "edit": False,
                "read_password": True,
                "read_notes": True,
                "read_totp": False,
                "share": False
            }

        share_id = str(uuid.uuid4())

        share_package = self._create_share_package(
            entry=entry,
            share_id=share_id,
            sharer=sharer,
            permissions=permissions,
            expires_at=expires_at
        )

        if method == SharingMethod.PASSWORD:
            encrypted_package = self._encrypt_share_package(share_package, method)
        elif method == SharingMethod.PUBLIC_KEY:
            encrypted_package = self._encrypt_share_package(
                share_package, method, public_key=recipient_public_key
            )
        else:
            encrypted_package = self._encrypt_share_package(share_package, method)
            access_token = self._generate_access_token()
            encrypted_package["share_link"] = self._create_share_link(share_id, access_token)
            encrypted_package["access_token"] = access_token

        logger.info(f"SHR-3 Step 4: Share package generated - {share_id}")

        self._save_share_metadata(
            share_id=share_id,
            original_entry_id=entry_id,
            sharer=sharer,
            recipient_id=recipient_id,
            permissions=permissions,
            method=method,
            expires_at=expires_at
        )

        delivery_info = self._deliver_share_package(
            encrypted_package,
            method,
            recipient_info,
            delivery_channel
        )

        logger.info(f"SHR-3 Step 5: Share delivered via {delivery_channel}")

        self._log_share_event(entry_id, recipient_id, share_id, method, permissions)

        result = {
            "share_id": share_id,
            "package": encrypted_package,
            "expires_at": expires_at.isoformat() + "Z",
            "permissions": permissions,
            "method": method,
            "sharer": sharer,
            "delivery": delivery_info,
            "workflow_steps_completed": [
                "select_entry",
                "select_recipient",
                "choose_encryption",
                "set_expiration",
                "generate_package",
                "deliver"
            ]
        }

        if method == SharingMethod.TIME_LIMITED:
            result["share_link"] = encrypted_package.get("share_link")

        if method == SharingMethod.PASSWORD and "share_password" in encrypted_package:
            result["share_password"] = encrypted_package["share_password"]

        return result


    def receive_share(self, share_file_path: str = None,
                      share_link: str = None,
                      share_data: Dict[str, Any] = None) -> Dict[str, Any]:

        if share_file_path:
            with open(share_file_path, 'r', encoding='utf-8') as f:
                share_data = json.load(f)
            logger.info(f"SHR-4: Share loaded from file: {share_file_path}")

        elif share_link:
            import re
            match = re.match(r'cryptosafe://share/([^/]+)/(.+)', share_link)
            if match:
                share_id = match.group(1)
                access_token = match.group(2)

                share_data = self._get_share_metadata(share_id)
                if share_data:
                    share_data["access_token"] = access_token
                logger.info(f"SHR-4: Share loaded from link: {share_id}")
            else:
                raise ValueError(f"Invalid share link format: {share_link}")

        elif not share_data:
            raise ValueError("Either share_file_path, share_link, or share_data must be provided")

        received_share = {
            "share_data": share_data,
            "received_at": datetime.utcnow().isoformat() + "Z",
            "share_id": share_data.get("share_id"),
            "share_format": share_data.get("share_format")
        }

        logger.info(f"SHR-4 Step 1: Share received - {received_share['share_id']}")

        return received_share

    def decrypt_share(self, received_share: Dict[str, Any],
                      password: str = None,
                      private_key: bytes = None) -> Dict[str, Any]:

        logger.info(f"SHR-4 Step 2: Decrypting share")

        share_data = received_share["share_data"]

        encryption_info = share_data.get("encryption", {})
        method = encryption_info.get("method")

        if not method:
            if share_data.get("share_password"):
                method = SharingMethod.PASSWORD
            elif share_data.get("share_link"):
                method = SharingMethod.TIME_LIMITED
            else:
                method = SharingMethod.PUBLIC_KEY

        if method == SharingMethod.PASSWORD:
            if not password:
                password = share_data.get("share_password")
                if not password:
                    raise ValueError("Password required for decryption")
            decryption_service = ExportDecryptionService(password=password)

        elif method == SharingMethod.PUBLIC_KEY:
            if not private_key:
                raise ValueError("Private key required for decryption")
            decryption_service = ExportDecryptionService(private_key=private_key)

        elif method == SharingMethod.TIME_LIMITED:
            access_token = share_data.get("access_token")
            if not access_token:
                access_token = password
            if not access_token:
                raise ValueError("Access token required for time-limited share")
            decryption_service = ExportDecryptionService(password=access_token)

        else:
            raise ValueError(f"Unknown encryption method: {method}")

        try:
            decrypted_data = decryption_service.decrypt(share_data)

            if isinstance(decrypted_data, str):
                decrypted_data = json.loads(decrypted_data)

            if decrypted_data.get("share_format") != "cryptosafe_share_v1":
                raise ValueError("Invalid share format")

            expires_at = decrypted_data.get("expires_at")
            if expires_at:
                expires_datetime = datetime.fromisoformat(expires_at.replace('Z', '+00:00'))
                if expires_datetime < datetime.utcnow():
                    raise ValueError(f"Share has expired on {expires_at}")

            entry = decrypted_data.get("entry", {})
            permissions = decrypted_data.get("permissions", {})
            sharer = decrypted_data.get("sharer")
            share_id = decrypted_data.get("share_id")
            access_type = permissions.get("access_type", Permission.READ_ONLY)

            entry["_shared"] = True
            entry["_shared_from"] = sharer
            entry["_share_id"] = share_id
            entry["_access_type"] = access_type
            entry["_permissions"] = permissions
            entry["_imported_at"] = datetime.utcnow().isoformat() + "Z"

            result = {
                "entry": entry,
                "share_id": share_id,
                "sharer": sharer,
                "permissions": permissions,
                "access_type": access_type,
                "expires_at": expires_at,
                "decrypted_at": datetime.utcnow().isoformat() + "Z",
                "decryption_method": method
            }

            logger.info(f"SHR-4 Step 2: Share decrypted successfully - {share_id}")

            return result

        except Exception as e:
            logger.error(f"Failed to decrypt share: {e}")
            raise
        finally:
            decryption_service = None

    def review_share(self, decrypted_share: Dict[str, Any]) -> Dict[str, Any]:

        logger.info(f"SHR-4 Step 3: Reviewing share")

        entry = decrypted_share.get("entry", {})
        permissions = decrypted_share.get("permissions", {})
        sharer = decrypted_share.get("sharer")
        expires_at = decrypted_share.get("expires_at")

        # Очищаем мета-поля для отображения
        clean_entry = {}
        for key, value in entry.items():
            if not key.startswith('_'):
                clean_entry[key] = value

        review_data = {
            "share_id": decrypted_share.get("share_id"),
            "sharer": sharer,
            "expires_at": expires_at,
            "is_expired": expires_at and datetime.fromisoformat(expires_at.replace('Z', '+00:00')) < datetime.utcnow(),
            "permissions": {
                "can_read": permissions.get("can_read", True),
                "can_edit": permissions.get("can_edit", False),
                "can_read_password": permissions.get("can_read_password", True),
                "can_read_notes": permissions.get("can_read_notes", True),
                "can_read_totp": permissions.get("can_read_totp", False),
                "access_type": permissions.get("access_type", Permission.READ_ONLY)
            },
            "entry": clean_entry,
            "has_password": bool(clean_entry.get("password")),
            "has_notes": bool(clean_entry.get("notes")),
            "has_totp": bool(clean_entry.get("totp_secret")),
            "reviewed_at": datetime.utcnow().isoformat() + "Z"
        }

        logger.info(f"SHR-4 Step 3: Share reviewed - {review_data['share_id']}")

        return review_data

    def save_share_to_vault(self, decrypted_share: Dict[str, Any],
                            custom_title: str = None) -> Dict[str, Any]:

        logger.info(f"SHR-4 Step 4: Saving share to vault")

        if not self.entry_manager:
            raise ValueError("Entry manager not available")

        entry = decrypted_share.get("entry", {}).copy()

        for key in list(entry.keys()):
            if key.startswith('_'):
                del entry[key]

        if custom_title:
            entry["title"] = custom_title
        else:
            entry["title"] = f"{entry.get('title', 'Shared entry')} (from {decrypted_share.get('sharer')})"

        entry["source"] = "shared"
        entry["shared_from"] = decrypted_share.get("sharer")
        entry["original_share_id"] = decrypted_share.get("share_id")
        entry["imported_at"] = datetime.utcnow().isoformat()

        entry_id = self.entry_manager.create_entry(entry)

        result = {
            "saved": True,
            "entry_id": entry_id,
            "title": entry.get("title"),
            "saved_at": datetime.utcnow().isoformat() + "Z",
            "share_id": decrypted_share.get("share_id")
        }

        if self.audit_logger:
            self.audit_logger.log_event(
                event_type='share_imported_to_vault',
                severity='INFO',
                source='sharing_service',
                details={
                    'share_id': decrypted_share.get("share_id"),
                    'entry_id': entry_id,
                    'sharer': decrypted_share.get("sharer"),
                }
            )

        logger.info(f"SHR-4 Step 4: Share saved to vault - {entry_id}")

        return result

    def use_temporarily(self, decrypted_share: Dict[str, Any]) -> Dict[str, Any]:

        logger.info(f"SHR-4 Step 4: Using share temporarily")

        entry = decrypted_share.get("entry", {}).copy()
        share_id = decrypted_share.get("share_id")

        temp_id = f"temp_{share_id}_{datetime.utcnow().timestamp()}"

        clean_entry = {}
        for key, value in entry.items():
            if not key.startswith('_'):
                clean_entry[key] = value

        self._temporary_entries[temp_id] = {
            "entry": clean_entry,
            "share_id": share_id,
            "sharer": decrypted_share.get("sharer"),
            "expires_at": decrypted_share.get("expires_at"),
            "created_at": datetime.utcnow().isoformat() + "Z",
            "permissions": decrypted_share.get("permissions", {})
        }

        result = {
            "temporary": True,
            "temp_id": temp_id,
            "entry": clean_entry,
            "share_id": share_id,
            "expires_at": decrypted_share.get("expires_at"),
            "note": "Запись не сохранена в хранилище и будет доступна только в этой сессии",
            "will_expire_in_session": True
        }

        logger.info(f"Temporary entry created - {temp_id}")

        return result

    def get_temporary_entry(self, temp_id: str) -> Optional[Dict[str, Any]]:
        return self._temporary_entries.get(temp_id)

    def clear_temporary_entries(self) -> None:
        count = len(self._temporary_entries)
        self._temporary_entries.clear()
        logger.info(f"SHR-4: Cleared {count} temporary entries")

    def import_shared_entry(
        self,
        share_file_path: str = None,
        share_link: str = None,
        share_data: Dict[str, Any] = None,
        password: str = None,
        private_key: bytes = None,
        save_to_vault: bool = True,
        custom_title: str = None
    ) -> Dict[str, Any]:

        workflow_steps = []

        try:
            received = self.receive_share(share_file_path, share_link, share_data)
            workflow_steps.append({"step": "receive", "status": "completed"})
        except Exception as e:
            workflow_steps.append({"step": "receive", "status": "failed", "error": str(e)})
            raise

        # Шаг 2: Расшифровка
        try:
            decrypted = self.decrypt_share(received, password, private_key)
            workflow_steps.append({"step": "decrypt", "status": "completed"})
        except Exception as e:
            workflow_steps.append({"step": "decrypt", "status": "failed", "error": str(e)})
            raise

        try:
            review = self.review_share(decrypted)
            workflow_steps.append({"step": "review", "status": "completed"})
        except Exception as e:
            workflow_steps.append({"step": "review", "status": "failed", "error": str(e)})
            raise

        try:
            if save_to_vault:
                result = self.save_share_to_vault(decrypted, custom_title)
                workflow_steps.append({"step": "save_to_vault", "status": "completed"})
            else:
                result = self.use_temporarily(decrypted)
                workflow_steps.append({"step": "use_temporarily", "status": "completed"})
        except Exception as e:
            workflow_steps.append({"step": "finalize", "status": "failed", "error": str(e)})
            raise

        result["workflow_steps"] = workflow_steps
        result["review_data"] = review

        logger.info(f"SHR-4: Full import workflow completed, saved={save_to_vault}")

        return result

    def _get_recipient_info(self, recipient_id: str) -> Optional[Dict[str, Any]]:
        cursor = self.db.execute(
            """
            SELECT contact_id, name, email, public_key, public_key_fingerprint
            FROM contacts
            WHERE contact_id = ?
            """,
            (recipient_id,)
        )
        row = cursor.fetchone()

        if not row:
            return None

        return {
            "id": row[0],
            "name": row[1],
            "email": row[2],
            "public_key": row[3],
            "public_key_fingerprint": row[4]
        }

    def _get_share_metadata(self, share_id: str) -> Optional[Dict[str, Any]]:
        cursor = self.db.execute(
            """
            SELECT share_id, original_entry_id, sharer, recipient, encryption_method,
                   permissions, access_type, shared_at, expires_at
            FROM shared_entries
            WHERE share_id = ?
            """,
            (share_id,)
        )
        row = cursor.fetchone()

        if not row:
            return None

        return {
            "share_id": row[0],
            "original_entry_id": row[1],
            "sharer": row[2],
            "recipient": row[3],
            "encryption_method": row[4],
            "permissions": json.loads(row[5]) if row[5] else {},
            "access_type": row[6],
            "shared_at": row[7],
            "expires_at": row[8]
        }

    def _get_entry(self, entry_id: str) -> Optional[Dict[str, Any]]:
        if self.entry_manager:
            try:
                return self.entry_manager.get_entry(entry_id)
            except Exception as e:
                logger.error(f"Failed to get entry {entry_id}: {e}")
                return None
        return None

    def _save_share_metadata(self, share_id: str, original_entry_id: str,
                             sharer: str, recipient_id: Optional[str],
                             permissions: Dict[str, Any],
                             method: str, expires_at: datetime) -> None:
        try:
            self.db.execute(
                """
                INSERT INTO shared_entries 
                (share_id, original_entry_id, sharer, recipient, encryption_method,
                 permissions, access_type, shared_at, expires_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    share_id,
                    original_entry_id,
                    sharer,
                    recipient_id,
                    method,
                    json.dumps(permissions),
                    permissions.get("access_type", Permission.READ_ONLY),
                    datetime.utcnow(),
                    expires_at
                )
            )
            if hasattr(self.db, 'commit'):
                self.db.commit()
        except Exception as e:
            logger.error(f"Failed to save share metadata: {e}")

    def _deliver_share_package(self, package: Dict[str, Any],
                                method: str,
                                recipient_info: Optional[Dict[str, Any]],
                                delivery_channel: str) -> Dict[str, Any]:
        delivery_info = {
            "channel": delivery_channel,
            "method": method,
            "delivered_at": datetime.utcnow().isoformat() + "Z"
        }

        if delivery_channel == "file":
            delivery_info["file_format"] = "cryptosafe_share"
            delivery_info["file_extension"] = ".cryptoshare"
            delivery_info["instruction"] = "Файл защищён шифрованием. Передайте получателю по защищённому каналу."

            if method == SharingMethod.PASSWORD and "share_password" in package:
                delivery_info["password_delivery_warning"] = "Пароль необходимо передать отдельным каналом (SMS/звонок/другой мессенджер)"

        elif delivery_channel == "link" and method == SharingMethod.TIME_LIMITED:
            delivery_info["link"] = package.get("share_link")
            delivery_info["instruction"] = "Отправьте ссылку получателю. Ссылка будет активна до истечения срока."

        elif delivery_channel == "qr":
            import qrcode
            import io

            data_to_encode = json.dumps({
                "share_id": package.get("share_id"),
                "type": "cryptosafe_share",
                "method": method
            })

            qr = qrcode.QRCode(box_size=10, border=4)
            qr.add_data(data_to_encode)
            qr.make(fit=True)

            img = qr.make_image(fill_color="black", back_color="white")

            buffer = io.BytesIO()
            img.save(buffer, format="PNG")
            qr_base64 = base64.b64encode(buffer.getvalue()).decode('utf-8')

            delivery_info["qr_code"] = f"data:image/png;base64,{qr_base64}"
            delivery_info["instruction"] = "Получатель может отсканировать QR код для получения доступа."

        return delivery_info

    def _log_share_event(self, entry_id: str, recipient_id: Optional[str],
                         share_id: str, method: str, permissions: Dict[str, Any]) -> None:
        if self.audit_logger:
            self.audit_logger.log_event(
                event_type='entry_shared',
                severity='INFO',
                source='sharing_service',
                details={
                    'entry_id': entry_id,
                    'recipient_id': recipient_id,
                    'share_id': share_id,
                    'method': method,
                    'access_type': permissions.get("access_type", Permission.READ_ONLY),
                }
            )
        else:
            logger.info(f"AUDIT: Entry {entry_id} shared via {method}")

    def revoke_share(self, share_id: str) -> bool:
        self.db.execute(
            """
            UPDATE shared_entries
            SET expires_at = ?, revoked_at = ?, is_revoked = 1
            WHERE share_id = ?
            """,
            (datetime.utcnow(), datetime.utcnow(), share_id)
        )

        if hasattr(self.db, 'commit'):
            self.db.commit()

        logger.info(f"SHR-3: Share {share_id} revoked")

        if self.audit_logger:
            self.audit_logger.log_event(
                event_type='share_revoked',
                severity='INFO',
                source='sharing_service',
                details={'share_id': share_id}
            )

        return True

    def get_share_workflow_status(self, share_id: str) -> Dict[str, Any]:
        cursor = self.db.execute(
            """
            SELECT share_id, original_entry_id, sharer, recipient, encryption_method,
                   permissions, access_type, shared_at, expires_at
            FROM shared_entries
            WHERE share_id = ?
            """,
            (share_id,)
        )
        row = cursor.fetchone()

        if not row:
            raise ValueError(f"Share not found: {share_id}")

        return {
            "share_id": row[0],
            "entry_id": row[1],
            "sharer": row[2],
            "recipient": row[3],
            "method": row[4],
            "permissions": json.loads(row[5]) if row[5] else {},
            "access_type": row[6],
            "shared_at": row[7],
            "expires_at": row[8],
            "is_expired": datetime.utcnow() > datetime.fromisoformat(row[8].replace('Z', '+00:00')),
            "workflow_completed": True
        }