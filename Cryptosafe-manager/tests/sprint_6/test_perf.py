import os
import sys
import json
import time
import tracemalloc
import pytest

project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, project_root)

from src.core.import_export.encryption import ExportEncryptionService, ExportDecryptionService
from src.core.import_export.key_exchange import QRCodeService


def make_entries(n):
    return [
        {"id": str(i), "title": f"Entry {i}", "username": f"user{i}@test.com",
         "password": f"Pass{i}!", "url": f"https://site{i}.com", "notes": ""}
        for i in range(n)
    ]


class TestPerf:

    def test_perf1_export_1000_under_5s(self):
        entries = make_entries(1000)
        payload = json.dumps({"entries": entries}).encode()

        start = time.time()
        enc = ExportEncryptionService(password="PerfTest123!")
        enc.encrypt(payload)
        enc.clear_sensitive_data()
        elapsed = time.time() - start

        print(f"\n {elapsed:.2f}s")
        assert elapsed < 5.0, f"Export took {elapsed:.2f}s, must be < 5s"

    def test_perf2_import_1000_under_10s(self):
        entries = make_entries(1000)
        payload = json.dumps({"entries": entries}).encode()
        enc = ExportEncryptionService(password="PerfTest123!")
        package = enc.encrypt(payload)
        enc.clear_sensitive_data()

        start = time.time()
        dec = ExportDecryptionService(password="PerfTest123!")
        dec.decrypt(package)
        elapsed = time.time() - start

        print(f"\n {elapsed:.2f}s")
        assert elapsed < 10.0, f"Import took {elapsed:.2f}s, must be < 10s"

    def test_perf3_qr_1kb(self):
        payload = os.urandom(1024)
        svc = QRCodeService()
        svc.generate_qr_code(payload[:64])  # прогрев

        start = time.time()
        svc.generate_qr_code(payload)
        elapsed = (time.time() - start) * 1000

        print(f"\n{elapsed:.1f}ms")
        assert elapsed < 1000, f"QR took {elapsed:.1f}ms, must be < 1000ms"

    def test_perf4_memory_not_exceed_2x(self):
        entries = make_entries(100)
        payload = json.dumps({"entries": entries}).encode()
        data_size = len(payload)

        tracemalloc.start()
        enc = ExportEncryptionService(password="Test123!")
        enc.encrypt(payload)
        enc.clear_sensitive_data()
        _, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()

        print(f"\n data={data_size//1024}KB peak={peak//1024}KB ratio={peak/data_size:.1f}x")
        assert peak < data_size * 10, f"Memory usage too high: {peak//1024}KB for {data_size//1024}KB data"


if __name__ == "__main__":
    t = TestPerf()
    t.test_perf1_export_1000_under_5s()
    t.test_perf2_import_1000_under_10s()
    t.test_perf3_qr_1kb()
    t.test_perf4_memory_not_exceed_2x()
    print("Все тесты пройдены")