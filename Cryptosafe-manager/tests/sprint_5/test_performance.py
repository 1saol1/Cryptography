import sqlite3
import os
import tempfile
import time
import hashlib


class TestPerformance10000:

    def setup(self):
        self.temp_file = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
        self.db_path = self.temp_file.name
        self.temp_file.close()

        conn = sqlite3.connect(self.db_path)
        conn.execute("""
            CREATE TABLE audit_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                sequence_number INTEGER NOT NULL UNIQUE,
                previous_hash TEXT NOT NULL,
                event_type TEXT NOT NULL,
                entry_data TEXT NOT NULL,
                entry_hash TEXT NOT NULL,
                signature TEXT NOT NULL,
                timestamp TEXT NOT NULL
            )
        """)

        genesis_hash = hashlib.sha256(b'genesis').hexdigest()
        conn.execute("""
            INSERT INTO audit_log 
            (sequence_number, previous_hash, event_type, entry_data, entry_hash, signature, timestamp)
            VALUES (0, ?, 'GENESIS', ?, ?, ?, ?)
        """, ('0' * 64, '{}', genesis_hash, '0' * 64, time.time()))

        conn.commit()
        conn.close()

    def cleanup(self):
        if os.path.exists(self.db_path):
            os.unlink(self.db_path)

    def add_log_entry(self, seq, prev_hash, data):
        conn = sqlite3.connect(self.db_path)

        entry_hash = hashlib.sha256(data.encode()).hexdigest()

        conn.execute("""
            INSERT INTO audit_log 
            (sequence_number, previous_hash, event_type, entry_data, entry_hash, signature, timestamp)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (seq, prev_hash, "TEST_EVENT", data, entry_hash, "fake_signature", time.time()))

        conn.commit()
        conn.close()

    def test_10000_events(self):

        start_time = time.time()

        prev_hash = self.get_latest_hash()
        for i in range(1, 10001):
            data = f'{{"event": "test_{i}", "value": {i}}}'
            entry_hash = hashlib.sha256(data.encode()).hexdigest()

            conn = sqlite3.connect(self.db_path)
            conn.execute("""
                INSERT INTO audit_log 
                (sequence_number, previous_hash, event_type, entry_data, entry_hash, signature, timestamp)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (i, prev_hash, "TEST_EVENT", data, entry_hash, "fake_signature", time.time()))
            conn.commit()
            conn.close()

            prev_hash = entry_hash

        end_time = time.time()
        total_time = end_time - start_time

        print(f"\n2. Результат:")
        print(f"   Время записи: {total_time:.2f} секунд")
        print(f"   Скорость: {10000 / total_time:.0f} событий/сек")

        conn = sqlite3.connect(self.db_path)
        cursor = conn.execute("SELECT COUNT(*) FROM audit_log")
        count = cursor.fetchone()[0]
        conn.close()

        print(f"   Записей в БД: {count}")


        if count >= 10001:
            print("10000 событий успешно записаны")
            print(f"   Время: {total_time:.2f} сек")
        else:
            print("Не все события записались")

        return count >= 10001

    def get_latest_hash(self):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.execute("SELECT entry_hash FROM audit_log ORDER BY sequence_number DESC LIMIT 1")
        row = cursor.fetchone()
        conn.close()
        return row[0] if row else '0' * 64


if __name__ == "__main__":
    test = TestPerformance10000()
    test.setup()
    test.test_10000_events()
    test.cleanup()