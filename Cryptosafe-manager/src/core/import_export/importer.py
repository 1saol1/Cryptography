"""Vault importer with validation and sanitization."""

from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime
import json
import logging
import os
import re
import hashlib
import tempfile
import shutil
import signal
import threading
from contextlib import contextmanager

from src.core.import_export.encryption import ExportDecryptionService
from src.core.import_export.formats.json_handler import JSONHandler
from src.core.import_export.formats.csv_handler import CSVHandler
from src.core.import_export.formats.bitwarden_handler import BitwardenHandler, LastPassHandler

logger = logging.getLogger(__name__)


class ImportMode:
    MERGE = "merge"
    REPLACE = "replace"
    DRY_RUN = "dry_run"


class TimeoutError(Exception):
    """IMP-4: Превышен тайм-аут операции импорта."""
    pass


class VaultImporter:

    SUPPORTED_FORMATS = {
        "encrypted_json": "Native CryptoSafe encrypted JSON format",
        "csv": "CSV format (multiple dialects)",
        "bitwarden_json": "Bitwarden JSON format",
        "lastpass_csv": "LastPass CSV format"
    }

    FIELD_CONSTRAINTS = {
        'title': {'max_length': 255, 'required': True, 'type': str},
        'username': {'max_length': 255, 'required': False, 'type': str},
        'password': {'max_length': 4096, 'required': False, 'type': str},
        'url': {'max_length': 2048, 'required': False, 'type': str},
        'notes': {'max_length': 10000, 'required': False, 'type': str},
        'category': {'max_length': 100, 'required': False, 'type': str},
    }

    MALICIOUS_PATTERNS = [
        (r'<script[^>]*>.*?</script>', '', re.IGNORECASE | re.DOTALL),
        (r'javascript:[^\s\'"]+', '', re.IGNORECASE),
        (r'on\w+\s*=\s*["\'][^"\']*["\']', '', re.IGNORECASE),
        (r'<\s*iframe[^>]*>.*?</iframe>', '', re.IGNORECASE | re.DOTALL),
        (r'<\s*object[^>]*>.*?</object>', '', re.IGNORECASE | re.DOTALL),
        (r'<\s*embed[^>]*>', '', re.IGNORECASE),
        (r'eval\s*\(', '', re.IGNORECASE),
        (r'document\.(write|cookie|location)', '', re.IGNORECASE),
        (r'window\.(alert|confirm|prompt)', '', re.IGNORECASE),
        (r'&\#\d+;', '', re.IGNORECASE),
        (r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]', '', re.IGNORECASE),
    ]

    # IMP-4: Конфигурация безопасности
    MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB
    IMPORT_TIMEOUT_SECONDS = 30  # 30 seconds
    SANDBOX_TEMP_PREFIX = "cryptosafe_import_"

    def __init__(self, entry_manager, key_manager, audit_logger=None):
        self.entry_manager = entry_manager
        self.key_manager = key_manager
        self.audit_logger = audit_logger

        # IMP-4: Для отслеживания временных файлов sandbox
        self._sandbox_files = []

    # ==================== IMP-4: ТАЙМ-АУТ ОПЕРАЦИЙ ====================

    @contextmanager
    def _timeout(self, seconds: int):
        """
        IMP-4: Контекстный менеджер для ограничения времени выполнения.

        Args:
            seconds: Максимальное время выполнения в секундах

        Raises:
            TimeoutError: Если операция превысила время
        """
        def timeout_handler(signum, frame):
            raise TimeoutError(f"Operation exceeded {seconds} second timeout")

        # Сохраняем старый обработчик
        old_handler = signal.signal(signal.SIGALRM, timeout_handler)
        signal.alarm(seconds)

        try:
            yield
        finally:
            # Отключаем таймер и восстанавливаем обработчик
            signal.alarm(0)
            signal.signal(signal.SIGALRM, old_handler)

    def _run_with_timeout(self, func, *args, **kwargs):
        """
        IMP-4: Запуск функции с ограничением по времени.

        Args:
            func: Функция для выполнения
            *args, **kwargs: Аргументы функции

        Returns:
            Результат функции

        Raises:
            TimeoutError: Если функция не завершилась за отведённое время
        """
        result = []
        error = []

        def wrapper():
            try:
                result.append(func(*args, **kwargs))
            except Exception as e:
                error.append(e)

        thread = threading.Thread(target=wrapper)
        thread.daemon = True
        thread.start()
        thread.join(timeout=self.IMPORT_TIMEOUT_SECONDS)

        if thread.is_alive():
            raise TimeoutError(f"Import operation exceeded {self.IMPORT_TIMEOUT_SECONDS} seconds")

        if error:
            raise error[0]

        return result[0] if result else None

    # ==================== IMP-4: ИЗОЛИРОВАННАЯ СРЕДА (SANDBOX) ====================

    def _create_sandbox(self) -> str:
        """
        IMP-4: Создание изолированной временной директории.

        Returns:
            Путь к sandbox директории
        """
        sandbox_path = tempfile.mkdtemp(prefix=self.SANDBOX_TEMP_PREFIX)
        self._sandbox_files.append(sandbox_path)
        logger.debug(f"Created sandbox directory: {sandbox_path}")
        return sandbox_path

    def _cleanup_sandbox(self) -> None:
        """
        IMP-4: Очистка sandbox директории.

        Удаляет все временные файлы и директории, созданные при импорте.
        """
        for sandbox_path in self._sandbox_files:
            try:
                if os.path.exists(sandbox_path):
                    shutil.rmtree(sandbox_path)
                    logger.debug(f"Cleaned up sandbox: {sandbox_path}")
            except Exception as e:
                logger.warning(f"Failed to cleanup sandbox {sandbox_path}: {e}")

        self._sandbox_files.clear()

    def _copy_to_sandbox(self, file_path: str, sandbox_path: str) -> str:
        """
        IMP-4: Копирование файла в sandbox для безопасной обработки.

        Args:
            file_path: Оригинальный путь к файлу
            sandbox_path: Путь к sandbox директории

        Returns:
            Путь к файлу в sandbox
        """
        filename = os.path.basename(file_path)
        sandbox_file = os.path.join(sandbox_path, filename)
        shutil.copy2(file_path, sandbox_file)
        self._sandbox_files.append(sandbox_file)
        logger.debug(f"Copied file to sandbox: {sandbox_file}")
        return sandbox_file

    # ==================== IMP-4: ПРОВЕРКА РАЗМЕРА ФАЙЛА ====================

    def _check_file_size(self, file_path: str) -> None:
        """
        IMP-4: Проверка размера файла перед импортом.

        Args:
            file_path: Путь к файлу

        Raises:
            ValueError: Если файл превышает максимальный размер
        """
        file_size = os.path.getsize(file_path)

        if file_size == 0:
            raise ValueError("Import file is empty")

        if file_size > self.MAX_FILE_SIZE:
            raise ValueError(
                f"File size ({file_size / (1024*1024):.1f} MB) exceeds "
                f"maximum allowed size ({self.MAX_FILE_SIZE / (1024*1024)} MB)"
            )

        logger.debug(f"File size check passed: {file_size} bytes")

    # ==================== IMP-4: ПРОВЕРКА ШИФРОВАНИЯ ПЕРЕД ДЕШИФРОВАНИЕМ ====================

    def _validate_encryption_before_decrypt(self, file_path: str, password: str = None) -> Tuple[bool, str]:
        """
        IMP-4: Проверка шифрования перед попыткой дешифрования.

        Args:
            file_path: Путь к файлу
            password: Пароль для проверки

        Returns:
            Tuple of (is_valid, message)
        """
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read(4096)  # Читаем достаточно для анализа

        # Проверка JSON структуры
        if not content.strip().startswith('{'):
            return False, "File does not appear to be JSON format"

        try:
            data = json.loads(content)
        except json.JSONDecodeError:
            return False, "Invalid JSON format"

        # Проверка наличия признаков шифрования
        has_encryption_marker = (
            data.get('cryptosafe_export') or
            data.get('encryption') or
            data.get('data')  # Зашифрованные данные обычно в поле 'data'
        )

        if not has_encryption_marker:
            return True, "No encryption detected (plaintext file)"

        # Для зашифрованного файла проверяем наличие обязательных полей
        required_fields = ['data']
        for field in required_fields:
            if field not in data:
                return False, f"Encrypted file missing required field: {field}"

        # Проверка что пароль предоставлен
        if not password:
            return False, "Password required for encrypted file"

        # Проверка что пароль не пустой
        if len(password) < 1:
            return False, "Password cannot be empty"

        logger.info("IMP-4: Encryption validation passed, ready to decrypt")
        return True, "Encryption validation passed"

    # ==================== IMP-2: ПРОВЕРКА ЦЕЛОСТНОСТИ ====================

    def _verify_integrity(self, file_path: str, password: str = None) -> Tuple[bool, str]:
        file_size = os.path.getsize(file_path)

        if file_size == 0:
            return False, "File is empty"

        if file_path.endswith('.json') or file_path.endswith('.cryptosafe'):
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = json.load(f)

                if content.get('cryptosafe_export') or content.get('encryption'):
                    if not password:
                        return False, "Password required for encrypted file"

                    if 'data' not in content:
                        return False, "Invalid encrypted file: missing data field"

                    try:
                        decryption_service = ExportDecryptionService(password=password)
                        decryption_service.decrypt(content)
                    except Exception as e:
                        return False, f"Decryption failed: {e}"
            except json.JSONDecodeError:
                return False, "Invalid JSON format"
            except Exception as e:
                return False, f"File verification failed: {e}"

        return True, "Integrity check passed"

    # ==================== IMP-2: ПРОВЕРКА ТИПОВ ДАННЫХ ====================

    def _validate_field_type(self, value: Any, expected_type: type, field_name: str) -> Tuple[bool, str]:
        if value is None or value == '':
            return True, ""

        if expected_type == str:
            if not isinstance(value, str):
                try:
                    str(value)
                    return True, ""
                except:
                    return False, f"Field '{field_name}' must be a string"
        return True, ""

    def _validate_field_length(self, value: Any, max_length: int, field_name: str) -> Tuple[bool, str]:
        if value is None:
            return True, ""

        value_str = str(value)
        if len(value_str) > max_length:
            return False, f"Field '{field_name}' exceeds maximum length of {max_length} characters"

        return True, ""

    def _validate_required_fields(self, entry: Dict[str, Any]) -> Tuple[bool, str]:
        if not entry.get('title'):
            return False, "Entry missing required field: 'title'"
        return True, ""

    def _validate_url_format(self, url: str) -> bool:
        if not url:
            return True

        url_pattern = re.compile(
            r'^https?://'
            r'(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+[A-Z]{2,6}\.?|'
            r'localhost|'
            r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})'
            r'(?::\d+)?'
            r'(?:/?|[/?]\S+)$', re.IGNORECASE
        )
        return bool(url_pattern.match(url))

    def _validate_entry(self, entry: Dict[str, Any]) -> Tuple[bool, List[str]]:
        errors = []

        is_valid, error = self._validate_required_fields(entry)
        if not is_valid:
            errors.append(error)

        for field_name, constraints in self.FIELD_CONSTRAINTS.items():
            value = entry.get(field_name)

            if constraints.get('type'):
                is_valid, error = self._validate_field_type(value, constraints['type'], field_name)
                if not is_valid:
                    errors.append(error)

            if constraints.get('max_length') and value:
                is_valid, error = self._validate_field_length(value, constraints['max_length'], field_name)
                if not is_valid:
                    errors.append(error)

        if entry.get('url') and not self._validate_url_format(entry['url']):
            errors.append(f"Invalid URL format: {entry['url']}")

        return len(errors) == 0, errors

    # ==================== IMP-2: ОЧИСТКА ВРЕДОНОСНОГО КОНТЕНТА ====================

    def _sanitize_string(self, text: str) -> str:
        if not isinstance(text, str):
            text = str(text)

        for pattern, replacement, flags in self.MALICIOUS_PATTERNS:
            try:
                text = re.sub(pattern, replacement, text, flags=flags)
            except re.error:
                continue

        html_escape = {
            '&': '&amp;',
            '<': '&lt;',
            '>': '&gt;',
            '"': '&quot;',
            "'": '&#x27;',
        }

        for char, escape in html_escape.items():
            text = text.replace(char, escape)

        return text.strip()

    def _sanitize_entry(self, entry: Dict[str, Any]) -> Dict[str, Any]:
        sanitized = {}

        for key, value in entry.items():
            if isinstance(value, str):
                sanitized[key] = self._sanitize_string(value)
            elif isinstance(value, list):
                sanitized[key] = [
                    self._sanitize_string(item) if isinstance(item, str) else item
                    for item in value
                ]
            elif isinstance(value, dict):
                sanitized[key] = self._sanitize_entry(value)
            else:
                sanitized[key] = value

        return sanitized

    # ==================== IMP-2: ПРОВЕРКА ДУБЛИКАТОВ ====================

    def _check_duplicates(self, entries: List[Dict[str, Any]],
                          existing_entries: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        existing_by_title = {e.get('title', '').lower(): e for e in existing_entries}
        existing_by_username_url = {}
        for existing in existing_entries:
            key = f"{existing.get('username', '')}|{existing.get('url', '')}".lower()
            existing_by_username_url[key] = existing

        for entry in entries:
            title = entry.get('title', '').lower()
            username_url_key = f"{entry.get('username', '')}|{entry.get('url', '')}".lower()

            entry['_duplicate'] = False
            entry['_duplicate_type'] = None
            entry['_existing_entry'] = None

            if title in existing_by_title:
                entry['_duplicate'] = True
                entry['_duplicate_type'] = 'exact_title'
                entry['_existing_entry'] = existing_by_title[title]
            elif username_url_key in existing_by_username_url:
                entry['_duplicate'] = True
                entry['_duplicate_type'] = 'same_credentials'
                entry['_existing_entry'] = existing_by_username_url[username_url_key]

        return entries

    def _handle_duplicate(self, entry: Dict[str, Any],
                          existing_entry: Dict[str, Any],
                          on_duplicate: str) -> Optional[Dict[str, Any]]:
        if on_duplicate == 'skip':
            logger.info(f"Skipping duplicate entry: {entry.get('title')}")
            return None

        elif on_duplicate == 'overwrite':
            logger.info(f"Overwriting duplicate entry: {entry.get('title')}")
            entry['id'] = existing_entry.get('id')
            return entry

        elif on_duplicate == 'rename':
            new_title = f"{entry.get('title')} (импорт {datetime.now().strftime('%Y%m%d')})"
            entry['title'] = new_title
            logger.info(f"Renamed duplicate entry: {new_title}")
            return entry

        return entry

    # ==================== IMP-1: ПАРСИНГ ФОРМАТОВ ====================

    def _detect_format(self, file_path: str) -> str:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read(1024)

        if content.strip().startswith('{'):
            try:
                data = json.loads(content)
                if data.get('cryptosafe_export') or data.get('encryption'):
                    return "encrypted_json"
                if data.get('items') and isinstance(data.get('items'), list):
                    return "bitwarden_json"
            except:
                pass

        if ',' in content and ('title' in content.lower() or 'username' in content.lower()):
            return "csv"

        if 'url,username,password' in content.lower() or 'name,grouping' in content.lower():
            return "lastpass_csv"

        raise ValueError(f"Could not detect format for file: {file_path}")

    def _parse_encrypted_json(self, file_path: str, password: str) -> List[Dict[str, Any]]:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = json.load(f)

        decryption_service = ExportDecryptionService(password=password)

        try:
            decrypted_data = decryption_service.decrypt(content)

            if 'entries' in decrypted_data:
                entries = decrypted_data['entries']
            elif isinstance(decrypted_data, list):
                entries = decrypted_data
            else:
                entries = [decrypted_data]

            return entries
        finally:
            decryption_service = None

    def _parse_csv(self, file_path: str) -> List[Dict[str, Any]]:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()

        entries = CSVHandler.deserialize(content)

        field_mapping = {
            'title': ['title', 'name', 'entry_name', 'site'],
            'username': ['username', 'user', 'login', 'email'],
            'password': ['password', 'pass', 'pwd'],
            'url': ['url', 'website', 'link', 'uri'],
            'notes': ['notes', 'comment', 'description', 'extra']
        }

        for entry in entries:
            for std_field, possible_names in field_mapping.items():
                for name in possible_names:
                    if name in entry:
                        entry[std_field] = entry[name]
                        break

        return entries

    def _parse_bitwarden_json(self, file_path: str) -> List[Dict[str, Any]]:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        return BitwardenHandler.deserialize(content)

    def _parse_lastpass_csv(self, file_path: str) -> List[Dict[str, Any]]:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        return LastPassHandler.deserialize(content)

    # ==================== IMP-3: РЕЖИМЫ ИМПОРТА ====================

    def _import_entries_merge(self, entries: List[Dict[str, Any]],
                               on_duplicate: str) -> Dict[str, Any]:
        stats = {
            'total': len(entries),
            'created': 0,
            'updated': 0,
            'skipped': 0,
            'errors': 0,
            'validation_errors': []
        }

        for entry in entries:
            try:
                is_valid, errors = self._validate_entry(entry)
                if not is_valid:
                    stats['validation_errors'].extend(errors)
                    stats['skipped'] += 1
                    continue

                sanitized = self._sanitize_entry(entry)

                if sanitized.get('_duplicate') and sanitized.get('_existing_entry'):
                    result = self._handle_duplicate(
                        sanitized,
                        sanitized['_existing_entry'],
                        on_duplicate
                    )
                    if result is None:
                        stats['skipped'] += 1
                        continue
                    elif result.get('id') and result != sanitized:
                        sanitized = result
                        for meta_field in ['_duplicate', '_duplicate_type', '_existing_entry']:
                            sanitized.pop(meta_field, None)
                        self.entry_manager.update_entry(sanitized['id'], sanitized)
                        stats['updated'] += 1
                        continue

                for meta_field in ['_duplicate', '_duplicate_type', '_existing_entry']:
                    sanitized.pop(meta_field, None)

                self.entry_manager.create_entry(sanitized)
                stats['created'] += 1

            except Exception as e:
                logger.error(f"Failed to import entry: {e}")
                stats['errors'] += 1

        return stats

    def _import_entries_replace(self, entries: List[Dict[str, Any]]) -> Dict[str, Any]:
        stats = {
            'total': len(entries),
            'created': 0,
            'updated': 0,
            'skipped': 0,
            'errors': 0,
            'validation_errors': [],
            'deleted_count': 0
        }

        existing_entries = self.entry_manager.get_all_entries()
        for entry in existing_entries:
            try:
                self.entry_manager.delete_entry(entry.get('id'), soft_delete=False)
                stats['deleted_count'] += 1
            except Exception as e:
                logger.error(f"Failed to delete entry during replace: {e}")

        logger.info(f"Replace mode: deleted {stats['deleted_count']} existing entries")

        for entry in entries:
            try:
                is_valid, errors = self._validate_entry(entry)
                if not is_valid:
                    stats['validation_errors'].extend(errors)
                    stats['skipped'] += 1
                    continue

                sanitized = self._sanitize_entry(entry)

                for meta_field in ['_duplicate', '_duplicate_type', '_existing_entry']:
                    sanitized.pop(meta_field, None)

                self.entry_manager.create_entry(sanitized)
                stats['created'] += 1

            except Exception as e:
                logger.error(f"Failed to import entry: {e}")
                stats['errors'] += 1

        return stats

    def _import_entries_dry_run(self, entries: List[Dict[str, Any]]) -> Dict[str, Any]:
        stats = {
            'total': len(entries),
            'created': 0,
            'updated': 0,
            'skipped': 0,
            'errors': 0,
            'validation_errors': [],
            'entries': []
        }

        for entry in entries:
            preview_entry = entry.copy()

            is_valid, errors = self._validate_entry(entry)
            preview_entry['_valid'] = is_valid
            preview_entry['_validation_errors'] = errors

            if not is_valid:
                stats['validation_errors'].extend(errors)
                stats['skipped'] += 1

            if preview_entry.get('_duplicate'):
                preview_entry['_will_be'] = 'skipped_or_updated'
            else:
                preview_entry['_will_be'] = 'created'
                stats['created'] += 1

            clean_preview = {}
            for key, value in preview_entry.items():
                if not key.startswith('_'):
                    clean_preview[key] = value
            clean_preview['_validation_status'] = 'valid' if is_valid else 'invalid'
            clean_preview['_validation_errors'] = errors
            clean_preview['_action'] = preview_entry['_will_be']

            stats['entries'].append(clean_preview)

        return stats

    def _import_entries(self, entries: List[Dict[str, Any]],
                        mode: str,
                        on_duplicate: str = 'skip') -> Dict[str, Any]:
        if mode == ImportMode.MERGE:
            return self._import_entries_merge(entries, on_duplicate)
        elif mode == ImportMode.REPLACE:
            return self._import_entries_replace(entries)
        elif mode == ImportMode.DRY_RUN:
            return self._import_entries_dry_run(entries)
        else:
            raise ValueError(f"Unknown import mode: {mode}")

    def _log_import_event(self, stats: Dict[str, Any], format: str,
                          mode: str, success: bool, error: str = None) -> None:
        if self.audit_logger:
            log_data = {
                'event_type': 'vault_import',
                'timestamp': datetime.utcnow().isoformat() + "Z",
                'total_entries': stats.get('total', 0),
                'created': stats.get('created', 0),
                'updated': stats.get('updated', 0),
                'skipped': stats.get('skipped', 0),
                'errors': stats.get('errors', 0),
                'validation_errors': len(stats.get('validation_errors', [])),
                'import_format': format,
                'import_mode': mode,
                'success': success
            }
            if error:
                log_data['error'] = error
            self.audit_logger.log(**log_data)

    # ==================== ОСНОВНОЙ МЕТОД С IMP-4 ====================

    def import_vault(
        self,
        file_path: str,
        password: Optional[str] = None,
        format: Optional[str] = None,
        mode: str = ImportMode.MERGE,
        on_duplicate: str = 'skip'
    ) -> Dict[str, Any]:
        """
        Import vault entries from file.

        IMP-4 Features:
        - Sandboxed environment for safe processing
        - File size limit (10MB default)
        - Encryption validation before decryption
        - 30 second timeout

        Args:
            file_path: Path to import file
            password: Password for encrypted imports
            format: Import format (auto-detected if None)
            mode: Import mode (merge, replace, dry_run)
            on_duplicate: How to handle duplicates ('skip', 'overwrite', 'rename')
        """
        sandbox_path = None

        try:
            # IMP-4: Проверка аутентификации
            if self.key_manager.get_cached_key() is None:
                raise ValueError("User must be authenticated to import vault")

            # IMP-4: Проверка существования файла
            if not os.path.exists(file_path):
                raise FileNotFoundError(f"File not found: {file_path}")

            # IMP-4: Проверка размера файла
            self._check_file_size(file_path)

            # IMP-4: Проверка шифрования перед дешифрованием
            is_valid, message = self._validate_encryption_before_decrypt(file_path, password)
            if not is_valid:
                raise ValueError(f"Encryption validation failed: {message}")

            # IMP-4: Создание sandbox (изолированная среда)
            sandbox_path = self._create_sandbox()
            sandbox_file = self._copy_to_sandbox(file_path, sandbox_path)

            # IMP-4: Автоопределение формата (с тайм-аутом)
            if format is None:
                format = self._run_with_timeout(self._detect_format, sandbox_file)

            if format not in self.SUPPORTED_FORMATS:
                raise ValueError(f"Unsupported format: {format}")

            # IMP-4: Парсинг с тайм-аутом
            if format == "encrypted_json":
                if not password:
                    raise ValueError("Password required for encrypted JSON import")
                entries = self._run_with_timeout(
                    self._parse_encrypted_json, sandbox_file, password
                )
            elif format == "csv":
                entries = self._run_with_timeout(self._parse_csv, sandbox_file)
            elif format == "bitwarden_json":
                entries = self._run_with_timeout(self._parse_bitwarden_json, sandbox_file)
            elif format == "lastpass_csv":
                entries = self._run_with_timeout(self._parse_lastpass_csv, sandbox_file)
            else:
                raise ValueError(f"Unsupported format: {format}")

            # Проверка дубликатов (только для merge режима)
            if mode == ImportMode.MERGE:
                existing_entries = self.entry_manager.get_all_entries()
                entries = self._check_duplicates(entries, existing_entries)

            # IMP-4: Импорт с тайм-аутом
            stats = self._run_with_timeout(
                self._import_entries, entries, mode, on_duplicate
            )

            # Логирование успеха
            self._log_import_event(stats, format, mode, True)

            if mode == ImportMode.DRY_RUN:
                logger.info(f"DRY RUN: Would import {stats['created']} entries, "
                           f"{stats['skipped']} would be skipped")
            else:
                logger.info(f"Import completed: {stats['created']} created, "
                           f"{stats['updated']} updated, {stats['skipped']} skipped")

            return stats

        except TimeoutError as e:
            self._log_import_event({}, format or 'unknown', mode, False, str(e))
            logger.error(f"Import timeout: {e}")
            raise

        except Exception as e:
            self._log_import_event({}, format or 'unknown', mode, False, str(e))
            raise

        finally:
            # IMP-4: Очистка sandbox (всегда выполняется)
            self._cleanup_sandbox()

    def get_supported_formats(self) -> Dict[str, str]:
        return self.SUPPORTED_FORMATS.copy()

    def preview_import(self, file_path: str, password: str = None,
                       format: str = None) -> Dict[str, Any]:
        return self.import_vault(
            file_path=file_path,
            password=password,
            format=format,
            mode=ImportMode.DRY_RUN
        )