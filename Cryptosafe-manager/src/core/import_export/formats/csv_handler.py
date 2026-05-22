import csv
import io
from typing import List, Dict, Any, Optional
from datetime import datetime
import json

from src.core.import_export.encryption import ExportEncryptionService


class CSVHandler:

    STANDARD_FIELDS = ['title', 'username', 'password', 'url', 'notes']
    SKIP_FIELDS = ['id', 'created_at', 'updated_at', 'version', 'deleted_at']
    METADATA_PREFIX = '# CryptoSafe Export | '

    @staticmethod
    def serialize(entries: List[Dict[str, Any]],
                  include_header: bool = True,
                  metadata: Optional[Dict[str, Any]] = None) -> str:

        output = io.StringIO()

        if metadata is not None:
            meta = {
                "exported_at": datetime.utcnow().isoformat() + "Z",
                "entry_count": len(entries),
                "source": "CryptoSafe Manager",
                **metadata
            }
            output.write(CSVHandler.METADATA_PREFIX + json.dumps(meta) + "\n")

        fieldnames = CSVHandler.STANDARD_FIELDS.copy()
        for entry in entries:
            for key in entry.keys():
                if key not in fieldnames and key not in CSVHandler.SKIP_FIELDS:
                    fieldnames.append(key)

        writer = csv.DictWriter(
            output, fieldnames=fieldnames,
            quoting=csv.QUOTE_ALL,
            lineterminator='\n'
        )

        if include_header:
            writer.writeheader()

        for entry in entries:
            row = {field: entry.get(field, '') for field in fieldnames}
            for key, value in row.items():
                if isinstance(value, (list, dict)):
                    row[key] = json.dumps(value, ensure_ascii=False)
                elif value is None:
                    row[key] = ''
            writer.writerow(row)

        return output.getvalue()

    @staticmethod
    def deserialize(content: str) -> List[Dict[str, Any]]:
        lines = [line for line in content.splitlines()
                 if not line.startswith('#')]
        clean_content = '\n'.join(lines)

        entries = []
        reader = csv.DictReader(io.StringIO(clean_content))

        for row in reader:
            entry = {}
            for key, value in row.items():
                if not key:
                    continue

                if value and (value.startswith('[') or value.startswith('{')):
                    try:
                        entry[key] = json.loads(value)
                        continue
                    except (json.JSONDecodeError, ValueError):
                        pass
                entry[key] = value
            entries.append(entry)

        return entries

    @staticmethod
    def parse_metadata(content: str) -> Optional[Dict[str, Any]]:
        for line in content.splitlines():
            if line.startswith(CSVHandler.METADATA_PREFIX):
                try:
                    meta_json = line[len(CSVHandler.METADATA_PREFIX):]
                    return json.loads(meta_json)
                except (json.JSONDecodeError, ValueError):
                    pass
        return None

    @staticmethod
    def encrypt_csv(csv_content: str, password: str) -> Dict[str, Any]:
        enc_service = ExportEncryptionService(password=password)
        try:
            encrypted = enc_service.encrypt(csv_content.encode('utf-8'))
            return encrypted
        finally:
            enc_service.clear_sensitive_data()