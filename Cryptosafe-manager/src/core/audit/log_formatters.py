from typing import Dict, Any, List


class LogFormatter:
    @staticmethod
    def to_json(entries: List[Dict[str, Any]]) -> str:
        return "[]"

    @staticmethod
    def to_csv(entries: List[Dict[str, Any]]) -> str:
        return ""

    @staticmethod
    def to_pdf(entries: List[Dict[str, Any]], output_path: str):
        pass