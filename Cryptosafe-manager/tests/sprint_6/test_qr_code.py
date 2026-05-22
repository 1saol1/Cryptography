import os
import sys
import json
import base64
import hashlib
import pytest
from datetime import datetime, timedelta

project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, project_root)

from src.core.import_export.key_exchange import QRCodeService, QRScanResult


class TestQRCode:

    @pytest.fixture(autouse=True)
    def setup(self):
        self.service = QRCodeService()

    def test_generate_qr(self):
        qr_codes = self.service.generate_qr_code(b"test data")
        assert len(qr_codes) > 0

    def test_qr_is_png(self):
        qr_codes = self.service.generate_qr_code(b"test")
        assert qr_codes[0].startswith("data:image/png;base64,")

    def test_1kb_payload(self):
        payload = os.urandom(1024)
        qr_codes = self.service.generate_qr_code(payload)
        assert len(qr_codes) > 0

    def test_expired_qr_rejected(self):
        payload = {
            "version": "1.0",
            "type": "share_link",
            "timestamp": "2020-01-01T00:00:00Z",
            "expires_at": "2020-01-01T00:05:00Z",
            "nonce": "abc123",
            "data": base64.b64encode(b"test").decode(),
            "checksum": hashlib.sha256(b"test").hexdigest()[:16]
        }
        result = self.service._validate_and_parse(json.dumps(payload))
        assert result["result"] == QRScanResult.EXPIRED

    def test_replay_attack_detected(self):
        future = (datetime.utcnow() + timedelta(minutes=5)).isoformat() + "Z"
        payload = {
            "version": "1.0",
            "type": "share_link",
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "expires_at": future,
            "nonce": "unique-nonce-replay-test",
            "data": base64.b64encode(b"test").decode(),
            "checksum": hashlib.sha256(b"test").hexdigest()[:16]
        }
        self.service._validate_and_parse(json.dumps(payload))
        result = self.service._validate_and_parse(json.dumps(payload))
        assert result["result"] == QRScanResult.REPLAY_ATTACK


if __name__ == "__main__":
    t = TestQRCode()
    t.service = QRCodeService()
    t.test_generate_qr()
    t.test_qr_is_png()
    t.test_1kb_payload()
    t.test_expired_qr_rejected()
    t.test_replay_attack_detected()
    print("Все тесты пройдены")