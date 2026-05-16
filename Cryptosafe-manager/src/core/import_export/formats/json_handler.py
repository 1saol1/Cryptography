"""JSON format handler for encrypted and plain JSON exports."""

from typing import Dict, Any


class JSONHandler:
    """Handles native encrypted JSON format."""

    @staticmethod
    def serialize(entries: list, metadata: Dict[str, Any]) -> str:
        """Serialize entries to JSON string."""
        raise NotImplementedError

    @staticmethod
    def deserialize(content: str) -> Dict[str, Any]:
        """Deserialize JSON content."""
        raise NotImplementedError