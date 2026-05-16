import sqlite3
import os
import tempfile
import hashlib
import time
import shutil


class TestRecovery:

    def setup(self):

        self.temp_dir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.temp_dir, 'test.db')
        self.backup_path = os.path.join(self.temp_dir, 'test_backup.db')

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

        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)

    def add_log_entries(self, count):

        conn = sqlite3.connect(self.db_path)

        cursor = conn.execute("SELECT entry_hash FROM audit_log ORDER BY sequence_number DESC LIMIT 1")
        row = cursor.fetchone()
        prev_hash = row[0] if row else '0' * 64
        start_seq = conn.execute("SELECT MAX(sequence_number) FROM audit_log").fetchone()[0] or 0
        start_seq += 1

        for i in range(start_seq, start_seq + count):
            data = f'{{"event": "test_{i}", "value": {i}}}'
            entry_hash = hashlib.sha256(data.encode()).hexdigest()

            conn.execute("""
                INSERT INTO audit_log 
                (sequence_number, previous_hash, event_type, entry_data, entry_hash, signature, timestamp)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (i, prev_hash, "TEST", data, entry_hash, "fake_signature", time.time()))

            prev_hash = entry_hash

        conn.commit()
        conn.close()

    def corrupt_database(self):

        with open(self.db_path, 'r+b') as f:
            f.seek(1024)
            f.write(b'\x00\x00\x00\x00')

    def check_integrity(self):

        conn = sqlite3.connect(self.db_path)
        try:
            cursor = conn.execute("PRAGMA integrity_check")
            result = cursor.fetchone()[0]
            conn.close()
            return result == 'ok'
        except:
            return False

    def recover_from_backup(self):

        if os.path.exists(self.backup_path):
            shutil.copy2(self.backup_path, self.db_path)
            return True
        return False

    def test_recovery(self):

        self.add_log_entries(100)

        shutil.copy2(self.db_path, self.backup_path)
        print(f"Резервная копия: {self.backup_path}")

        is_ok = self.check_integrity()
        if is_ok:
            print("БД цела")
        else:
            print("БД уже повреждена")

        self.corrupt_database()

        is_ok = self.check_integrity()
        if not is_ok:
            print("Повреждение обнаружено")
        else:
            print("Повреждение не обнаружено")

        self.recover_from_backup()

        is_ok = self.check_integrity()

        conn = sqlite3.connect(self.db_path)
        cursor = conn.execute("SELECT COUNT(*) FROM audit_log")
        count = cursor.fetchone()[0]
        conn.close()


        if is_ok and count >= 101:
            print("Успешное восстановление после повреждения")
            print(f"   Записей восстановлено: {count}")
        elif is_ok:
            print("БД восстановлена, но часть данных потеряна")
            print(f"   Осталось записей: {count}")
        else:
            print("Не удалось восстановить БД")

        return is_ok


if __name__ == "__main__":
    test = TestRecovery()
    test.setup()
    test.test_recovery()
    test.cleanup()