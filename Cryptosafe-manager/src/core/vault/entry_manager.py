import uuid
import json
import re
from datetime import datetime
from typing import List, Dict, Any

from .encryption_service import EncryptionService
from .password_generator import PasswordGenerator

try:
    from fuzzywuzzy import fuzz

    FUZZY_AVAILABLE = True
except ImportError:
    FUZZY_AVAILABLE = False
    print("Для нечеткого поиска установите: pip install fuzzywuzzy python-Levenshtein")


class EntryManager:
    def __init__(self, db_connection, key_manager, auth_service=None, event_system=None):
        self.db = db_connection
        self.key_manager = key_manager
        self.auth_service = auth_service
        self.event_system = event_system

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
        if not query or not query.strip():
            return self.get_all_entries()

        query = query.strip()

        filters = self._parse_search_query(query)

        all_entries = self.get_all_entries()

        results = []
        for entry in all_entries:
            if self._matches_filters(entry, filters):
                results.append(entry)

        return results

    def _parse_search_query(self, query: str) -> dict:
        result = {
            'global': '',
            'title': '',
            'username': '',
            'url': '',
            'notes': ''
        }

        pattern = r'(\w+):"([^"]*)"|(\w+):(\S+)|([^"\s]+)'

        matches = re.findall(pattern, query)

        for match in matches:
            if match[0] and match[1]:
                field, value = match[0], match[1].lower()
                if field in result:
                    result[field] = value
            elif match[2] and match[3]:
                field, value = match[2], match[3].lower()
                if field in result:
                    result[field] = value
            elif match[4]:
                word = match[4].lower()
                if result['global']:
                    result['global'] += ' ' + word
                else:
                    result['global'] = word

        result['global'] = result['global'].strip()

        return result

    def _fuzzy_match(self, text: str, search: str, threshold: int = 80) -> bool:
        if not search:
            return True
        if not text:
            return False

        text = text.lower()
        search = search.lower()

        if search in text:
            return True

        if FUZZY_AVAILABLE:
            ratio = fuzz.partial_ratio(text, search)
            return ratio >= threshold

        return False

    def _matches_filters(self, entry: dict, filters: dict) -> bool:
        if filters['title']:
            title = entry.get('title', '')
            if not self._fuzzy_match(title, filters['title']):
                return False

        if filters['username']:
            username = entry.get('username', '')
            if not self._fuzzy_match(username, filters['username']):
                return False

        if filters['url']:
            url = entry.get('url', '')
            if not self._fuzzy_match(url, filters['url']):
                return False

        if filters['notes']:
            notes = entry.get('notes', '')
            if not self._fuzzy_match(notes, filters['notes']):
                return False

        if filters['global']:
            all_text = ' '.join([
                entry.get('title', ''),
                entry.get('username', ''),
                entry.get('url', ''),
                entry.get('notes', '')
            ])

            if not self._fuzzy_match(all_text, filters['global']):
                return False

        return True

    def generate_password(self) -> str:
        return self.generator.generate()

    def generate_with_settings(self, length=16, use_uppercase=True, use_lowercase=True,
                               use_digits=True, use_special=True, exclude_ambiguous=True) -> str:
        return self.generator.generate(
            length=length,
            use_uppercase=use_uppercase,
            use_lowercase=use_lowercase,
            use_digits=use_digits,
            use_special=use_special,
            exclude_ambiguous=exclude_ambiguous
        )

    def generate_pin(self, length: int = 6) -> str:
        return self.generator.generate_pin(length)

    def check_password_strength(self, password: str) -> dict:
        return self.generator.check_strength(password)

    def is_session_active(self) -> bool:
        return self.key_manager.get_cached_key() is not None