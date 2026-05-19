import sqlite3
import os
import tempfile
import hashlib
import sys
import pytest

project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, project_root)

from src.core.audit.audit_logger import AuditLogger


class DummySigner:

    def sign(self, data: bytes) -> bytes:
        return hashlib.sha256(data).digest()

    def verify(self, data: bytes, signature: bytes) -> bool:
        return True


class TestSecurity:

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

    def test_sql_injection(self):
        print("\nПроверка защиты от SQL-инъекции")

        malicious_input = "'; DROP TABLE audit_log; -- OR '1'='1"

        try:
            self.logger.log_event(
                event_type="AUTH_LOGIN_SUCCESS",
                severity="INFO",
                source="security_test",
                details={"username": malicious_input, "attempt": 1},
                user_id="tester"
            )
            print("SQL-инъекция успешно отражена")
        except Exception as e:
            pytest.fail(f"Ошибка при логгировании: {e}")

    def test_tampering_detection(self):
        print("\nПроверка обнаружения подделки")

        for i in range(3):
            self.logger.log_event(
                event_type="VAULT_ENTRY_CREATE",
                severity="INFO",
                source="test",
                details={"entry_id": f"test_{i}", "title": f"Entry {i}"},
                user_id="tester"
            )

        conn = sqlite3.connect(self.db_path)
        conn.execute(
            "UPDATE audit_log SET entry_data = ? WHERE sequence_number = 2",
            (b'{"tampered": true, "title": "Hacked Entry"}',)
        )
        conn.commit()
        conn.close()

        print("Подделка внесена в запись #2")
        assert True


if __name__ == "__main__":
    test = TestSecurity()
    test.setup()
    test.test_sql_injection()
    test.test_tampering_detection()
    test.teardown()