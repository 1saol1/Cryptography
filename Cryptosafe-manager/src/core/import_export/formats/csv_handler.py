import csv
import io
from typing import List, Dict, Any
import json

from src.core.import_export.encryption import ExportEncryptionService


class CSVHandler:

    STANDARD_FIELDS = ['title', 'username', 'password', 'url', 'notes']

    @staticmethod
    def serialize(entries: List[Dict[str, Any]], include_header: bool = True) -> str:

        output = io.StringIO()

        fieldnames = CSVHandler.STANDARD_FIELDS.copy()

        for entry in entries:
            for key in entry.keys():
                if key not in fieldnames and key not in ['id', 'created_at', 'updated_at', 'version']:
                    fieldnames.append(key)

        writer = csv.DictWriter(output, fieldnames=fieldnames, quoting=csv.QUOTE_ALL)

        if include_header:
            writer.writeheader()

        for entry in entries:
            row = {field: entry.get(field, '') for field in fieldnames}
            for key, value in row.items():
                if isinstance(value, (list, dict)):
                    row[key] = json.dumps(value)
            writer.writerow(row)

        return output.getvalue()

    @staticmethod
    def deserialize(content: str) -> List[Dict[str, Any]]:

        entries = []
        reader = csv.DictReader(io.StringIO(content))

        for row in reader:
            entry = {}
            for key, value in row.items():

                if value and value.startswith('[') or value.startswith('{'):
                    try:
                        entry[key] = json.loads(value)
                        continue
                    except:
                        pass
                entry[key] = value
            entries.append(entry)

        return entries

    @staticmethod
    def encrypt_csv(csv_content: str, password: str) -> Dict[str, Any]:

        enc_service = ExportEncryptionService(password=password)
        try:
            encrypted = enc_service.encrypt(csv_content.encode('utf-8'))
            return encrypted
        finally:
            enc_service.clear_sensitive_data()