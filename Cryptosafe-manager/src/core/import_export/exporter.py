from typing import List, Dict, Any, Optional
from datetime import datetime
import json
import hashlib
import logging
import tempfile
import os

from src.core.import_export.encryption import ExportEncryptionService
from src.core.import_export.formats.json_handler import JSONHandler
from src.core.import_export.formats.csv_handler import CSVHandler
from src.core.import_export.formats.bitwarden_handler import BitwardenHandler

logger = logging.getLogger(__name__)


class VaultExporter:
    SUPPORTED_FORMATS = {
        "encrypted_json": "Native encrypted JSON format with full metadata",
        "csv": "CSV format (plaintext, good for migration)",
        "bitwarden_json": "Bitwarden/LastPass compatible JSON format"
    }

    def __init__(self, entry_manager, key_manager, auth_service=None, audit_logger=None):
        self.entry_manager = entry_manager
        self.key_manager = key_manager
        self.auth_service = auth_service
        self.audit_logger = audit_logger
        self._temp_files = []

    def _confirm_master_password(self, password: str) -> bool:
        if self.key_manager.get_cached_key() is None:
            raise ValueError("User must be authenticated to export vault")

        if self.auth_service:
            if not self.auth_service.verify_password(password):
                raise ValueError("Master password confirmation failed")

        return True

    def _create_temp_file(self, data: bytes, suffix: str = '.tmp') -> str:
        fd, temp_path = tempfile.mkstemp(suffix=suffix, prefix='cryptosafe_export_')
        with os.fdopen(fd, 'wb') as f:
            f.write(data)
        self._temp_files.append(temp_path)
        return temp_path

    def _cleanup_temp_files(self) -> None:
        for temp_path in self._temp_files:
            try:
                if os.path.exists(temp_path):
                    file_size = os.path.getsize(temp_path)
                    with open(temp_path, 'wb') as f:
                        f.write(os.urandom(file_size))
                    os.remove(temp_path)
            except Exception as e:
                logger.warning(f"Failed to delete temp file: {e}")
        self._temp_files.clear()

    def _log_export_event(self, entry_count: int, format: str,
                          export_mode: str, success: bool,
                          error_message: str = None) -> None:

        if self.audit_logger:
            log_data = {
                'event_type': 'vault_export',
                'timestamp': datetime.utcnow().isoformat() + "Z",
                'entry_count': entry_count,
                'export_format': format,
                'export_mode': export_mode,
                'success': success,
            }
            if error_message:
                log_data['error'] = error_message
            self.audit_logger.log(**log_data)
        else:
            logger.info(f"AUDIT: Export {entry_count} entries, format={format}, success={success}")

    def _get_entries_for_export(self, entry_ids: Optional[List[str]] = None) -> List[Dict[str, Any]]:
        if entry_ids is None:
            return self.entry_manager.get_all_entries()
        else:
            entries = []
            for entry_id in entry_ids:
                entry = self.entry_manager.get_entry(entry_id)
                entries.append(entry)
            return entries

    def _apply_field_filtering(self, entries: List[Dict[str, Any]],
                               options: Dict[str, Any]) -> List[Dict[str, Any]]:
        include_fields = options.get('include_fields')
        exclude_fields = options.get('exclude_fields', [])

        if not include_fields and not exclude_fields:
            return entries

        filtered_entries = []
        for entry in entries:
            filtered_entry = entry.copy()
            if include_fields:
                filtered_entry = {}
                for field in include_fields:
                    if field in entry:
                        filtered_entry[field] = entry[field]
                if 'id' in entry:
                    filtered_entry['id'] = entry['id']
            elif exclude_fields:
                for field in exclude_fields:
                    if field in filtered_entry:
                        del filtered_entry[field]
            filtered_entries.append(filtered_entry)
        return filtered_entries

    def _prepare_export_data(self, entries: List[Dict[str, Any]],
                             options: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        if options is None:
            options = {}

        filtered_entries = self._apply_field_filtering(entries, options)

        export_data = {
            "version": "1.0",
            "exported_at": datetime.utcnow().isoformat() + "Z",
            "entry_count": len(filtered_entries),
            "entries": filtered_entries,
            "export_type": "vault_export",
            "key_separation": True,
        }

        export_data["export_options_used"] = {
            "include_fields": options.get('include_fields'),
            "exclude_fields": options.get('exclude_fields'),
            "compression": options.get('compression'),
            "encryption_strength": options.get('encryption_strength', 256)
        }

        if options.get('compression') == 'gzip':
            import gzip
            import base64

            json_str = json.dumps(export_data, sort_keys=True, default=str)
            compressed = gzip.compress(json_str.encode('utf-8'))
            export_data['compressed'] = True
            export_data['compression_format'] = 'gzip'
            export_data['compressed_data'] = base64.b64encode(compressed).decode('ascii')
            del export_data['entries']

        return export_data

    def _get_total_entry_count(self) -> int:
        try:
            entries = self.entry_manager.get_all_entries()
            return len(entries)
        except Exception as e:
            logger.error(f"Failed to get total entry count: {e}")
            return 0

    def _export_as_encrypted_json(self, entries: List[Dict[str, Any]],
                                  password: str = None,
                                  public_key: bytes = None,
                                  options: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:

        export_data = self._prepare_export_data(entries, options)
        json_str = json.dumps(export_data, sort_keys=True, default=str)

        encryption_strength = options.get('encryption_strength', 256) if options else 256

        if password:
            enc_service = ExportEncryptionService(password=password)
            encrypted_package = enc_service.encrypt(json_str.encode('utf-8'))

            if 'encryption' in encrypted_package:
                encrypted_package['encryption']['key_size'] = encryption_strength
                encrypted_package['encryption']['key_purpose'] = 'export'

            enc_service.clear_sensitive_data()

        elif public_key:
            enc_service = ExportEncryptionService(public_key=public_key)
            encrypted_package = enc_service.encrypt(json_str.encode('utf-8'))
            enc_service.clear_sensitive_data()
        else:
            raise ValueError("Password or public key required for encryption")

        data_hash = hashlib.sha256(json_str.encode('utf-8')).hexdigest()
        encrypted_package["integrity"] = {
            "hash": data_hash,
            "hash_algorithm": "SHA256"
        }

        return encrypted_package

    def _export_as_csv(self, entries: List[Dict[str, Any]],
                       encrypt: bool = False,
                       password: str = None,
                       options: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:

        filtered_entries = self._apply_field_filtering(entries, options or {})
        csv_content = CSVHandler.serialize(filtered_entries)

        if encrypt:
            if not password:
                raise ValueError("Password required for encrypted CSV export")

            encryption_strength = options.get('encryption_strength', 256) if options else 256

            enc_service = ExportEncryptionService(password=password)
            try:
                encrypted = enc_service.encrypt(csv_content.encode('utf-8'))
                return {
                    "format": "csv_encrypted",
                    "data": encrypted.get('data'),
                    "encryption": encrypted.get('encryption'),
                    "encryption_strength": encryption_strength
                }
            finally:
                enc_service.clear_sensitive_data()  # EXP-4: Очистка ключа из памяти
        else:
            return {
                "format": "csv_plaintext",
                "data": csv_content,
                "note": "Plaintext CSV - not encrypted, suitable for migration"
            }

    def _export_as_bitwarden_json(self, entries: List[Dict[str, Any]],
                                  options: Optional[Dict[str, Any]] = None) -> str:
        filtered_entries = self._apply_field_filtering(entries, options or {})
        return BitwardenHandler.serialize(filtered_entries)

    def export_vault(
            self,
            entry_ids: Optional[List[str]] = None,
            password: Optional[str] = None,
            public_key: Optional[bytes] = None,
            format: str = "encrypted_json",
            options: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:

        if password:
            self._confirm_master_password(password)
        else:
            if self.key_manager.get_cached_key() is None:
                raise ValueError("User must be authenticated to export vault")

        if format not in self.SUPPORTED_FORMATS:
            raise ValueError(f"Unsupported format: {format}")

        entries = self._get_entries_for_export(entry_ids)

        if not entries:
            self._log_export_event(0, format, 'full' if entry_ids is None else 'selective', True)
            return {
                "version": "1.0",
                "exported_at": datetime.utcnow().isoformat() + "Z",
                "entry_count": 0,
                "entries": []
            }

        if options is None:
            options = {}

        encryption_strength = options.get('encryption_strength', 256)
        export_mode = 'full' if entry_ids is None else 'selective'

        try:
            if format == "encrypted_json":
                if not password and not public_key:
                    raise ValueError("encrypted_json format requires password or public_key")

                result = self._export_as_encrypted_json(entries, password, public_key, options)
                result["format"] = "encrypted_json"
                result["entry_count"] = len(entries)
                result["encryption_strength"] = encryption_strength

            elif format == "csv":
                encrypt = options.get('encrypt', False)
                result = self._export_as_csv(entries, encrypt, password, options)
                result["entry_count"] = len(entries)

            elif format == "bitwarden_json":
                result = self._export_as_bitwarden_json(entries, options)
                result = {
                    "format": "bitwarden_json",
                    "data": result,
                    "entry_count": len(entries)
                }

            result["metadata"] = {
                "source": "CryptoSafe Manager",
                "version": "1.0",
                "timestamp": datetime.utcnow().isoformat(),
                "export_mode": export_mode,
                "entry_count": len(entries),
                "total_entries_in_vault": self._get_total_entry_count(),
                "format": format
            }

            self._log_export_event(len(entries), format, export_mode, True)

            logger.info(f"Export completed: {len(entries)} entries, format: {format}, "
                        f"mode: {export_mode}")

            return result

        except Exception as e:
            self._log_export_event(0, format, export_mode, False, str(e))
            raise

        finally:
            self._cleanup_temp_files()

    def get_supported_formats(self) -> Dict[str, str]:
        return self.SUPPORTED_FORMATS.copy()