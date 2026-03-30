import threading
import time
from typing import Optional
from datetime import datetime

class ClipboardMonitor:
    def __init__(self, clipboard_service, event_bus, config_manager):
        self.clipboard = clipboard_service
        self.events = event_bus
        self.config = config_manager

        self._monitoring = False
        self._monitor_thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()

        self._last_known_content: Optional[str] = None
        self._last_check_time: Optional[datetime] = None

        self._load_settings()

        self._suspicious_count = 0

    def _load_settings(self):
        try:
            monitor_enabled = self.config.get("clipboard_monitor_enabled", "true")
            self.monitor_enabled = monitor_enabled.lower() == "true"

            self.check_interval = int(self.config.get("clipboard_monitor_interval", "1"))
            self.suspicious_threshold = int(self.config.get("clipboard_suspicious_threshold", "3"))

        except Exception as e:
            print(f"Ошибка загрузки настроек: {e}")
            self.monitor_enabled = True
            self.check_interval = 1
            self.suspicious_threshold = 3

    def start_monitoring(self):
        if not self.monitor_enabled:
            print("Мониторинг отключен в настройках")
            return

        if self._monitoring:
            print("Мониторинг уже запущен")
            return

        self._monitoring = True
        self._stop_event.clear()
        self._monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self._monitor_thread.start()


    def stop_monitoring(self):
        if not self._monitoring:
            return

        self._stop_event.set()
        self._monitoring = False

        if self._monitor_thread:
            self._monitor_thread.join(timeout=2)


    def _monitor_loop(self):
        while not self._stop_event.is_set():
            try:
                self._check_clipboard()
            except Exception as e:
                print(f"Ошибка при проверке")
            time.sleep(self.check_interval)

    def _check_clipboard(self):
        current_content = self.clipboard.platform_adapter.get_clipboard_content()

        if self.clipboard.is_clipboard_active():
            current_service_data = self.clipboard.get_current_data_preview(reveal=False)

            if current_content and current_service_data:
                service_data_full = self.clipboard.get_current_data_preview(reveal=True)

                if service_data_full and current_content != service_data_full:
                    self._on_external_change(current_content)

        if self._last_known_content is not None:
            if current_content != self._last_known_content:
                self._on_clipboard_read()

        self._last_known_content = current_content
        self._last_check_time = datetime.utcnow()

    def _on_external_change(self, new_content: str):

        current_timeout = self.clipboard.timeout_seconds
        accelerated_timeout = max(1, current_timeout // 2)

        self.clipboard._start_timer()

        self._suspicious_count += 1

        self.events.publish("ClipboardSuspiciousAccess", {
            'type': 'external_change',
            'suspicious_count': self._suspicious_count,
            'timestamp': datetime.utcnow().isoformat()
        })

        if self._suspicious_count >= self.suspicious_threshold:
            self._enable_protection_mode()

    def _on_clipboard_read(self):

        self._suspicious_count += 1

        self.events.publish("ClipboardSuspiciousAccess", {
            'type': 'read_detected',
            'suspicious_count': self._suspicious_count,
            'timestamp': datetime.utcnow().isoformat()
        })

        if self._suspicious_count >= self.suspicious_threshold:
            self._enable_protection_mode()

    def _enable_protection_mode(self):

        self.clipboard.clear_clipboard(manual=False)

        self.clipboard.set_timeout(5)

        self.events.publish("ClipboardProtectionEnabled", {
            'reason': 'suspicious_activity',
            'suspicious_count': self._suspicious_count,
            'timestamp': datetime.utcnow().isoformat()
        })

    def reset_suspicious_counter(self):
        self._suspicious_count = 0

    def is_monitoring(self) -> bool:
        return self._monitoring

    def get_stats(self) -> dict:
        return {
            'monitoring_active': self._monitoring,
            'monitor_enabled': self.monitor_enabled,
            'suspicious_count': self._suspicious_count,
            'check_interval': self.check_interval,
            'suspicious_threshold': self.suspicious_threshold
        }