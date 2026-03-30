import secrets
from datetime import datetime
from typing import Optional


class SecureClipboardItem:
    def __init__(self, data: str, data_type: str, source_entry_id: Optional[str] = None):
        self.data_type = data_type
        self.source_entry_id = source_entry_id
        self.copied_at = datetime.utcnow()

        self._mask = secrets.token_bytes(32)

        self._obfuscated_data = self._obfuscate(data)

    def _obfuscate(self, data: str) -> bytes:
        data_bytes = data.encode('utf-8')
        obfuscated = bytes([
            b ^ self._mask[i % len(self._mask)]
            for i, b in enumerate(data_bytes)
        ])
        return obfuscated

    def _deobfuscate(self) -> str:
        try:
            data_bytes = bytes([
                b ^ self._mask[i % len(self._mask)]
                for i, b in enumerate(self._obfuscated_data)
            ])
            return data_bytes.decode('utf-8')
        except Exception:
            return ""

    def get_data(self) -> str:
        return self._deobfuscate()

    def secure_wipe(self):
        if hasattr(self, '_obfuscated_data'):
            self._obfuscated_data = bytes(len(self._obfuscated_data))

        if hasattr(self, '_mask'):
            self._mask = bytes(len(self._mask))

        self.data_type = ""
        self.source_entry_id = None
        self.copied_at = None

    def get_status(self) -> dict:
        remaining = None
        if self.copied_at:
            remaining = (datetime.utcnow() - self.copied_at).total_seconds()

        return {
            'data_type': self.data_type,
            'source_entry_id': self.source_entry_id,
            'copied_at': self.copied_at.isoformat() if self.copied_at else None,
            'age_seconds': remaining
        }