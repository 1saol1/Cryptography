import time
import sqlite3
import tempfile
import os
import hashlib
import random
import sys
import tracemalloc

project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, project_root)

from src.core.audit.log_verifier import LogVerifier
from src.core.audit.log_signer import AuditLogSigner
from src.core.crypto.key_manager import KeyManager


class TestPerformance:

    def setup(self):
        self.temp_db = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
        self.db_path = self.temp_db.name
        self.temp_db.close()

        conn = sqlite3.connect(self.db_path)
        conn.execute("""
            CREATE TABLE audit_log (
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

        genesis_hash = hashlib.sha256(b'genesis').hexdigest()
        conn.execute("""
            INSERT INTO audit_log 
            (sequence_number, previous_hash, event_type, severity, user_id, source, entry_data, entry_hash, signature, timestamp)
            VALUES (0, ?, 'SYSTEM_GENESIS', 'INFO', 'system', 'test', ?, ?, ?, ?)
        """, ('0' * 64, b'{}', genesis_hash, '0' * 64, time.time()))

        conn.commit()
        conn.close()

        class Logger:
            def __init__(self, db_path):
                self.db_path = db_path

            def _get_next_sequence(self, conn):
                cursor = conn.execute("SELECT MAX(sequence_number) FROM audit_log")
                max_seq = cursor.fetchone()[0]
                return (max_seq or -1) + 1

            def log_event(self, event_type, severity="INFO", user_id="tester"):
                conn = sqlite3.connect(self.db_path)
                try:
                    seq = self._get_next_sequence(conn)
                    entry_data = f'{{"event":"{event_type}"}}'
                    entry_hash = hashlib.sha256(entry_data.encode()).hexdigest()

                    conn.execute("""
                        INSERT INTO audit_log 
                        (sequence_number, previous_hash, event_type, severity, user_id, source, entry_data, entry_hash, signature, timestamp)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        seq, '0' * 64, event_type, severity, user_id, 'test',
                        entry_data.encode(), entry_hash, '0' * 64, time.time()
                    ))
                    conn.commit()
                finally:
                    conn.close()

        self.logger = Logger(self.db_path)

    def cleanup(self):
        if os.path.exists(self.db_path):
            os.unlink(self.db_path)

    def test_one_log(self):
        start = time.perf_counter()
        self.logger.log_event("TEST")
        elapsed_ms = (time.perf_counter() - start) * 1000

        if elapsed_ms < 10:
            print(f" Одна запись = {elapsed_ms:.2f}ms (< 10ms)")
            return True
        else:
            print(f" Одна запись = {elapsed_ms:.2f}ms (должно быть < 10ms)")
            return False

    def test_verification_1000_entries(self):
        conn = sqlite3.connect(self.db_path)
        for i in range(1000):
            seq = i + 1
            entry_data = f'{{"event":"bulk_test_{i}"}}'
            entry_hash = hashlib.sha256(entry_data.encode()).hexdigest()
            conn.execute("""
                INSERT INTO audit_log 
                (sequence_number, previous_hash, event_type, severity, user_id, source, entry_data, entry_hash, signature, timestamp)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (seq, '0' * 64, 'BULK_TEST', 'INFO', 'tester', 'test',
                  entry_data.encode(), entry_hash, '0' * 64, time.time()))
        conn.commit()
        conn.close()

        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row

        key_manager = KeyManager()
        key_manager.cache_key(b'\x00' * 32)
        signer = AuditLogSigner(key_manager)
        verifier = LogVerifier(conn, signer)

        start = time.perf_counter()
        result = verifier.verify_integrity()
        elapsed_ms = (time.perf_counter() - start) * 1000

        conn.close()

        if elapsed_ms < 1000:
            print(f"Верификация {result['total_entries']} записей = {elapsed_ms:.2f}ms (< 1000ms)")
            return True
        else:
            print(f"Верификация = {elapsed_ms:.2f}ms (должно быть < 1000ms)")
            return False

    def test_query_filter_10000_entries(self):
        conn = sqlite3.connect(self.db_path)

        conn.execute("DELETE FROM audit_log WHERE sequence_number > 0")

        event_types = ['AUTH_LOGIN_SUCCESS', 'CLIPBOARD_COPY', 'VAULT_ENTRY_CREATE',
                       'AUTH_LOGIN_FAILURE', 'CONFIG_CHANGE']
        severities = ['INFO', 'WARN', 'ERROR', 'CRITICAL']
        users = ['alice', 'bob', 'charlie', 'diana']

        for i in range(10000):
            seq = i + 1
            event_type = random.choice(event_types)
            severity = random.choice(severities)
            user_id = random.choice(users)
            entry_data = f'{{"event":"{event_type}","user":"{user_id}"}}'
            entry_hash = hashlib.sha256(entry_data.encode()).hexdigest()
            timestamp = time.time() - random.randint(0, 86400 * 30)  # последние 30 дней

            conn.execute("""
                INSERT INTO audit_log 
                (sequence_number, previous_hash, event_type, severity, user_id, source, entry_data, entry_hash, signature, timestamp)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (seq, '0' * 64, event_type, severity, user_id, 'test',
                  entry_data.encode(), entry_hash, '0' * 64, timestamp))

        conn.commit()

        start = time.perf_counter()

        cursor = conn.execute("""
            SELECT COUNT(*) FROM audit_log 
            WHERE event_type = 'AUTH_LOGIN_FAILURE' 
            AND severity = 'WARN'
            AND user_id = 'alice'
        """)
        count = cursor.fetchone()[0]

        elapsed_ms = (time.perf_counter() - start) * 1000
        conn.close()

        if elapsed_ms < 500:
            print(f"Фильтрация 10000 записей = {elapsed_ms:.2f}ms (< 500ms)")
            print(f"   Найдено записей: {count}")
            return True
        else:
            print(f"Фильтрация = {elapsed_ms:.2f}ms (должно быть < 500ms)")
            return False

    def test_memory_10000_entries(self):
        print("\n[PERF-4] Проверка использования памяти...")

        tracemalloc.start()

        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row

        cursor = conn.execute("SELECT * FROM audit_log ORDER BY sequence_number LIMIT 10000")
        rows = cursor.fetchall()  # Загружаем в память

        current, peak = tracemalloc.get_traced_memory()
        current_mb = current / (1024 * 1024)
        peak_mb = peak / (1024 * 1024)

        tracemalloc.stop()
        conn.close()

        if current_mb < 50:
            print(f"Память для 10000 записей = {current_mb:.2f}MB (< 50MB)")
            print(f"Пиковая память: {peak_mb:.2f}MB")
            print(f"Загружено записей: {len(rows)}")
            return True
        else:
            print(f"Память = {current_mb:.2f}MB (должно быть < 50MB)")
            return False


if __name__ == "__main__":
    test = TestPerformance()
    test.setup()

    print("Тест производительности логирования")
    test.test_one_log()

    print("Тест производительности верификации")
    test.test_verification_1000_entries()

    print("Тест производительности фильтрации")
    test.test_query_filter_10000_entries()

    print("Тест использования памяти")
    test.test_memory_10000_entries()

    test.cleanup()