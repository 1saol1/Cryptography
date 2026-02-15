from collections import defaultdict
from typing import Callable, Dict, List, Any


class EventBus:
    """
    Простой publish/subscribe event bus.
    """

    def __init__(self):
        self._subscribers: Dict[str, List[Callable]] = defaultdict(list)

    def subscribe(self, event_type: str, handler: Callable):
        """
        Подписка обработчика на событие.
        """
        self._subscribers[event_type].append(handler)

    def publish(self, event_type: str, data: Any = None):
        """
        Публикация события.
        """
        for handler in self._subscribers.get(event_type, []):
            handler(data)

ENTRY_ADDED = "EntryAdded"
ENTRY_UPDATED = "EntryUpdated"
ENTRY_DELETED = "EntryDeleted"

USER_LOGGED_IN = "UserLoggedIn"
USER_LOGGED_OUT = "UserLoggedOut"

CLIPBOARD_COPIED = "ClipboardCopied"
CLIPBOARD_CLEARED = "ClipboardCleared"