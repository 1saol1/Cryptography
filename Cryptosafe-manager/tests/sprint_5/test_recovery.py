import sqlite3
import os
import tempfile
import shutil
import sys

import pytest

project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, project_root)

from src.core.audit.audit_logger import AuditLogger


class DummySigner:
    def sign(self, data: bytes) -> bytes:
        return b'fake_signature'

    def verify(self, data: bytes, signature: bytes) -> bool:
        return True


class TestRecovery:

    @pytest.fixture(autouse=True)
    def setup(self):
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.temp_dir, 'test_recovery.db')
        self.backup_path = os.path.join(self.temp_dir, 'backup.db')

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
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_recovery_after_corruption(self):
        print("\nRecovery Test")

        print("Создаём 200 записей...")
        for i in range(200):
            self.logger.log_event(
                event_type="VAULT_ENTRY_CREATE",
                severity="INFO",
                source="recovery_test",
                details={"entry_id": f"entry_{i}"},
                user_id="tester"
            )

        shutil.copy2(self.db_path, self.backup_path)

        print("Имитируем повреждение БД...")
        with open(self.db_path, 'r+b') as f:
            f.seek(512)
            f.write(b'\x00\x00\x00\x00\xFF\xFF\xFF\xFF')

        conn = sqlite3.connect(self.db_path)
        try:
            result = conn.execute("PRAGMA integrity_check").fetchone()[0]
            print(f"PRAGMA integrity_check: {result}")
        except:
            print("БД повреждена (ожидаемо)")
        finally:
            conn.close()

        shutil.copy2(self.backup_path, self.db_path)

        conn = sqlite3.connect(self.db_path)
        count = conn.execute("SELECT COUNT(*) FROM audit_log").fetchone()[0]
        conn.close()

        print(f"Записей после восстановления: {count}")

        assert count >= 200, f"После восстановления потеряны данные! Осталось только {count}"
        print("Восстановление успешно — данные сохранены")

        return True


if __name__ == "__main__":
    test = TestRecovery()
    test.setup()
    test.test_recovery_after_corruption()
    test.teardown()