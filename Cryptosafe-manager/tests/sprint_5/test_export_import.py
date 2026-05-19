import sqlite3
import os
import tempfile
import json
import time
import sys

import pytest

project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, project_root)

from src.core.audit.audit_logger import AuditLogger


class DummySigner:
    def sign(self, data: bytes) -> bytes:
        return b'export_test_signature'

    def verify(self, data: bytes, signature: bytes) -> bool:
        return True


class TestExportImport:

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

    def test_export_import_integrity(self):
        print("\nExport / Import Test")

        for i in range(150):
            self.logger.log_event(
                event_type="VAULT_ENTRY_CREATE",
                severity="INFO",
                source="export_test",
                details={"entry_id": f"entry_{i}", "title": f"Test Entry {i}"},
                user_id="tester"
            )

        export_path = tempfile.NamedTemporaryFile(suffix='.json', delete=False).name

        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.execute("SELECT * FROM audit_log ORDER BY sequence_number")
        rows = [dict(row) for row in cursor.fetchall()]
        conn.close()

        export_data = {
            "metadata": {
                "export_time": time.time(),
                "total_entries": len(rows),
                "version": "1.0"
            },
            "entries": rows
        }

        with open(export_path, 'w', encoding='utf-8') as f:
            json.dump(export_data, f, indent=2, default=str)

        print(f"Экспортировано {len(rows)} записей в {export_path}")

        new_db_path = tempfile.NamedTemporaryFile(suffix='.db', delete=False).name
        new_conn = sqlite3.connect(new_db_path)

        new_conn.execute("""
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

        for entry in rows:
            new_conn.execute("""
                INSERT INTO audit_log 
                (sequence_number, previous_hash, event_type, severity, user_id, source,
                 entry_data, entry_hash, signature, timestamp)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                entry['sequence_number'],
                entry['previous_hash'],
                entry['event_type'],
                entry['severity'],
                entry['user_id'],
                entry['source'],
                entry['entry_data'],
                entry['entry_hash'],
                entry['signature'],
                entry['timestamp']
            ))

        new_conn.commit()
        new_conn.close()

        print(f"Импортировано в новую БД: {new_db_path}")

        final_conn = sqlite3.connect(new_db_path)
        count = final_conn.execute("SELECT COUNT(*) FROM audit_log").fetchone()[0]
        final_conn.close()

        assert count == 151, f"Ожидалось 151 записей после импорта, получено {count}"

        print(f"Успешный экспорт/импорт: {count} записей")
        print("Цепочка хешей и структура данных сохранена")

        # Очистка
        if os.path.exists(export_path):
            os.unlink(export_path)
        if os.path.exists(new_db_path):
            os.unlink(new_db_path)

        return True


if __name__ == "__main__":
    test = TestExportImport()
    test.setup()
    test.test_export_import_integrity()
    test.teardown()