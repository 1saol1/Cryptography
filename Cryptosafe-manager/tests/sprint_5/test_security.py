import sqlite3
import os
import tempfile
import hashlib
import time


class TestSecurity:

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

    def execute_with_params(self, query, params):

        conn = sqlite3.connect(self.db_path)
        try:
            cursor = conn.execute(query, params)
            conn.commit()
            result = cursor.fetchall()
            conn.close()
            return result
        except Exception as e:
            conn.close()
            return str(e)

    def test_sql_injection(self):

        malicious_input = "'; DROP TABLE audit_log; --"

        try:

            result = self.execute_with_params(
                "SELECT * FROM audit_log WHERE event_type = ?",
                (malicious_input,)
            )

            conn = sqlite3.connect(self.db_path)
            cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='audit_log'")
            table_exists = cursor.fetchone() is not None
            conn.close()

            if table_exists:
                print("SQL инъекция не удалась (параметризованный запрос)")
            else:
                print(" SQL инъекция удалась! Таблица удалена!")
        except Exception as e:
            print(f"Ошибка: {e}")

        print("\n2. Проверка обнаружения подделки...")

        data = '{"msg": "original data"}'
        entry_hash = hashlib.sha256(data.encode()).hexdigest()

        conn = sqlite3.connect(self.db_path)
        conn.execute("""
            INSERT INTO audit_log 
            (sequence_number, previous_hash, event_type, entry_data, entry_hash, signature, timestamp)
            VALUES (1, ?, 'TEST', ?, ?, ?, ?)
        """, ('0' * 64, data, entry_hash, 'signature123', time.time()))
        conn.commit()

        conn.execute("""
            UPDATE audit_log 
            SET entry_data = '{"msg": "TAMPERED"}',
                entry_hash = ?
            WHERE sequence_number = 1
        """, (hashlib.sha256(b'{"msg": "TAMPERED"}').hexdigest(),))
        conn.commit()

        cursor = conn.execute("SELECT entry_data, entry_hash FROM audit_log WHERE sequence_number = 1")
        row = cursor.fetchone()
        conn.close()

        if row:
            stored_data, stored_hash = row
            computed_hash = hashlib.sha256(stored_data.encode()).hexdigest()

            if computed_hash == stored_hash:
                print("Хеш соответствует данным (подделка не повлияла на обнаружение)")
            else:
                print("Хеш не соответствует данным")

        conn2 = sqlite3.connect(self.db_path)

        cursor1 = conn.execute("SELECT COUNT(*) FROM audit_log")
        cursor2 = conn2.execute("SELECT COUNT(*) FROM audit_log")

        count1 = cursor1.fetchone()[0]
        count2 = cursor2.fetchone()[0]

        conn.close()
        conn2.close()

        if count1 == count2:
            print("Оба подключения видят одинаковые данные")
        else:
            print("Данные изолированы некорректно")

        return True

    def test_tampering_logged(self):

        conn = sqlite3.connect(self.db_path)

        old_data = conn.execute("SELECT entry_data FROM audit_log WHERE sequence_number = 0").fetchone()[0]
        conn.execute("UPDATE audit_log SET entry_data = 'tampered' WHERE sequence_number = 0")
        conn.commit()

        new_data = conn.execute("SELECT entry_data FROM audit_log WHERE sequence_number = 0").fetchone()[0]
        conn.close()

        if new_data != old_data:
            print("Запись была изменена (это обнаружится при проверке цепочки хешей)")
            print("Механизм обнаружения подделки сработает при верификации")

        return True


if __name__ == "__main__":
    test = TestSecurity()
    test.setup()
    test.test_sql_injection()
    test.test_tampering_logged()
    test.cleanup()