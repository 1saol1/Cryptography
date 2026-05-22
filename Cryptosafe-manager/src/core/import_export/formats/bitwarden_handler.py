import json
import uuid
from typing import List, Dict, Any
from datetime import datetime
import csv
import io

class BitwardenHandler:

    @staticmethod
    def serialize(entries: List[Dict[str, Any]]) -> str:

        bitwarden_export = {
            "encrypted": False,
            "folders": [],
            "items": [],
            "collections": []
        }

        for entry in entries:
            bitwarden_item = {
                "id": entry.get("id", ""),
                "organizationId": None,
                "folderId": None,
                "type": 1,
                "name": entry.get("title", ""),
                "notes": entry.get("notes", ""),
                "favorite": False,
                "login": {
                    "username": entry.get("username", ""),
                    "password": entry.get("password", ""),
                    "totp": entry.get("totp_secret", ""),
                    "uris": []
                },
                "collectionIds": None,
                "revisionDate": entry.get("updated_at", datetime.utcnow().isoformat())
            }

            if entry.get("url"):
                bitwarden_item["login"]["uris"] = [
                    {
                        "match": None,
                        "uri": entry.get("url", "")
                    }
                ]

            custom_fields = []
            for key, value in entry.items():
                if key not in ['id', 'title', 'username', 'password', 'url', 'notes',
                               'totp_secret', 'created_at', 'updated_at', 'version',
                               'category', 'tags', 'share_metadata']:
                    custom_fields.append({
                        "name": key,
                        "value": str(value),
                        "type": 0
                    })

            if custom_fields:
                bitwarden_item["fields"] = custom_fields

            bitwarden_export["items"].append(bitwarden_item)

        return json.dumps(bitwarden_export, indent=2, default=str)

    @staticmethod
    def deserialize(content: str) -> List[Dict[str, Any]]:

        try:
            data = json.loads(content)
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid Bitwarden JSON: {e}")

        entries = []

        items = data.get("items", [])

        for item in items:
            entry = {
                "title": item.get("name", ""),
                "notes": item.get("notes", ""),
                "created_at": item.get("creationDate", datetime.utcnow().isoformat()),
                "updated_at": item.get("revisionDate", datetime.utcnow().isoformat())
            }

            login = item.get("login", {})
            if login:
                entry["username"] = login.get("username", "")
                entry["password"] = login.get("password", "")
                entry["totp_secret"] = login.get("totp", "")

                uris = login.get("uris", [])
                if uris and len(uris) > 0:
                    entry["url"] = uris[0].get("uri", "")

            fields = item.get("fields", [])
            for field in fields:
                field_name = field.get("name", "")
                field_value = field.get("value", "")
                if field_name and field_name not in entry:
                    entry[field_name] = field_value

            if not entry.get("id"):
                import uuid
                entry["id"] = str(uuid.uuid4())

            entries.append(entry)

        return entries


class LastPassHandler:

    @staticmethod
    def serialize(entries: List[Dict[str, Any]]) -> str:
        """Экспорт в LastPass CSV формат."""
        output = io.StringIO()
        # LastPass ожидает именно такой порядок колонок
        writer = csv.DictWriter(
            output,
            fieldnames=["name", "url", "username", "password", "extra", "grouping", "fav"],
            quoting=csv.QUOTE_ALL,
            lineterminator="\n"
        )
        writer.writeheader()
        for entry in entries:
            writer.writerow({
                "name": entry.get("title", ""),
                "url": entry.get("url", ""),
                "username": entry.get("username", ""),
                "password": entry.get("password", ""),
                "extra": entry.get("notes", ""),
                "grouping": entry.get("category", ""),
                "fav": "1" if entry.get("favorite") else "0"
            })
        return output.getvalue()

    @staticmethod
    def deserialize(content: str) -> List[Dict[str, Any]]:

        entries = []
        reader = csv.DictReader(io.StringIO(content))

        for row in reader:
            entry = {
                "title": row.get("name", row.get("hostname", "")),
                "url": row.get("url", ""),
                "username": row.get("username", ""),
                "password": row.get("password", ""),
                "notes": row.get("extra", ""),
                "category": row.get("grouping", "Imported"),
                "id": str(uuid.uuid4()),
                "created_at": datetime.utcnow().isoformat(),
                "updated_at": datetime.utcnow().isoformat()
            }

            entries.append(entry)

        return entries