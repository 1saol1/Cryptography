from typing import List, Optional, Dict, Any, Tuple, Callable
import json
import base64
import hashlib
import zlib
import logging
from datetime import datetime
from enum import Enum
import time
import secrets
import qrcode
import io
import uuid
import threading

from cryptography.hazmat.primitives.asymmetric import rsa, ec, padding
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.backends import default_backend
from cryptography.exceptions import InvalidSignature

logger = logging.getLogger(__name__)

QR_MAX_PAYLOAD_VERSION_40_L = 2953
QR_CHUNK_HEADER_SIZE = 64


class QRPayloadType(Enum):
    PUBLIC_KEY = "public_key"
    ENCRYPTED_ENTRY = "encrypted_entry"
    SHARE_LINK = "share_link"
    CONTACT_INFO = "contact_info"


class QRErrorCorrection(Enum):
    L = 1
    M = 0
    Q = 3
    H = 2


class QRScanResult(Enum):
    SUCCESS = "success"
    INVALID_FORMAT = "invalid_format"
    CHECKSUM_FAILED = "checksum_failed"
    INCOMPLETE = "incomplete"
    TIMEOUT = "timeout"
    CANCELLED = "cancelled"
    NO_QR_FOUND = "no_qr_found"
    EXPIRED = "expired"
    REPLAY_ATTACK = "replay_attack"


class QRCodeService:
    def __init__(self, error_correction: QRErrorCorrection = QRErrorCorrection.M,
                 qr_validity_seconds: int = 300):
        self.error_correction = error_correction
        self._qr_sessions = {}
        self._scan_callbacks = {}
        self._is_scanning = False
        self._qr_validity_seconds = qr_validity_seconds
        self._used_nonces: set = set()

    def generate_qr_code(self, data: bytes,
                         payload_type: QRPayloadType = QRPayloadType.SHARE_LINK,
                         chunk_size: int = QR_MAX_PAYLOAD_VERSION_40_L,
                         include_checksum: bool = True) -> List[str]:
        payload = self._create_payload(data, payload_type, include_checksum)
        compressed = zlib.compress(payload)
        logger.debug(f"Original size: {len(payload)} bytes, compressed: {len(compressed)} bytes")

        chunks = self._split_into_chunks(compressed, chunk_size)

        qr_codes = []
        for i, chunk in enumerate(chunks):
            chunk_data = self._create_chunk_payload(chunk, i + 1, len(chunks))
            qr_code = self._encode_to_qr(chunk_data)
            qr_codes.append(qr_code)

            logger.debug(f"Generated QR code {i+1}/{len(chunks)}")

        return qr_codes

    def _create_payload(self, data: bytes, payload_type: QRPayloadType,
                        include_checksum: bool) -> bytes:
        now = datetime.utcnow()
        nonce = secrets.token_hex(16)
        expires_at = (
            datetime.utcfromtimestamp(now.timestamp() + self._qr_validity_seconds).isoformat() + "Z"
        )
        payload_dict = {
            "version": "1.0",
            "type": payload_type.value,
            "timestamp": now.isoformat() + "Z",
            "expires_at": expires_at,
            "nonce": nonce,
            "data": base64.b64encode(data).decode('ascii')
        }

        if include_checksum:
            checksum = hashlib.sha256(data).hexdigest()[:16]
            payload_dict["checksum"] = checksum

        return json.dumps(payload_dict, sort_keys=True).encode('utf-8')

    def _split_into_chunks(self, data: bytes, chunk_size: int) -> List[bytes]:
        chunks = []
        for i in range(0, len(data), chunk_size):
            chunk = data[i:i + chunk_size]
            chunks.append(chunk)
        return chunks

    def _create_chunk_payload(self, chunk: bytes, chunk_num: int, total_chunks: int) -> bytes:
        chunk_payload = {
            "chunk": chunk_num,
            "total": total_chunks,
            "data": base64.b64encode(chunk).decode('ascii')
        }
        return json.dumps(chunk_payload).encode('utf-8')

    def _encode_to_qr(self, data: bytes) -> str:

        error_correction_map = {
            QRErrorCorrection.L: qrcode.constants.ERROR_CORRECT_L,
            QRErrorCorrection.M: qrcode.constants.ERROR_CORRECT_M,
            QRErrorCorrection.Q: qrcode.constants.ERROR_CORRECT_Q,
            QRErrorCorrection.H: qrcode.constants.ERROR_CORRECT_H,
        }

        qr = qrcode.QRCode(
            version=None,
            error_correction=error_correction_map[self.error_correction],
            box_size=10,
            border=4,
        )

        qr.add_data(data)
        qr.make(fit=True)

        img = qr.make_image(fill_color="black", back_color="white")
        buffer = io.BytesIO()
        img.save(buffer, format="PNG")
        png_bytes = buffer.getvalue()
        import base64 as _b64
        return "data:image/png;base64," + _b64.b64encode(png_bytes).decode('ascii')

    def scan_from_camera(self, callback: Callable, timeout_seconds: int = 60) -> str:

        import uuid
        import threading

        session_id = str(uuid.uuid4())

        self._scan_callbacks[session_id] = {
            "callback": callback,
            "timeout": timeout_seconds,
            "start_time": time.time(),
            "status": "scanning"
        }

        self._is_scanning = True

        timer = threading.Timer(timeout_seconds, self._scan_timeout, args=[session_id])
        timer.daemon = True
        timer.start()

        logger.info(f"QR-2: Started camera scan session {session_id}")

        return session_id

    def _scan_timeout(self, session_id: str) -> None:
        if session_id in self._scan_callbacks:
            callback_info = self._scan_callbacks[session_id]
            if callback_info["status"] == "scanning":
                callback_info["status"] = "timeout"
                callback_info["callback"]({
                    "result": QRScanResult.TIMEOUT,
                    "data": None,
                    "message": "Scan timeout exceeded"
                })
                del self._scan_callbacks[session_id]

        self._is_scanning = False
        logger.info(f"QR-2: Scan session {session_id} timed out")

    def process_camera_frame(self, session_id: str, frame_data: bytes) -> Optional[Dict[str, Any]]:

        if session_id not in self._scan_callbacks:
            return None

        callback_info = self._scan_callbacks[session_id]
        if callback_info["status"] != "scanning":
            return None

        result = self.scan_from_image(frame_data)

        if result and result.get("result") == QRScanResult.SUCCESS:
            callback_info["status"] = "completed"
            callback_info["callback"](result)
            del self._scan_callbacks[session_id]
            self._is_scanning = False
            return result

        return None

    def stop_camera_scan(self, session_id: str) -> bool:
        if session_id in self._scan_callbacks:
            callback_info = self._scan_callbacks[session_id]
            if callback_info["status"] == "scanning":
                callback_info["status"] = "cancelled"
                callback_info["callback"]({
                    "result": QRScanResult.CANCELLED,
                    "data": None,
                    "message": "Scan cancelled by user"
                })
            del self._scan_callbacks[session_id]
            self._is_scanning = False
            logger.info(f"QR-2: Camera scan session {session_id} stopped")
            return True
        return False

    def scan_from_file(self, file_path: str) -> Dict[str, Any]:

        try:
            with open(file_path, 'rb') as f:
                image_data = f.read()

            return self.scan_from_image(image_data)

        except FileNotFoundError:
            return {
                "result": QRScanResult.INVALID_FORMAT,
                "data": None,
                "message": f"File not found: {file_path}"
            }
        except Exception as e:
            return {
                "result": QRScanResult.INVALID_FORMAT,
                "data": None,
                "message": f"Failed to read file: {e}"
            }

    def scan_from_image(self, image_data: bytes) -> Dict[str, Any]:

        try:
            from PIL import Image
            import io
            import qrcode

            image = Image.open(io.BytesIO(image_data))

            decoded = qrcode.decode(image)

            if not decoded or not decoded.data:
                return {
                    "result": QRScanResult.NO_QR_FOUND,
                    "data": None,
                    "message": "No QR code found in image"
                }

            return self._validate_and_parse(decoded.data)

        except ImportError:
            logger.error("PIL or qrcode not available for scanning")
            return {
                "result": QRScanResult.INVALID_FORMAT,
                "data": None,
                "message": "QR scanning libraries not available"
            }
        except Exception as e:
            logger.error(f"Failed to scan QR code: {e}")
            return {
                "result": QRScanResult.INVALID_FORMAT,
                "data": None,
                "message": f"Failed to scan QR code: {e}"
            }

    def _validate_and_parse(self, qr_data: str) -> Dict[str, Any]:

        if qr_data.strip().startswith('{'):
            try:
                data = json.loads(qr_data)

                expires_at_str = data.get("expires_at")
                if expires_at_str:
                    try:
                        expires_at = datetime.fromisoformat(expires_at_str.rstrip("Z"))
                        if datetime.utcnow() > expires_at:
                            logger.warning("QR-4: QR код просрочен")
                            return {
                                "result": QRScanResult.EXPIRED,
                                "data": None,
                                "message": f"QR code expired at {expires_at_str}"
                            }
                    except ValueError:
                        logger.warning("QR-4: Некорректный формат expires_at")

                # QR-4: Проверка nonce (защита от replay-атак)
                nonce = data.get("nonce")
                if nonce:
                    if nonce in self._used_nonces:
                        logger.warning(f"QR-4: Replay attack detected, nonce={nonce[:8]}...")
                        return {
                            "result": QRScanResult.REPLAY_ATTACK,
                            "data": None,
                            "message": "Replay attack detected: QR code already used"
                        }
                    self._used_nonces.add(nonce)

                if "checksum" in data:
                    data_bytes = base64.b64decode(data["data"])
                    expected_checksum = hashlib.sha256(data_bytes).hexdigest()[:16]

                    if data["checksum"] != expected_checksum:
                        logger.warning("QR-2: Checksum validation failed")
                        return {
                            "result": QRScanResult.CHECKSUM_FAILED,
                            "data": None,
                            "message": "Checksum validation failed - data may be corrupted"
                        }

                    if "type" in data:
                        return {
                            "result": QRScanResult.SUCCESS,
                            "data": {
                                "type": data["type"],
                                "payload": base64.b64decode(data["data"]),
                                "timestamp": data.get("timestamp"),
                                "expires_at": data.get("expires_at"),
                                "version": data.get("version")
                            },
                            "message": "QR code scanned successfully"
                        }

                if "chunk" in data and "total" in data:
                    return {
                        "result": QRScanResult.SUCCESS,
                        "data": {
                            "type": "chunk",
                            "chunk_num": data["chunk"],
                            "total_chunks": data["total"],
                            "chunk_data": base64.b64decode(data["data"])
                        },
                        "message": f"Chunk {data['chunk']}/{data['total']} scanned"
                    }

                # Обычный JSON без контрольной суммы
                return {
                    "result": QRScanResult.SUCCESS,
                    "data": data,
                    "message": "QR code scanned successfully (no checksum)"
                }

            except json.JSONDecodeError:
                pass

        if qr_data.startswith("cryptosafe://"):
            return {
                "result": QRScanResult.SUCCESS,
                "data": {
                    "type": "share_link",
                    "share_link": qr_data
                },
                "message": "Share link scanned successfully"
            }

        if qr_data.startswith("-----BEGIN") and "KEY-----" in qr_data:
            return {
                "result": QRScanResult.SUCCESS,
                "data": {
                    "type": "public_key",
                    "public_key": qr_data.encode('utf-8')
                },
                "message": "Public key scanned successfully"
            }

        return {
            "result": QRScanResult.INVALID_FORMAT,
            "data": None,
            "message": "Invalid QR code format"
        }

    def process_qr_chunk(self, session_id: str, chunk_num: int,
                         total_chunks: int, chunk_data: bytes) -> Dict[str, Any]:

        if session_id not in self._qr_sessions:
            self._qr_sessions[session_id] = {
                "created_at": datetime.utcnow().isoformat(),
                "chunks": {},
                "total_chunks": total_chunks
            }

        session = self._qr_sessions[session_id]
        session["chunks"][chunk_num] = chunk_data

        logger.debug(f"Received chunk {chunk_num}/{total_chunks} for session {session_id}")

        if len(session["chunks"]) == total_chunks:

            combined = b''
            for i in range(1, total_chunks + 1):
                if i in session["chunks"]:
                    combined += session["chunks"][i]
                else:
                    return {
                        "status": "incomplete",
                        "message": f"Missing chunk {i}"
                    }

            try:
                decompressed = zlib.decompress(combined)
                result = self._validate_and_parse(decompressed.decode('utf-8'))

                del self._qr_sessions[session_id]

                return {
                    "status": "complete",
                    "result": result
                }

            except Exception as e:
                return {
                    "status": "error",
                    "message": f"Failed to reassemble chunks: {e}"
                }

        return {
            "status": "partial",
            "received": len(session["chunks"]),
            "total": total_chunks,
            "message": f"Received {len(session['chunks'])} of {total_chunks} chunks"
        }

    def decode_qr_chunks(self, chunks: List[str]) -> Optional[bytes]:
        extracted_chunks = []

        for qr_data in chunks:
            chunk_data = self._decode_qr(qr_data)
            if chunk_data is None:
                logger.error("Failed to decode QR code")
                return None
            extracted_chunks.append(chunk_data)

        extracted_chunks.sort(key=lambda x: x["chunk"])

        total_chunks = extracted_chunks[0]["total"]
        if len(extracted_chunks) != total_chunks:
            logger.error(f"Missing chunks: expected {total_chunks}, got {len(extracted_chunks)}")
            return None

        for i, chunk in enumerate(extracted_chunks):
            if chunk["chunk"] != i + 1:
                logger.error(f"Invalid chunk order: expected {i+1}, got {chunk['chunk']}")
                return None

        combined_data = b''
        for chunk in extracted_chunks:
            combined_data += base64.b64decode(chunk["data"])

        try:
            decompressed = zlib.decompress(combined_data)
        except Exception as e:
            logger.error(f"Failed to decompress data: {e}")
            return None

        try:
            payload = json.loads(decompressed.decode('utf-8'))
        except Exception as e:
            logger.error(f"Failed to parse payload: {e}")
            return None

        if "checksum" in payload:
            data_bytes = base64.b64decode(payload["data"])
            expected_checksum = hashlib.sha256(data_bytes).hexdigest()[:16]
            if payload["checksum"] != expected_checksum:
                logger.error("Checksum validation failed")
                return None

        return base64.b64decode(payload["data"])

    def _decode_qr(self, qr_data: str) -> Optional[Dict[str, Any]]:

        try:
            if qr_data.strip().startswith('{'):
                return json.loads(qr_data)
        except json.JSONDecodeError:
            pass
        return None

    def create_public_key_qr(self, public_key: bytes, user_id: str = None) -> List[str]:
        key_data = {
            "public_key": base64.b64encode(public_key).decode('ascii'),
            "algorithm": "RSA-2048",
            "user_id": user_id
        }
        return self.generate_qr_code(
            data=json.dumps(key_data).encode('utf-8'),
            payload_type=QRPayloadType.PUBLIC_KEY,
            include_checksum=True
        )

    def create_encrypted_entry_qr(self, encrypted_entry: Dict[str, Any]) -> List[str]:
        return self.generate_qr_code(
            data=json.dumps(encrypted_entry).encode('utf-8'),
            payload_type=QRPayloadType.ENCRYPTED_ENTRY,
            include_checksum=True
        )

    def create_share_link_qr(self, share_link: str) -> List[str]:
        return self.generate_qr_code(
            data=share_link.encode('utf-8'),
            payload_type=QRPayloadType.SHARE_LINK,
            include_checksum=True
        )

    def validate_qr_code(self, qr_code: str) -> Tuple[bool, str]:

        if not qr_code or len(qr_code) < 10:
            return False, "QR code is empty or too short"

        if qr_code.strip().startswith('<svg'):
            return True, "Valid SVG QR code"

        if qr_code.strip().startswith('{'):
            try:
                data = json.loads(qr_code)
                if "checksum" in data:
                    return True, "Valid QR code with checksum"
                return True, "Valid QR code JSON"
            except:
                pass

        return True, "Valid QR code"

    def estimate_qr_capacity(self, data_size: int) -> int:
        compressed_estimate = int(data_size * 0.7)
        chunks_needed = (compressed_estimate + QR_MAX_PAYLOAD_VERSION_40_L - 1) // QR_MAX_PAYLOAD_VERSION_40_L
        return max(1, chunks_needed)

    def create_qr_session(self, data: bytes, session_id: str = None) -> str:
        import uuid
        if session_id is None:
            session_id = str(uuid.uuid4())

        self._qr_sessions[session_id] = {
            "data": data,
            "created_at": datetime.utcnow().isoformat(),
            "chunks": []
        }

        return session_id

    def add_qr_chunk_to_session(self, session_id: str, chunk_num: int,
                                 total_chunks: int, chunk_data: bytes) -> bool:
        if session_id not in self._qr_sessions:
            return False

        session = self._qr_sessions[session_id]

        if "chunks" not in session:
            session["chunks"] = []

        session["chunks"].append({
            "num": chunk_num,
            "total": total_chunks,
            "data": chunk_data
        })

        if len(session["chunks"]) == total_chunks:
            session["chunks"].sort(key=lambda x: x["num"])
            return True

        return False

    def get_session_data(self, session_id: str) -> Optional[bytes]:
        if session_id not in self._qr_sessions:
            return None

        session = self._qr_sessions[session_id]

        if len(session.get("chunks", [])) != session["chunks"][0]["total"]:
            return None

        combined = b''
        for chunk in session["chunks"]:
            combined += chunk["data"]

        return combined

    def clear_session(self, session_id: str) -> None:
        if session_id in self._qr_sessions:
            del self._qr_sessions[session_id]

    def is_scanning(self) -> bool:
        return self._is_scanning

    def get_active_scan_sessions(self) -> List[str]:
        return list(self._scan_callbacks.keys())

class KeyAlgorithm(Enum):
    RSA_2048 = "RSA-2048"
    ECC_P256 = "ECC-P256"


class KeyStatus(Enum):
    ACTIVE = "active"
    REVOKED = "revoked"
    ROTATED = "rotated"


class PublicKeyExchangeService:

    def __init__(self, db_conn=None):

        self._db = db_conn
        self._private_key = None
        self._public_key = None
        self._algorithm: Optional[KeyAlgorithm] = None
        self._key_id: Optional[str] = None
        self._key_created_at: Optional[str] = None

    def generate_key_pair(self, algorithm: KeyAlgorithm = KeyAlgorithm.RSA_2048) -> Dict[str, Any]:

        import uuid

        if algorithm == KeyAlgorithm.RSA_2048:
            private_key = rsa.generate_private_key(
                public_exponent=65537,
                key_size=2048,
                backend=default_backend()
            )
        elif algorithm == KeyAlgorithm.ECC_P256:
            private_key = ec.generate_private_key(
                ec.SECP256R1(),
                backend=default_backend()
            )
        else:
            raise ValueError(f"Неподдерживаемый алгоритм: {algorithm}")

        self._private_key = private_key
        self._public_key = private_key.public_key()
        self._algorithm = algorithm
        self._key_id = str(uuid.uuid4())
        self._key_created_at = datetime.utcnow().isoformat() + "Z"

        public_key_pem = self._serialize_public_key(self._public_key)
        fingerprint = self.compute_fingerprint(public_key_pem)

        logger.info(f"Сгенерирована пара ключей {algorithm.value}, id={self._key_id}")

        return {
            "key_id": self._key_id,
            "algorithm": algorithm.value,
            "public_key_pem": public_key_pem.decode('utf-8'),
            "fingerprint": fingerprint,
            "created_at": self._key_created_at
        }

    def get_private_key_pem(self, password: Optional[bytes] = None) -> bytes:

        if self._private_key is None:
            raise ValueError("QR-3: Приватный ключ не сгенерирован")

        encryption = (
            serialization.BestAvailableEncryption(password)
            if password
            else serialization.NoEncryption()
        )

        return self._private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=encryption
        )

    def load_private_key(self, private_key_pem: bytes,
                         password: Optional[bytes] = None) -> None:
        self._private_key = serialization.load_pem_private_key(
            private_key_pem,
            password=password,
            backend=default_backend()
        )
        self._public_key = self._private_key.public_key()

        if isinstance(self._private_key, rsa.RSAPrivateKey):
            self._algorithm = KeyAlgorithm.RSA_2048
        elif isinstance(self._private_key, ec.EllipticCurvePrivateKey):
            self._algorithm = KeyAlgorithm.ECC_P256
        else:
            raise ValueError("Неподдерживаемый тип приватного ключа")

        logger.info(f"Загружен приватный ключ {self._algorithm.value}")

    def compute_fingerprint(self, public_key_pem: bytes) -> str:

        public_key = serialization.load_pem_public_key(
            public_key_pem if isinstance(public_key_pem, bytes)
            else public_key_pem.encode('utf-8'),
            backend=default_backend()
        )

        der_bytes = public_key.public_bytes(
            encoding=serialization.Encoding.DER,
            format=serialization.PublicFormat.SubjectPublicKeyInfo
        )

        digest = hashlib.sha256(der_bytes).hexdigest()
        # Форматируем как пары через двоеточие: "ab:cd:ef:..."
        return ':'.join(digest[i:i+2] for i in range(0, len(digest), 2))

    def verify_fingerprint(self, public_key_pem: bytes, expected_fingerprint: str) -> bool:

        actual = self.compute_fingerprint(public_key_pem)
        actual_norm = actual.replace(' ', '').lower()
        expected_norm = expected_fingerprint.replace(' ', '').lower()
        match = actual_norm == expected_norm

        return match

    def add_contact(self, name: str, public_key_pem: str,
                    algorithm: str = "RSA-2048",
                    verified: bool = False) -> Dict[str, Any]:

        import uuid

        fingerprint = self.compute_fingerprint(public_key_pem.encode('utf-8')
                                               if isinstance(public_key_pem, str)
                                               else public_key_pem)
        contact_id = str(uuid.uuid4())
        now = datetime.utcnow().isoformat() + "Z"

        contact = {
            "contact_id": contact_id,
            "name": name,
            "public_key_pem": public_key_pem if isinstance(public_key_pem, str)
                              else public_key_pem.decode('utf-8'),
            "algorithm": algorithm,
            "fingerprint": fingerprint,
            "status": KeyStatus.ACTIVE.value,
            "verified": verified,
            "created_at": now,
            "updated_at": now,
            "revoked_at": None,
            "rotation_successor_id": None   # ID нового ключа при ротации
        }

        if self._db:
            self._db_insert_contact(contact)
        else:

            if not hasattr(self, '_contacts_cache'):
                self._contacts_cache = {}
            self._contacts_cache[contact_id] = contact

        logger.info(f"Контакт '{name}' добавлен, fingerprint={fingerprint[:23]}...")
        return contact

    def get_contact(self, contact_id: str) -> Optional[Dict[str, Any]]:
        if self._db:
            return self._db_get_contact(contact_id)
        return getattr(self, '_contacts_cache', {}).get(contact_id)

    def get_all_contacts(self) -> List[Dict[str, Any]]:
        if self._db:
            return self._db_get_all_contacts()
        cache = getattr(self, '_contacts_cache', {})
        return [c for c in cache.values() if c["status"] == KeyStatus.ACTIVE.value]

    def find_contact_by_fingerprint(self, fingerprint: str) -> Optional[Dict[str, Any]]:
        norm = fingerprint.replace(' ', '').lower()
        contacts = self.get_all_contacts()
        for contact in contacts:
            if contact["fingerprint"].replace(' ', '').lower() == norm:
                return contact
        return None

    def mark_contact_verified(self, contact_id: str) -> bool:
        if self._db:
            return self._db_update_contact(contact_id, {"verified": True,
                                                         "updated_at": datetime.utcnow().isoformat() + "Z"})
        cache = getattr(self, '_contacts_cache', {})
        if contact_id in cache:
            cache[contact_id]["verified"] = True
            cache[contact_id]["updated_at"] = datetime.utcnow().isoformat() + "Z"
            logger.info(f"QR-3: Контакт {contact_id} помечен как верифицированный")
            return True
        return False

    def revoke_key(self, contact_id: str, reason: str = "manual_revocation") -> bool:

        now = datetime.utcnow().isoformat() + "Z"
        updates = {
            "status": KeyStatus.REVOKED.value,
            "revoked_at": now,
            "revocation_reason": reason,
            "updated_at": now
        }

        if self._db:
            result = self._db_update_contact(contact_id, updates)
        else:
            cache = getattr(self, '_contacts_cache', {})
            if contact_id not in cache:
                return False
            cache[contact_id].update(updates)
            result = True

        if result:
            logger.warning(f"Ключ контакта {contact_id} ОТОЗВАН, причина: {reason}")
        return result

    def rotate_own_key(self, algorithm: KeyAlgorithm = KeyAlgorithm.RSA_2048) -> Dict[str, Any]:

        old_key_id = self._key_id


        if self._private_key is not None:
            self._private_key = None
            self._public_key = None

        new_key_info = self.generate_key_pair(algorithm)

        logger.info(f"QR-3: Ротация ключа выполнена. "
                    f"Старый id={old_key_id}, новый id={new_key_info['key_id']}")

        return {
            **new_key_info,
            "rotation": True,
            "previous_key_id": old_key_id
        }

    def rotate_contact_key(self, contact_id: str,
                           new_public_key_pem: str,
                           new_algorithm: str = "RSA-2048") -> Optional[Dict[str, Any]]:

        old_contact = self.get_contact(contact_id)
        if not old_contact:
            logger.error(f"QR-3: Контакт {contact_id} не найден для ротации")
            return None

        new_contact = self.add_contact(
            name=old_contact["name"],
            public_key_pem=new_public_key_pem,
            algorithm=new_algorithm,
            verified=False
        )

        now = datetime.utcnow().isoformat() + "Z"
        updates = {
            "status": KeyStatus.ROTATED.value,
            "rotation_successor_id": new_contact["contact_id"],
            "updated_at": now,
            "revoked_at": now,
            "revocation_reason": "rotation"
        }

        if self._db:
            self._db_update_contact(contact_id, updates)
        else:
            cache = getattr(self, '_contacts_cache', {})
            if contact_id in cache:
                cache[contact_id].update(updates)

        logger.info(f"Ключ контакта '{old_contact['name']}' ротирован. "
                    f"Новый contact_id={new_contact['contact_id']}")

        return new_contact

    def export_own_public_key_as_qr(self, qr_service: "QRCodeService",
                                     user_id: str = None) -> List[str]:
        if self._public_key is None:
            raise ValueError("Ключевая пара не сгенерирована")

        public_key_pem = self._serialize_public_key(self._public_key)
        fingerprint = self.compute_fingerprint(public_key_pem)

        key_data = {
            "key_id": self._key_id,
            "algorithm": self._algorithm.value,
            "fingerprint": fingerprint,
            "created_at": self._key_created_at
        }

        return qr_service.create_public_key_qr(
            public_key=public_key_pem,
            user_id=user_id or self._key_id
        )

    def import_contact_from_qr_scan(self, scan_result: Dict[str, Any],
                                     contact_name: str) -> Optional[Dict[str, Any]]:

        if scan_result.get("result") != QRScanResult.SUCCESS:
            logger.error(f"Сканирование не успешно: {scan_result.get('message')}")
            return None

        data = scan_result.get("data", {})
        data_type = data.get("type")

        if data_type == QRPayloadType.PUBLIC_KEY.value:
            try:
                payload = data.get("payload")
                if isinstance(payload, bytes):
                    key_info = json.loads(payload.decode('utf-8'))
                else:
                    key_info = payload

                raw_key = base64.b64decode(key_info["public_key"])
                public_key_pem = raw_key.decode('utf-8')
                algorithm = key_info.get("algorithm", "RSA-2048")

            except Exception as e:
                logger.error(f"Ошибка разбора публичного ключа из QR: {e}")
                return None

        elif data_type == "public_key":
            raw = data.get("public_key", b"")
            public_key_pem = raw.decode('utf-8') if isinstance(raw, bytes) else raw
            algorithm = "RSA-2048"

        else:
            logger.error(f"Неожиданный тип QR данных: {data_type}")
            return None

        return self.add_contact(
            name=contact_name,
            public_key_pem=public_key_pem,
            algorithm=algorithm,
            verified=False
        )

    def _db_insert_contact(self, contact: Dict[str, Any]) -> None:
        cursor = self._db.cursor()
        cursor.execute("""
            INSERT INTO contacts (
                contact_id, name, public_key_pem, algorithm, fingerprint,
                status, verified, created_at, updated_at,
                revoked_at, revocation_reason, rotation_successor_id
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            contact["contact_id"],
            contact["name"],
            contact["public_key_pem"],
            contact["algorithm"],
            contact["fingerprint"],
            contact["status"],
            int(contact["verified"]),
            contact["created_at"],
            contact["updated_at"],
            contact.get("revoked_at"),
            contact.get("revocation_reason"),
            contact.get("rotation_successor_id")
        ))
        self._db.commit()

    def _db_get_contact(self, contact_id: str) -> Optional[Dict[str, Any]]:

        cursor = self._db.cursor()
        cursor.execute("SELECT * FROM contacts WHERE contact_id = ?", (contact_id,))
        row = cursor.fetchone()
        return self._row_to_contact(row) if row else None

    def _db_get_all_contacts(self) -> List[Dict[str, Any]]:

        cursor = self._db.cursor()
        cursor.execute(
            "SELECT * FROM contacts WHERE status = ? ORDER BY created_at DESC",
            (KeyStatus.ACTIVE.value,)
        )
        return [self._row_to_contact(row) for row in cursor.fetchall()]

    def _db_update_contact(self, contact_id: str, updates: Dict[str, Any]) -> bool:
        cursor = self._db.cursor()
        set_clause = ", ".join(f"{k} = ?" for k in updates.keys())
        values = list(updates.values()) + [contact_id]
        cursor.execute(
            f"UPDATE contacts SET {set_clause} WHERE contact_id = ?",
            values
        )
        self._db.commit()
        return cursor.rowcount > 0

    def _row_to_contact(self, row) -> Dict[str, Any]:

        columns = [
            "contact_id", "name", "public_key_pem", "algorithm", "fingerprint",
            "status", "verified", "created_at", "updated_at",
            "revoked_at", "revocation_reason", "rotation_successor_id"
        ]
        contact = dict(zip(columns, row))
        contact["verified"] = bool(contact.get("verified", 0))
        return contact


    @staticmethod
    def _serialize_public_key(public_key) -> bytes:
        return public_key.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo
        )