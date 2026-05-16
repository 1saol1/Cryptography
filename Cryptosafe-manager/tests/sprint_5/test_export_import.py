import json
import sqlite3
import os
import tempfile
import hashlib
import time


class TestExportImport:

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
        """, (seq, prev_hash, "TEST", data, entry_hash, "fake_signature", time.time()))

        conn.commit()
        conn.close()

    def get_all_entries(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.execute("SELECT * FROM audit_log ORDER BY sequence_number")
        rows = cursor.fetchall()
        conn.close()
        return [dict(row) for row in rows]

    def export_to_json(self, output_path):
        entries = self.get_all_entries()

        export_data = {
            'metadata': {
                'export_time': time.time(),
                'total_entries': len(entries)
            },
            'entries': entries
        }

        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(export_data, f, indent=2, default=str)

        return export_data

    def import_from_json(self, json_path):
        with open(json_path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        new_temp = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
        new_db_path = new_temp.name
        new_temp.close()

        conn = sqlite3.connect(new_db_path)
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

        for entry in data['entries']:
            conn.execute("""
                INSERT INTO audit_log 
                (sequence_number, previous_hash, event_type, entry_data, entry_hash, signature, timestamp)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                entry['sequence_number'],
                entry['previous_hash'],
                entry['event_type'],
                entry['entry_data'],
                entry['entry_hash'],
                entry['signature'],
                entry['timestamp']
            ))

        conn.commit()
        conn.close()

        return new_db_path

    def verify_chain(self, db_path):
        conn = sqlite3.connect(db_path)
        rows = conn.execute(
            "SELECT sequence_number, previous_hash, entry_hash FROM audit_log ORDER BY sequence_number"
        ).fetchall()
        conn.close()

        for i in range(1, len(rows)):
            curr_prev_hash = rows[i][1]
            prev_curr_hash = rows[i - 1][2]

            if curr_prev_hash != prev_curr_hash:
                return False, i

        return True, None

    def test_export_import_verify(self):
        prev_hash = '0' * 64
        for i in range(1, 101):
            data = f'{{"event": "test_{i}", "value": {i}, "data": "some_content_{i}"}}'
            self.add_log_entry(i, prev_hash, data)

            conn = sqlite3.connect(self.db_path)
            cursor = conn.execute("SELECT entry_hash FROM audit_log WHERE sequence_number = ?", (i,))
            prev_hash = cursor.fetchone()[0]
            conn.close()

        export_path = tempfile.NamedTemporaryFile(suffix='.json', delete=False)
        export_file = export_path.name
        export_path.close()

        export_data = self.export_to_json(export_file)
        print(f"Экспортировано {export_data['metadata']['total_entries']} записей в {export_file}")

        new_db_path = self.import_from_json(export_file)
        print(f"Импортировано в новую БД: {new_db_path}")

        is_valid, broken_at = self.verify_chain(new_db_path)

        if is_valid:
            print("Экспорт/импорт успешен, цепочка хешей сохранена")
            print(f"   Файл экспорта: {export_file}")
            print(f"   Количество записей: {export_data['metadata']['total_entries']}")
        else:
            print("Цепочка хешей нарушена при импорте")
            print(f"   Ошибка на записи #{broken_at}")

        if os.path.exists(export_file):
            os.unlink(export_file)
        if os.path.exists(new_db_path):
            os.unlink(new_db_path)

        return is_valid


if __name__ == "__main__":
    test = TestExportImport()
    test.setup()
    test.test_export_import_verify()
    test.cleanup()