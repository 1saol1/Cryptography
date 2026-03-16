import unittest
import os
import tempfile
import sqlite3
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from src.core.crypto.authentication import AuthenticationService
from src.core.state_manager import StateManager


class TestPasswordChange(unittest.TestCase):

    def setUp(self):
        self.temp_file = tempfile.NamedTemporaryFile(delete=False)
        self.db_path = self.temp_file.name
        self.temp_file.close()

        self._create_tables()

        self.auth = AuthenticationService(self.db_path)
        self.state = StateManager()

        self.old_pass = "OldPassword123!"
        self.new_pass = "NewPassword456!"

    def _create_tables(self):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS key_store (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                key_type TEXT NOT NULL,
                key_data BLOB NOT NULL,
                version INTEGER NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS vault_entries (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                username TEXT,
                encrypted_password BLOB NOT NULL,
                url TEXT,
                notes TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)

        conn.commit()
        conn.close()

    def _add_10_entries(self):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        for i in range(1, 11):
            cursor.execute("""
                INSERT INTO vault_entries (title, username, encrypted_password, url)
                VALUES (?, ?, ?, ?)
            """, (
                f"Запись {i}",
                f"user{i}",
                f"encrypted_data_{i}".encode(),
                f"https://site{i}.com"
            ))

        conn.commit()
        conn.close()

    def _count_entries(self):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM vault_entries")
        count = cursor.fetchone()[0]
        conn.close()
        return count


    def test_password_change_with_10_entries(self):
        ok, error = self.auth.register(self.old_pass)
        if not ok:
            self.fail(f"Registration failed: {error}")

        self._add_10_entries()
        self.assertEqual(self._count_entries(), 10, "Должно быть 10 записей")

        ok, error = self.auth.change_password(self.old_pass, self.new_pass)
        if not ok:
            self.fail(f"Password change failed: {error}")

        key = self.auth.login(self.new_pass)
        if key is None:
            self.fail("Cannot login with new password")

        self.assertEqual(self._count_entries(), 10, "Записи пропали после смены пароля")

        key = self.auth.login(self.old_pass)
        if key is not None:
            self.fail("Old password still works!")

    def test_wrong_old_password(self):
        ok, error = self.auth.register(self.old_pass)
        if not ok:
            self.fail("Registration failed")

        ok, error = self.auth.change_password("wrong_password", self.new_pass)
        if ok:
            self.fail("Password changed with wrong old password!")

    def test_weak_new_password(self):
        ok, error = self.auth.register(self.old_pass)
        if not ok:
            self.fail("Registration failed")

        ok, error = self.auth.change_password(self.old_pass, "123")
        if ok:
            self.fail("Weak password was accepted!")


if __name__ == "__main__":
    unittest.main()