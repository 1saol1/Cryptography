import threading
from datetime import datetime, timedelta
from typing import Optional, Callable

from src.core.clipboard.platform_adapter import get_platform_adapter, ClipboardAdapter
from src.core.clipboard.secure_item import SecureClipboardItem


class ClipboardService:
    def __init__(self, event_bus, state_manager, config_manager):
        self.events = event_bus
        self.state_manager = state_manager
        self.config = config_manager

        self.platform_adapter: ClipboardAdapter = get_platform_adapter()

        self._current_item: Optional[SecureClipboardItem] = None

        self._timer: Optional[threading.Timer] = None
        self._timer_lock = threading.RLock()

        self._load_settings()

        self.events.subscribe("UserLoggedOut", self._on_user_logged_out)
        self.events.subscribe("UserLoggedIn", self._on_user_logged_in)


    def _load_settings(self):
        try:
            timeout_str = self.config.get("clipboard_timeout", "30")
            self.timeout_seconds = int(timeout_str)

            if self.timeout_seconds != 0:
                self.timeout_seconds = max(5, min(300, self.timeout_seconds))

            self.security_level = self.config.get("clipboard_security_level", "standard")

        except Exception as e:
            print(f"Ошибка загрузки настроек: {e}")
            self.timeout_seconds = 30
            self.security_level = "standard"

    def _save_settings(self):
        try:
            self.config.set("clipboard_timeout", str(self.timeout_seconds))
            self.config.set("clipboard_security_level", self.security_level)
        except Exception as e:
            print(f"Ошибка сохранения настроек: {e}")

    def set_timeout(self, seconds: int):
        if seconds == 0:
            self.timeout_seconds = 0
            self._save_settings()
            return

        seconds = max(5, min(300, seconds))
        self.timeout_seconds = seconds
        self._save_settings()

    def set_security_level(self, level: str):
        if level == "standard":
            self.set_timeout(30)
        elif level == "secure":
            self.set_timeout(15)
        elif level == "paranoid":
            self.set_timeout(5)
        else:
            return

        self.security_level = level
        self._save_settings()

    def copy_to_clipboard(self, data: str, data_type: str = "text",
                          source_entry_id: Optional[str] = None,
                          show_notification: bool = True) -> bool:
        print(f"[CLIPBOARD] ===== НАЧАЛО КОПИРОВАНИЯ =====")

        print(f"[CLIPBOARD] copy_to_clipboard вызван: type={data_type}, data={data[:20]}...")

        if self.state_manager.is_locked or not self.state_manager.logged_in:
            print("[CLIPBOARD] ОШИБКА: хранилище заблокировано!")
            return False

        if not data:
            print("[CLIPBOARD] ОШИБКА: пустые данные!")
            return False

        with self._timer_lock:
            self._clear_clipboard_internal(reason="new_content")

            self._current_item = SecureClipboardItem(
                data=data,
                data_type=data_type,
                source_entry_id=source_entry_id
            )

            print(f"[CLIPBOARD] Копируем в системный буфер через адаптер...")
            success = self.platform_adapter.copy_to_clipboard(data)

            if not success:
                print("[CLIPBOARD] ОШИБКА: адаптер не смог скопировать!")
                self._current_item = None
                return False

            print(f"[CLIPBOARD] УСПЕШНО скопировано!")

            self._start_timer()

            self.events.publish("ClipboardCopied", {
                'data_type': data_type,
                'source_entry_id': source_entry_id,
                'timeout': self.timeout_seconds,
                'timestamp': datetime.utcnow().isoformat()
            })
            print(f"[CLIPBOARD] ===== КОПИРОВАНИЕ УСПЕШНО ЗАВЕРШЕНО =====")
            return True

    def _start_timer(self):
        if self.timeout_seconds == 0:
            print("Авто-очистка отключена")
            return

        if self._timer:
            self._timer.cancel()
            self._timer = None

        self._timer = threading.Timer(self.timeout_seconds, self._on_timeout)
        self._timer.daemon = True
        self._timer.start()

    def _on_timeout(self):
        with self._timer_lock:
            if self._current_item:
                self._clear_clipboard_internal(reason="timeout")
                self.events.publish("ClipboardCleared", {
                    'reason': 'timeout',
                    'timestamp': datetime.utcnow().isoformat()
                })

    def clear_clipboard(self, manual: bool = True) -> bool:
        with self._timer_lock:
            reason = "manual" if manual else "programmatic"
            return self._clear_clipboard_internal(reason)

    def _clear_clipboard_internal(self, reason: str) -> bool:
        if self._timer:
            self._timer.cancel()
            self._timer = None

        success = self.platform_adapter.clear_clipboard()

        if self._current_item:
            self._current_item.secure_wipe()
            self._current_item = None

        if reason != "new_content":
            self.events.publish("ClipboardCleared", {
                'reason': reason,
                'timestamp': datetime.utcnow().isoformat()
            })

        return success

    def _on_user_logged_out(self, data=None):
        with self._timer_lock:
            self._clear_clipboard_internal(reason="lock")

    def _on_user_logged_in(self, data=None):
        self.platform_adapter.clear_clipboard()

    def get_current_status(self) -> dict:
        with self._timer_lock:
            if not self._current_item:
                return {
                    'active': False,
                    'has_content': False,
                    'remaining_seconds': 0
                }

            if self.timeout_seconds == 0:
                return {
                    'active': True,
                    'has_content': True,
                    'data_type': self._current_item.data_type,
                    'source_entry_id': self._current_item.source_entry_id,
                    'remaining_seconds': -1,  # -1 означает "никогда не очистится"
                    'timeout_configured': 0,
                    'auto_clear_disabled': True
                }

            elapsed = (datetime.utcnow() - self._current_item.copied_at).total_seconds()
            remaining = max(0, self.timeout_seconds - elapsed)

            return {
                'active': True,
                'has_content': True,
                'data_type': self._current_item.data_type,
                'source_entry_id': self._current_item.source_entry_id,
                'remaining_seconds': int(remaining),
                'timeout_configured': self.timeout_seconds,
                'auto_clear_disabled': False
            }

    def get_current_data_preview(self, reveal: bool = False) -> Optional[str]:
        with self._timer_lock:
            if not self._current_item:
                return None

            data = self._current_item.get_data()

            if not reveal:
                if len(data) <= 4:
                    return "•" * len(data)
                else:
                    return data[:2] + "•" * (len(data) - 4) + data[-2:]

            if self.state_manager.is_locked or not self.state_manager.logged_in:
                return None

            return data

    def is_clipboard_active(self) -> bool:
        with self._timer_lock:
            return self._current_item is not None

    def get_remaining_time(self) -> int:
        status = self.get_current_status()
        return status.get('remaining_seconds', 0)

    def shutdown(self):
        with self._timer_lock:
            self._clear_clipboard_internal(reason="shutdown")