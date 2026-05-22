import json
import base64
from datetime import datetime
from typing import Dict, Any, List, Optional


class JSONHandler:

    @staticmethod
    def serialize(entries: List[Dict[str, Any]], metadata: Optional[Dict[str, Any]] = None) -> str:

        if metadata is None:
            metadata = {}

        export_data = {
            "version": "1.0",
            "exported_at": datetime.utcnow().isoformat() + "Z",
            "entry_count": len(entries),
            "entries": entries,
            **metadata
        }

        return json.dumps(export_data, indent=2, sort_keys=True, default=str)

    @staticmethod
    def deserialize(content: str) -> Dict[str, Any]:

        try:
            data = json.loads(content)
            return data
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON format: {e}")

    @staticmethod
    def create_encrypted_package(encrypted_data_bytes: bytes,
                                 encryption_info: Dict[str, Any],
                                 signature: Optional[bytes] = None) -> Dict[str, Any]:


        import hashlib
        data_hash = hashlib.sha256(encrypted_data_bytes).hexdigest()

        package = {
            "version": "1.0",
            "cryptosafe_export": True,
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "encryption": encryption_info,
            "data": base64.b64encode(encrypted_data_bytes).decode('ascii'),
            "integrity": {
                "hash": data_hash,
                "hash_algorithm": "SHA256"
            }
        }

        if signature:
            package["integrity"]["signature"] = base64.b64encode(signature).decode('ascii')

        return package

    @staticmethod
    def parse_encrypted_package(package: Dict[str, Any]) -> tuple:
        import hashlib

        if not package.get("cryptosafe_export"):
            raise ValueError("Not a valid CryptoSafe export file")

        encrypted_data = base64.b64decode(package["data"])
        encryption_info = package.get("encryption", {})
        integrity_info = package.get("integrity", {})

        expected_hash = integrity_info.get("hash")
        if expected_hash:
            actual_hash = hashlib.sha256(encrypted_data).hexdigest()
            if actual_hash != expected_hash:
                raise ValueError(
                    "Integrity check failed — file may be corrupted or tampered"
                )

        return encrypted_data, encryption_info, integrity_info