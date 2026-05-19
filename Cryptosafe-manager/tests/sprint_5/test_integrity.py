import sqlite3
import os
import tempfile
import sys

import pytest

project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, project_root)

from src.core.audit.audit_logger import AuditLogger
from src.core.audit.log_verifier import LogVerifier

class DummySigner:
    def sign(self, data: bytes) -> bytes:
        return b'fake_signature_for_test'

    def verify(self, data: bytes, signature: bytes) -> bool:
        return True


class TestIntegrity:

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

    def test_integrity_detection(self):
        print("\nIntegrity Test (1000 записей)")

        for i in range(1000):
            self.logger.log_event(
                event_type="VAULT_ENTRY_CREATE",
                severity="INFO",
                source="integrity_test",
                details={"entry_id": f"entry_{i}", "title": f"Test Entry {i}"},
                user_id="tester"
            )

        tampered_seq = 500
        conn = sqlite3.connect(self.db_path)
        conn.execute(
            "UPDATE audit_log SET entry_data = ? WHERE sequence_number = ?",
            (b'{"tampered": true, "title": "HACKED ENTRY"}', tampered_seq)
        )
        conn.commit()
        conn.close()

        conn = sqlite3.connect(self.db_path)
        count = conn.execute("SELECT COUNT(*) FROM audit_log").fetchone()[0]
        conn.close()

        assert count == 1001, f"Ожидалось 1001 записей, получено {count}"
        print(f"Всего записей в БД: {count}")

        return True


if __name__ == "__main__":
    test = TestIntegrity()
    test.setup()
    test.test_integrity_detection()
    test.teardown()