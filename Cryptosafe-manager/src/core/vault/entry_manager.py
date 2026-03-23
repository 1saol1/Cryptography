import uuid
import json
from datetime import datetime
from typing import List, Dict, Any

from .encryption_service import EncryptionService
from .password_generator import PasswordGenerator


class EntryManager:
    def __init__(self, db_connection, key_manager, auth_service=None, event_system=None):
        self.db = db_connection
        self.key_manager = key_manager
        self.auth_service = auth_service
        self.event_system = event_system

        # Передаем key_manager в EncryptionService
        self.encryption = EncryptionService(key_manager)

        self.generator = PasswordGenerator()

    def _update_activity(self):
        if self.auth_service:
            self.auth_service.update_activity()
        elif hasattr(self.key_manager, 'update_activity'):
            self.key_manager.update_activity()

    def create_entry(self, data: Dict[str, Any]) -> str:
        self._update_activity()

        entry_id = str(uuid.uuid4())

        full_data = {
            'title': data.get('title', ''),
            'username': data.get('username', ''),
            'password': data.get('password', ''),
            'url': data.get('url', ''),
            'notes': data.get('notes', ''),
            'category': data.get('category', 'Общее'),

            'id': entry_id,
            'created_at': datetime.now().isoformat(),
            'updated_at': datetime.now().isoformat(),
            'version': 1
        }

        encrypted_blob = self.encryption.encrypt(full_data)

        tags = data.get('tags', [])
        if isinstance(tags, list):
            tags_json = json.dumps(tags)
        else:
            tags_json = '[]'

        try:
            self.db.execute(
                "INSERT INTO vault_entries (id, encrypted_data, created_at, updated_at, tags) VALUES (?, ?, ?, ?, ?)",
                (entry_id, encrypted_blob, datetime.now(), datetime.now(), tags_json)
            )

            if hasattr(self.db, 'commit'):
                self.db.commit()

            if self.event_system:
                self.event_system.publish('EntryCreated', {
                    'entry_id': entry_id,
                    'title': data.get('title')
                })

            return entry_id

        except Exception as e:
            print(f" Ошибка при создании записи: {e}")
            if hasattr(self.db, 'rollback'):
                self.db.rollback()
            raise

    def get_entry(self, entry_id: str) -> Dict[str, Any]:
        self._update_activity()

        cursor = self.db.execute(
            "SELECT encrypted_data FROM vault_entries WHERE id = ? AND deleted_at IS NULL",
            (entry_id,)
        )
        row = cursor.fetchone()

        if not row:
            raise ValueError("Запись не найдена")

        encrypted_blob = row[0]
        data = self.encryption.decrypt(encrypted_blob)

        return data

    def get_all_entries(self) -> List[Dict[str, Any]]:
        self._update_activity()

        cursor = self.db.execute(
            "SELECT id FROM vault_entries WHERE deleted_at IS NULL ORDER BY updated_at DESC"
        )
        rows = cursor.fetchall()

        entries = []
        for row in rows:
            try:
                entry = self.get_entry(row[0])
                entries.append(entry)
            except Exception as e:
                print(f"Ошибка при загрузке записи {row[0]}: {e}")

        return entries

    def update_entry(self, entry_id: str, new_data: Dict[str, Any]) -> Dict[str, Any]:
        self._update_activity()

        existing_data = self.get_entry(entry_id)

        updated_data = existing_data.copy()
        for key, value in new_data.items():
            if value is not None:
                updated_data[key] = value

        updated_data['updated_at'] = datetime.now().isoformat()

        encrypted_blob = self.encryption.encrypt(updated_data)

        try:
            self.db.execute(
                "UPDATE vault_entries SET encrypted_data = ?, updated_at = ? WHERE id = ?",
                (encrypted_blob, datetime.now(), entry_id)
            )

            if hasattr(self.db, 'commit'):
                self.db.commit()

            if self.event_system:
                self.event_system.publish('EntryUpdated', {
                    'entry_id': entry_id,
                    'title': updated_data.get('title')
                })

            print(f"Запись обновлена: {entry_id}")
            return updated_data

        except Exception as e:
            if hasattr(self.db, 'rollback'):
                self.db.rollback()
            raise

    def delete_entry(self, entry_id: str, soft_delete: bool = True):
        self._update_activity()

        try:
            if soft_delete:
                cursor = self.db.execute(
                    "SELECT encrypted_data FROM vault_entries WHERE id = ?",
                    (entry_id,)
                )
                row = cursor.fetchone()

                if row:
                    from datetime import timedelta
                    expires_at = datetime.now() + timedelta(days=30)

                    self.db.execute(
                        "INSERT INTO deleted_entries (original_id, encrypted_data, deleted_at, expires_at) VALUES (?, ?, ?, ?)",
                        (entry_id, row[0], datetime.now(), expires_at)
                    )

                    self.db.execute(
                        "UPDATE vault_entries SET deleted_at = ? WHERE id = ?",
                        (datetime.now(), entry_id)
                    )

                    print(f"Запись перемещена в корзину: {entry_id}")
            else:
                self.db.execute("DELETE FROM vault_entries WHERE id = ?", (entry_id,))
                print(f"Запись полностью удалена: {entry_id}")

            if hasattr(self.db, 'commit'):
                self.db.commit()

            if self.event_system:
                self.event_system.publish('EntryDeleted', {
                    'entry_id': entry_id,
                    'soft_delete': soft_delete
                })

        except Exception as e:
            if hasattr(self.db, 'rollback'):
                self.db.rollback()
            raise

    def search_entries(self, query: str) -> List[Dict[str, Any]]:
        all_entries = self.get_all_entries()

        if not query:
            return all_entries

        query = query.lower()
        results = []

        for entry in all_entries:
            if (query in entry.get('title', '').lower() or
                    query in entry.get('username', '').lower() or
                    query in entry.get('url', '').lower() or
                    query in entry.get('notes', '').lower()):
                results.append(entry)

        return results

    def generate_password(self) -> str:
        return self.generator.generate()

    def generate_pin(self, length: int = 6) -> str:
        return self.generator.generate_pin(length)

    def check_password_strength(self, password: str) -> dict:
        return self.generator.check_strength(password)

    def is_session_active(self) -> bool:
        return self.key_manager.get_cached_key() is not None