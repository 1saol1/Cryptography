import os
import sys
import json
import time

project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, project_root)

from src.core.import_export.encryption import ExportEncryptionService, ExportDecryptionService
from src.core.import_export.formats.csv_handler import CSVHandler
from src.core.import_export.key_exchange import QRCodeService


def make_entries(n):
    return [
        {"id": str(i), "title": f"Entry {i}", "username": f"user{i}@test.com",
         "password": f"Pass{i}!", "url": f"https://site{i}.com", "notes": ""}
        for i in range(n)
    ]


class TestPerformance:

    def test_export_1000_entries(self):
        entries = make_entries(1000)
        payload = json.dumps({"entries": entries}).encode()

        start = time.time()
        enc = ExportEncryptionService(password="PerfTest123!")
        enc.encrypt(payload)
        enc.clear_sensitive_data()
        elapsed = time.time() - start

        print(f"\n  Export 1000 entries: {elapsed:.2f}s")

    def test_import_1000_entries(self):
        entries = make_entries(1000)
        payload = json.dumps({"entries": entries}).encode()
        enc = ExportEncryptionService(password="PerfTest123!")
        package = enc.encrypt(payload)
        enc.clear_sensitive_data()

        start = time.time()
        dec = ExportDecryptionService(password="PerfTest123!")
        dec.decrypt(package)
        elapsed = time.time() - start

        print(f"\n  Import 1000 entries: {elapsed:.2f}s")

    def test_qr_1kb(self):
        payload = os.urandom(1024)
        svc = QRCodeService()

        start = time.time()
        svc.generate_qr_code(payload)
        elapsed = (time.time() - start) * 1000

        print(f"\n  QR 1KB: {elapsed:.1f}ms")

    def test_csv_1000_entries(self):
        entries = make_entries(1000)

        start = time.time()
        csv_str = CSVHandler.serialize(entries)
        elapsed = time.time() - start

        print(f"\n  CSV 1000 entries: {elapsed:.2f}s, size: {len(csv_str)//1024}KB")


if __name__ == "__main__":
    t = TestPerformance()
    t.test_export_1000_entries()
    t.test_import_1000_entries()
    t.test_qr_1kb()
    t.test_csv_1000_entries()
    print("Измерения завершены")