import sqlite3
import os
import tempfile
import hashlib


class TestIntegrity:

    def setup(self):
        self.temp_file = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
        self.db_path = self.temp_file.name
        self.temp_file.close()

        # Создаём таблицу
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
        """, (seq, prev_hash, "TEST", data, entry_hash, "fake_signature", "2026-01-01"))

        conn.commit()
        conn.close()

    def get_entry_hash(self, seq):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.execute("SELECT entry_hash FROM audit_log WHERE sequence_number = ?", (seq,))
        result = cursor.fetchone()
        conn.close()
        return result[0] if result else None

    def tamper_entry(self, seq, new_data):
        conn = sqlite3.connect(self.db_path)
        new_hash = hashlib.sha256(new_data.encode()).hexdigest()
        conn.execute("""
            UPDATE audit_log 
            SET entry_data = ?, entry_hash = ?
            WHERE sequence_number = ?
        """, (new_data, new_hash, seq))
        conn.commit()
        conn.close()

    def test_tampering_detection(self):
        print("Проверка обнаружения подделки логов")

        prev_hash = "0" * 64
        for i in range(1000):
            data = f'{{"msg": "entry {i}", "value": {i}}}'
            self.add_log_entry(i, prev_hash, data)
            prev_hash = self.get_entry_hash(i)

        tampered_seq = 500
        self.tamper_entry(tampered_seq, '{"msg": "TAMPERED!!!", "value": 99999}')

        conn = sqlite3.connect(self.db_path)
        rows = conn.execute(
            "SELECT sequence_number, previous_hash, entry_hash FROM audit_log ORDER BY sequence_number"
        ).fetchall()
        conn.close()

        broken_at = None
        for i in range(1, len(rows)):
            curr_prev_hash = rows[i][1]
            prev_curr_hash = rows[i - 1][2]

            if curr_prev_hash != prev_curr_hash:
                broken_at = rows[i][0]
                break

        if broken_at is not None:
            print(f"Подделка обнаружена!")
            print(f"   Разрыв цепочки найден на записи #{broken_at}")
        else:
            print("Подделка не обнаружена")

        return broken_at is not None


if __name__ == "__main__":
    test = TestIntegrity()
    test.setup()
    test.test_tampering_detection()
    test.cleanup()