from datetime import datetime
from src.core.events import ENTRY_ADDED, ENTRY_UPDATED, ENTRY_DELETED


class AuditLogger:
    """
    Заглушка журнала аудита (Sprint 1).
    """

    def __init__(self, event_bus):
        self.event_bus = event_bus
        self._subscribe()

    def _subscribe(self):
        self.event_bus.subscribe(ENTRY_ADDED, self.log)
        self.event_bus.subscribe(ENTRY_UPDATED, self.log)
        self.event_bus.subscribe(ENTRY_DELETED, self.log)

    def log(self, data):
        """
        В Sprint 1 просто выводим в консоль.
        """
        print(f"[AUDIT] {datetime.utcnow()} — event: {data}")
