"""CSV format handler for plaintext exports/imports."""

from typing import List, Dict, Any


class CSVHandler:
    """Handles CSV format with multiple dialects."""

    @staticmethod
    def serialize(entries: List[Dict[str, Any]]) -> str:
        """Serialize entries to CSV string."""
        raise NotImplementedError

    @staticmethod
    def deserialize(content: str) -> List[Dict[str, Any]]:
        """Deserialize CSV content to entries."""
        raise NotImplementedError