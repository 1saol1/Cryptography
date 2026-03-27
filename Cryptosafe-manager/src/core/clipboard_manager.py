import time
import threading
from PyQt6.QtCore import QObject, pyqtSignal


class ClipboardManager(QObject):
    clipboard_copied = pyqtSignal(str)
    clipboard_cleared = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._timer = None
        self._clear_timeout = 30
        self._last_copied = None

    def set_clear_timeout(self, seconds: int):
        self._clear_timeout = seconds

    def copy_to_clipboard(self, text: str, auto_clear: bool = True):
        if not text:
            return

        print(f"[CLIPBOARD] Копирование (заглушка): {text[:20]}...")

        self._last_copied = text

        self.clipboard_copied.emit(text[:50])

        if auto_clear:
            self._schedule_clear()

    def _schedule_clear(self):
        print(f"[CLIPBOARD] Запланирована очистка через {self._clear_timeout} сек (заглушка)")

        def delayed_clear():
            time.sleep(self._clear_timeout)
            self.clear_clipboard()

        thread = threading.Thread(target=delayed_clear, daemon=True)
        thread.start()

    def clear_clipboard(self):
        print(f"[CLIPBOARD] Очистка буфера (заглушка)")
        self._last_copied = None
        self.clipboard_cleared.emit()

    def get_last_copied(self) -> str:
        return self._last_copied