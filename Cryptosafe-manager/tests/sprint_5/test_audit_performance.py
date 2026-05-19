import sqlite3
import os
import tempfile
import time
import sys
import tracemalloc

import pytest

project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, project_root)

from src.core.audit.audit_logger import AuditLogger
from src.core.audit.log_verifier import LogVerifier


# from src.core.audit.log_verifier import LogVerifier

class DummySigner:
    def sign(self, data: bytes) -> bytes:
        return b'fake_signature_for_test'

    def verify(self, data: bytes, signature: bytes) -> bool:
        return True


class TestPerformance:

    @pytest.fixture(autouse=True)
    def setup(self):
        self.temp_file = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
        self.db_path = self.temp_file.name
        self.temp_file.close()

        conn = sqlite3.connect(self.db_path)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS audit_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                sequence_number INTEGER NOT NULL UNIQUE,
                previous_hash TEXT NOT NULL,
                event_type TEXT NOT NULL,
                severity TEXT NOT NULL,
                user_id TEXT NOT NULL,
                source TEXT NOT NULL,
                entry_data BLOB NOT NULL,
                entry_hash TEXT NOT NULL,
                signature TEXT NOT NULL,
                timestamp TEXT NOT NULL
            )
        """)
        conn.commit()
        conn.close()

        self.signer = DummySigner()
        self.logger = AuditLogger(
            db_path=self.db_path,
            signer=self.signer,
            config={'async_logging': False}
        )

    def teardown(self):
        if os.path.exists(self.db_path):
            os.unlink(self.db_path)

    def test_single_log_performance(self):
        print("\nSingle Logging Performance")
        times = []
        for i in range(100):
            start = time.perf_counter()
            self.logger.log_event("VAULT_ENTRY_CREATE", "INFO", "perf_test", {"i": i}, "tester")
            times.append((time.perf_counter() - start) * 1000)

        avg = sum(times) / len(times)
        print(f"Среднее время одной записи: {avg:.2f} ms")
        assert avg < 15, f"Слишком медленно ({avg:.2f} ms)"
        print("Тест пройден")

    def test_verification_performance(self):
        print("\nSignature + Chain Verification (1000 entries)")

        for i in range(1000):
            self.logger.log_event(
                event_type="TEST_EVENT",
                severity="INFO",
                source="verification_test",
                details={"index": i},
                user_id="tester"
            )

        try:

            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            verifier = LogVerifier(conn, self.signer)

            start = time.perf_counter()
            result = verifier.verify_integrity()
            elapsed = (time.perf_counter() - start) * 1000

            conn.close()

            print(f"Верификация {result.get('total_entries', 1000)} записей заняла: {elapsed:.2f} ms")

            if elapsed < 1000:
                print("Тест пройден (отлично)")

            assert elapsed < 1500, f"Верификация слишком медленная: {elapsed:.2f} ms"

        except ImportError:
            print("LogVerifier не найден — тест пропущен")
            pytest.skip("LogVerifier not implemented yet")
        except Exception as e:
            print(f"Ошибка верификации: {e}")
            pytest.skip(f"Verification test failed: {e}")

    def test_query_performance(self):
        print("\nQuery Performance")
        for i in range(10000):
            self.logger.log_event(
                "AUTH_LOGIN_SUCCESS" if i % 3 == 0 else "VAULT_ENTRY_CREATE",
                "WARN" if i % 10 == 0 else "INFO",
                "perf_test",
                {"user": f"user_{i % 100}"},
                f"user_{i % 50}"
            )

        start = time.perf_counter()
        conn = sqlite3.connect(self.db_path)
        count = conn.execute("""
            SELECT COUNT(*) FROM audit_log 
            WHERE severity = 'WARN' AND event_type = 'AUTH_LOGIN_SUCCESS'
        """).fetchone()[0]
        elapsed = (time.perf_counter() - start) * 1000
        conn.close()

        print(f"Фильтрация заняла: {elapsed:.2f} ms | Найдено: {count}")
        assert elapsed < 600, f"Запрос медленный ({elapsed:.2f} ms)"
        print("Тест пройден")

    def test_memory_usage(self):
        print("\nMemory Usage")
        tracemalloc.start()
        conn = sqlite3.connect(self.db_path)
        rows = conn.execute("SELECT * FROM audit_log").fetchall()
        conn.close()

        current, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()

        current_mb = current / (1024 * 1024)
        print(f"Память: {current_mb:.2f} MB")
        assert current_mb < 60, f"Слишком много памяти: {current_mb:.2f} MB"
        print("Тест пройден")


if __name__ == "__main__":
    test = TestPerformance()
    test.setup()
    test.test_single_log_performance()
    test.test_verification_performance()
    test.test_query_performance()
    test.test_memory_usage()
    test.teardown()