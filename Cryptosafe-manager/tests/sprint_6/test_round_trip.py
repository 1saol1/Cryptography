import os
import sys
import json
import pytest

project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, project_root)

from src.core.import_export.encryption import ExportEncryptionService, ExportDecryptionService
from src.core.import_export.formats.csv_handler import CSVHandler
from src.core.import_export.formats.json_handler import JSONHandler


class TestRoundTrip:

    def test_encrypt_decrypt(self):
        password = "TestPassword123!"
        data = '{"title": "Test Entry", "password": "secret123"}'

        enc = ExportEncryptionService(password=password)
        package = enc.encrypt(data.encode("utf-8"))
        enc.clear_sensitive_data()

        dec = ExportDecryptionService(password=password)
        result = dec.decrypt(package)

        assert result is not None
        assert result["title"] == "Test Entry"

    def test_wrong_password_fails(self):
        enc = ExportEncryptionService(password="correct")
        package = enc.encrypt(b"data")
        enc.clear_sensitive_data()

        dec = ExportDecryptionService(password="wrong")
        with pytest.raises(ValueError):
            dec.decrypt(package)

    def test_csv_serialize_deserialize(self):
        entries = [
            {"title": "Google", "username": "user@gmail.com",
             "password": "pass123", "url": "https://google.com", "notes": ""}
        ]
        csv_str = CSVHandler.serialize(entries)
        restored = CSVHandler.deserialize(csv_str)

        assert len(restored) == 1
        assert restored[0]["title"] == "Google"
        assert restored[0]["password"] == "pass123"

    def test_json_package_has_required_fields(self):
        package = JSONHandler.create_encrypted_package(b"test", {})

        assert package["cryptosafe_export"] is True
        assert package["version"] == "1.0"
        assert "data" in package
        assert "integrity" in package
        assert "hash" in package["integrity"]


if __name__ == "__main__":
    t = TestRoundTrip()
    t.test_encrypt_decrypt()
    t.test_wrong_password_fails()
    t.test_csv_serialize_deserialize()
    t.test_json_package_has_required_fields()
    print("Все тесты пройдены")