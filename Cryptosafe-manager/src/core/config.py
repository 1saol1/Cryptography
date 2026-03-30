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
            # Проверяем, есть ли таблица settings
            cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='settings'")
            table_exists = cursor.fetchone() is not None

            if not table_exists:
                # Создаём таблицу с правильной структурой
                conn.execute("""
                    CREATE TABLE settings (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        setting_key TEXT UNIQUE,
                        setting_value TEXT,
                        encrypted INTEGER DEFAULT 0
                    )
                """)
                print("[ConfigManager] Таблица settings создана")
            else:
                # Проверяем существующие колонки
                cursor = conn.execute("PRAGMA table_info(settings)")
                columns = [col[1] for col in cursor.fetchall()]
                print(f"[ConfigManager] Существующие колонки: {columns}")

                # Если нет setting_key, но есть name - переименовываем
                if 'setting_key' not in columns and 'name' in columns:
                    try:
                        conn.execute("ALTER TABLE settings RENAME COLUMN name TO setting_key")
                        print("[ConfigManager] Колонка name переименована в setting_key")
                    except Exception as e:
                        print(f"[ConfigManager] Ошибка переименования name: {e}")

                # Если нет setting_value, но есть value - переименовываем
                if 'setting_value' not in columns and 'value' in columns:
                    try:
                        conn.execute("ALTER TABLE settings RENAME COLUMN value TO setting_value")
                        print("[ConfigManager] Колонка value переименована в setting_value")
                    except Exception as e:
                        print(f"[ConfigManager] Ошибка переименования value: {e}")

                # Если нет setting_key и нет name - добавляем
                if 'setting_key' not in columns:
                    try:
                        conn.execute("ALTER TABLE settings ADD COLUMN setting_key TEXT")
                        print("[ConfigManager] Добавлена колонка setting_key")
                    except Exception as e:
                        print(f"[ConfigManager] Ошибка добавления setting_key: {e}")

                # Если нет setting_value - добавляем
                if 'setting_value' not in columns:
                    try:
                        conn.execute("ALTER TABLE settings ADD COLUMN setting_value TEXT")
                        print("[ConfigManager] Добавлена колонка setting_value")
                    except Exception as e:
                        print(f"[ConfigManager] Ошибка добавления setting_value: {e}")

                # Если нет encrypted - добавляем
                if 'encrypted' not in columns:
                    try:
                        conn.execute("ALTER TABLE settings ADD COLUMN encrypted INTEGER DEFAULT 0")
                        print("[ConfigManager] Добавлена колонка encrypted")
                    except Exception as e:
                        print(f"[ConfigManager] Ошибка добавления encrypted: {e}")

            conn.commit()

    def set(self, key: str, value: str, encrypted: bool = False):
        with self._get_connection() as conn:
            # Проверяем, какие колонки есть
            cursor = conn.execute("PRAGMA table_info(settings)")
            columns = [col[1] for col in cursor.fetchall()]

            if 'setting_key' in columns and 'setting_value' in columns:
                conn.execute("""
                    INSERT OR REPLACE INTO settings
                    (setting_key, setting_value, encrypted)
                    VALUES (?, ?, ?)
                """, (key, value, int(encrypted)))
            elif 'name' in columns and 'value' in columns:
                # Старая структура
                conn.execute("""
                    INSERT OR REPLACE INTO settings
                    (name, value)
                    VALUES (?, ?)
                """, (key, value))
            else:
                raise Exception("Неизвестная структура таблицы settings")

    def get(self, key: str, default=None):
        with self._get_connection() as conn:
            try:
                # Пробуем новую структуру
                cur = conn.execute("""
                    SELECT setting_value FROM settings
                    WHERE setting_key = ?
                """, (key,))
                row = cur.fetchone()
                if row:
                    return row[0]
            except:
                pass

            try:
                # Пробуем старую структуру
                cur = conn.execute("""
                    SELECT value FROM settings
                    WHERE name = ?
                """, (key,))
                row = cur.fetchone()
                if row:
                    return row[0]
            except:
                pass

            return default