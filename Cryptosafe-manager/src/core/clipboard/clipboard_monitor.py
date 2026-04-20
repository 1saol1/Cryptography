import threading
import time
from typing import Optional
from datetime import datetime
import json
import ctypes
from ctypes import wintypes


class ClipboardMonitor:
    def __init__(self, clipboard_service, event_bus, config_manager):
        self.clipboard = clipboard_service
        self.events = event_bus
        self.config = config_manager

        self._monitoring = False
        self._monitor_thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._start_error = None

        self._last_known_content: Optional[str] = None
        self._last_check_time: Optional[datetime] = None

        self._load_settings()

        self._suspicious_count = 0
        self._protection_mode = False

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

    def _is_app_whitelisted(self, process_name: str = None) -> bool:
        try:
            whitelist_json = self.config.get('clipboard_whitelist', '[]')
            whitelist = json.loads(whitelist_json)

            if not whitelist:
                return False

            if process_name is None:
                try:
                    user32 = ctypes.windll.user32
                    psapi = ctypes.windll.psapi
                    kernel32 = ctypes.windll.kernel32

                    hwnd = user32.GetForegroundWindow()
                    if not hwnd:
                        return False

                    pid = wintypes.DWORD()
                    user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))

                    handle = kernel32.OpenProcess(0x0400 | 0x0010, False, pid.value)
                    if handle:
                        exe_path = ctypes.create_unicode_buffer(260)
                        psapi.GetModuleFileNameExW(handle, None, exe_path, 260)
                        kernel32.CloseHandle(handle)
                        process_name = exe_path.value.lower()
                    else:
                        return False

                except Exception as e:
                    print(f"Ошибка определения процесса: {e}")
                    return False

            if not process_name:
                return False

            for whitelisted_path in whitelist:
                whitelisted_lower = whitelisted_path.lower()
                if whitelisted_lower in process_name or process_name in whitelisted_lower:
                    print(f"Приложение '{process_name}' в белом списке, пропускаем")
                    return True

            return False

        except Exception as e:
            print(f"Ошибка проверки белого списка: {e}")
            return False

    def start_monitoring(self):
        if not self.monitor_enabled:
            print("Мониторинг отключен в настройках")
            self._notify_monitoring_disabled()
            return False

        if self._monitoring:
            print("Мониторинг уже запущен")
            return True

        try:
            if not self.clipboard.platform_adapter._available:
                raise RuntimeError("Платформенный адаптер не доступен")

            test_content = self.clipboard.platform_adapter.get_clipboard_content()

            self._monitoring = True
            self._protection_mode = False
            self._stop_event.clear()
            self._monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
            self._monitor_thread.start()

            print("Мониторинг буфера обмена запущен")
            self._start_error = None
            return True

        except Exception as e:
            error_msg = str(e)
            print(f"Ошибка: Не удалось запустить мониторинг - {error_msg}")
            self._start_error = error_msg
            self._monitoring = False

            self.events.publish("ClipboardMonitoringFailed", {
                'reason': error_msg,
                'timestamp': datetime.utcnow().isoformat()
            })

            self._notify_monitoring_failed(error_msg)
            return False

    def _notify_monitoring_disabled(self):
        self.events.publish("ClipboardMonitoringDisabled", {
            'reason': 'disabled_in_settings',
            'timestamp': datetime.utcnow().isoformat()
        })

    def _notify_monitoring_failed(self, error_msg: str):
        self.events.publish("ClipboardMonitoringFailed", {
            'reason': error_msg,
            'timestamp': datetime.utcnow().isoformat()
        })

    def stop_monitoring(self):
        if not self._monitoring:
            return

        self._stop_event.set()
        self._monitoring = False

        if self._monitor_thread:
            self._monitor_thread.join(timeout=2)
        print("Мониторинг буфера обмена остановлен")

    def _monitor_loop(self):
        while not self._stop_event.is_set():
            try:
                self._check_clipboard()
            except Exception as e:
                print(f"Ошибка при проверке: {e}")
            time.sleep(self.check_interval)

    def _check_clipboard(self):
        try:
            current_content = self.clipboard.platform_adapter.get_clipboard_content()
        except Exception as e:
            print(f"Ошибка получения содержимого буфера: {e}")
            return

        try:
            if self.clipboard.is_clipboard_active():
                our_data = self.clipboard.get_current_data_preview(reveal=True)

                if our_data and current_content and current_content != our_data:
                    self._on_external_change(current_content)

            if self._last_known_content is not None:
                if current_content != self._last_known_content:
                    our_data = self.clipboard.get_current_data_preview(reveal=True)
                    if our_data and current_content == our_data:
                        print("Наше собственное копирование, игнорируем")
                    else:
                        self._on_clipboard_read()

            self._last_known_content = current_content
            self._last_check_time = datetime.utcnow()
        except Exception as e:
            print(f"Ошибка в цикле мониторинга: {e}")

    def _on_external_change(self, new_content: str):
        if self._is_app_whitelisted():
            print("Приложение из белого списка - внешнее изменение игнорируется")
            return

        print("Обнаружено внешнее изменение буфера обмена")

        self._suspicious_count += 1

        current_timeout = self.clipboard.timeout_seconds
        if current_timeout > 10:
            accelerated_timeout = max(5, current_timeout // 2)
            self.clipboard.set_timeout(accelerated_timeout)
            print(f"Ускорена очистка: {current_timeout} - {accelerated_timeout} сек")

        self.events.publish("ClipboardSuspiciousAccess", {
            'type': 'external_change',
            'suspicious_count': self._suspicious_count,
            'timestamp': datetime.utcnow().isoformat()
        })

        if self._suspicious_count >= self.suspicious_threshold:
            self._enable_protection_mode()

    def _on_clipboard_read(self):
        if self._is_app_whitelisted():
            print("Приложение из белого списка - чтение игнорируется")
            return

        print("Обнаружено чтение буфера обмена")

        self._suspicious_count += 1

        self.clipboard.clear_clipboard(manual=False)

        if self.clipboard.timeout_seconds > 5:
            self.clipboard.set_timeout(5)
            print("Таймаут уменьшен до 5 секунд")

        self.events.publish("ClipboardSuspiciousAccess", {
            'type': 'read_detected',
            'suspicious_count': self._suspicious_count,
            'timestamp': datetime.utcnow().isoformat()
        })

        if self._suspicious_count >= self.suspicious_threshold:
            self._enable_protection_mode()

    def _enable_protection_mode(self):
        if self._protection_mode:
            return

        print("Режим защиты активирован")

        self._protection_mode = True

        self.clipboard.clear_clipboard(manual=False)

        self.clipboard.set_timeout(5)

        self.events.publish("ClipboardProtectionEnabled", {
            'reason': 'suspicious_activity',
            'suspicious_count': self._suspicious_count,
            'timestamp': datetime.utcnow().isoformat(),
            'block_future_copies': True
        })

        self.events.publish("ClipboardCopyBlocked", {
            'reason': 'protection_mode_active',
            'suspicious_count': self._suspicious_count,
            'timestamp': datetime.utcnow().isoformat()
        })

    def is_protection_mode(self) -> bool:
        return self._protection_mode

    def reset_suspicious_counter(self):
        self._suspicious_count = 0
        self._protection_mode = False
        print("Счетчик подозрительной активности сброшен")
        print("Режим защиты деактивирован")

    def is_monitoring(self) -> bool:
        return self._monitoring

    def get_start_error(self) -> Optional[str]:
        return self._start_error

    def get_stats(self) -> dict:
        return {
            'monitoring_active': self._monitoring,
            'monitor_enabled': self.monitor_enabled,
            'protection_mode': self._protection_mode,
            'suspicious_count': self._suspicious_count,
            'check_interval': self.check_interval,
            'suspicious_threshold': self.suspicious_threshold,
            'start_error': self._start_error
        }