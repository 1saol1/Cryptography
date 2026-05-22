import os
import sys
import base64
import copy
import pytest

project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, project_root)

from unittest.mock import MagicMock
from src.core.import_export.sharing_service import SharingService


SHARE_PACKAGE = {
    "share_id": "test-123",
    "entry": {"title": "Test", "password": "secret"},
    "sharer": "alice"
}


class TestSharingSecurity:

    @pytest.fixture(autouse=True)
    def setup(self):
        self.svc = SharingService(
            db_connection=None,
            crypto_service=MagicMock(),
            key_manager=MagicMock(),
            audit_logger=None,
            entry_manager=MagicMock()
        )

    def test_password_encrypt_decrypt(self):
        encrypted = self.svc._encrypt_share_package(
            SHARE_PACKAGE, "password", password="Pass123!"
        )
        decrypted = self.svc._decrypt_password_share(encrypted, "Pass123!")
        assert decrypted["share_id"] == "test-123"

    def test_wrong_password_fails(self):
        encrypted = self.svc._encrypt_share_package(
            SHARE_PACKAGE, "password", password="Pass123!"
        )
        with pytest.raises(ValueError):
            self.svc._decrypt_password_share(encrypted, "WrongPass!")

    def test_tamper_detected(self):
        encrypted = self.svc._encrypt_share_package(
            SHARE_PACKAGE, "password", password="Pass123!"
        )
        tampered = copy.deepcopy(encrypted)
        data = bytearray(base64.b64decode(tampered["data"]))
        data[0] ^= 0xFF
        tampered["data"] = base64.b64encode(bytes(data)).decode()

        with pytest.raises(ValueError):
            self.svc._decrypt_password_share(tampered, "Pass123!")

    def test_hmac_in_package(self):
        encrypted = self.svc._encrypt_share_package(
            SHARE_PACKAGE, "password", password="Pass123!"
        )
        assert "integrity" in encrypted
        assert "hmac" in encrypted["integrity"]


if __name__ == "__main__":
    t = TestSharingSecurity()

    class FakeRequest:
        pass

    t.setup.__wrapped__(t) if hasattr(t.setup, '__wrapped__') else None

    svc = SharingService(
        db_connection=None, crypto_service=MagicMock(),
        key_manager=MagicMock(), audit_logger=None,
        entry_manager=MagicMock()
    )
    t.svc = svc
    t.test_password_encrypt_decrypt()
    t.test_wrong_password_fails()
    t.test_tamper_detected()
    t.test_hmac_in_package()
    print("Все тесты пройдены")