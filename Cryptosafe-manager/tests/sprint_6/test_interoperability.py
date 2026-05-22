import os
import sys
import json
import pytest

project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, project_root)

from src.core.import_export.formats.csv_handler import CSVHandler
from src.core.import_export.formats.bitwarden_handler import BitwardenHandler


BITWARDEN_SAMPLE = json.dumps({
    "encrypted": False,
    "folders": [],
    "items": [
        {
            "id": "1", "type": 1, "name": "GitHub",
            "notes": "work account", "folderId": None,
            "login": {
                "username": "dev@example.com",
                "password": "SecretPass123!",
                "uris": [{"uri": "https://github.com"}],
                "totp": None
            }
        }
    ]
})

LASTPASS_CSV = """url,username,password,totp,extra,name,grouping,fav
https://github.com,dev@example.com,SecretPass123!,,,GitHub,Work,0
"""


class TestInteroperability:

    def test_bitwarden_import(self):
        entries = BitwardenHandler.deserialize(BITWARDEN_SAMPLE)
        assert len(entries) == 1

    def test_bitwarden_fields_mapped(self):
        entries = BitwardenHandler.deserialize(BITWARDEN_SAMPLE)
        e = entries[0]
        assert e["username"] == "dev@example.com"
        assert e["password"] == "SecretPass123!"

    def test_lastpass_csv_import(self):
        entries = CSVHandler.deserialize(LASTPASS_CSV)
        assert len(entries) > 0

    def test_csv_export_reimport(self):
        original = [{"title": "Test", "username": "u@test.com",
                     "password": "pass", "url": "https://test.com", "notes": ""}]
        csv_str = CSVHandler.serialize(original)
        restored = CSVHandler.deserialize(csv_str)
        assert restored[0]["title"] == "Test"


if __name__ == "__main__":
    t = TestInteroperability()
    t.test_bitwarden_import()
    t.test_bitwarden_fields_mapped()
    t.test_lastpass_csv_import()
    t.test_csv_export_reimport()
    print("Все тесты пройдены")