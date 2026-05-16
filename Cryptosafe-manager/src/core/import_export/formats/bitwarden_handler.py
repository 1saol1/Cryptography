"""Bitwarden JSON format handler for compatibility."""

from typing import Dict, Any


class BitwardenHandler:
    """Handles Bitwarden JSON export/import format."""

    @staticmethod
    def serialize(entries: list) -> str:
        """Serialize entries to Bitwarden-compatible JSON."""
        raise NotImplementedError

    @staticmethod
    def deserialize(content: str) -> list:
        """Deserialize Bitwarden JSON to internal entry format."""
        raise NotImplementedError