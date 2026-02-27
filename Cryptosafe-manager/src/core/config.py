import os
import sqlite3


class ConfigManager:

    def __init__(self, db_path: str):
        self.db_path = db_path
        self._ensure_settings_table()

    def _get_connection(self):
        return sqlite3.connect(self.db_path)

    def _ensure_settings_table(self):
        with self._get_connection() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS settings (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    setting_key TEXT UNIQUE,
                    setting_value TEXT,
                    encrypted INTEGER DEFAULT 0
                )
            """)

    def set(self, key: str, value: str, encrypted: bool = False):
        with self._get_connection() as conn:
            conn.execute("""
                INSERT OR REPLACE INTO settings
                (setting_key, setting_value, encrypted)
                VALUES (?, ?, ?)
            """, (key, value, int(encrypted)))

    def get(self, key: str, default=None):
        with self._get_connection() as conn:
            cur = conn.execute("""
                SELECT setting_value FROM settings
                WHERE setting_key = ?
            """, (key,))
            row = cur.fetchone()
            return row[0] if row else default
