from datetime import datetime
import traceback
from src.core.events import (
    ENTRY_ADDED, ENTRY_UPDATED, ENTRY_DELETED,
    CLIPBOARD_COPIED, CLIPBOARD_CLEARED,
    CLIPBOARD_SUSPICIOUS_ACCESS, CLIPBOARD_PROTECTION_ENABLED
)


class AuditLogger:

    def __init__(self, event_bus):
        self.event_bus = event_bus
        self._subscribe()

    def _subscribe(self):
        self.event_bus.subscribe(ENTRY_ADDED, self.log_entry_added)
        self.event_bus.subscribe(ENTRY_UPDATED, self.log_entry_updated)
        self.event_bus.subscribe(ENTRY_DELETED, self.log_entry_deleted)

        self.event_bus.subscribe(CLIPBOARD_COPIED, self.log_clipboard_copied)
        self.event_bus.subscribe(CLIPBOARD_CLEARED, self.log_clipboard_cleared)
        self.event_bus.subscribe(CLIPBOARD_SUSPICIOUS_ACCESS, self.log_suspicious_access)
        self.event_bus.subscribe(CLIPBOARD_PROTECTION_ENABLED, self.log_protection_enabled)

        self.event_bus.subscribe("ClipboardCopyBlocked", self.log_copy_blocked)
        self.event_bus.subscribe("ClipboardClearFailed", self.log_clear_failed)
        self.event_bus.subscribe("ClipboardMonitoringFailed", self.log_monitoring_failed)
        self.event_bus.subscribe("ClipboardMonitoringDisabled", self.log_monitoring_disabled)

    def log_entry_added(self, data):
        print(
            f"[AUDIT] {datetime.utcnow()} — ЗАПИСЬ ДОБАВЛЕНА: {data.get('title', 'без названия')} (ID: {data.get('entry_id')})")

    def log_entry_updated(self, data):
        print(f"[AUDIT] {datetime.utcnow()} — ЗАПИСЬ ОБНОВЛЕНА: ID: {data.get('entry_id')}")

    def log_entry_deleted(self, data):
        print(
            f"[AUDIT] {datetime.utcnow()} — ЗАПИСЬ УДАЛЕНА: ID: {data.get('entry_id')}, soft_delete: {data.get('soft_delete')}")

    def log_clipboard_copied(self, data):
        entry_id = data.get('source_entry_id')
        data_type = data.get('data_type', 'текст')
        timeout = data.get('timeout', 30)

        if entry_id:
            print(
                f"[AUDIT] {datetime.utcnow()} — БУФЕР: скопирован {data_type} из записи {entry_id} (очистится через {timeout} сек)")
        else:
            print(f"[AUDIT] {datetime.utcnow()} — БУФЕР: скопирован {data_type} (очистится через {timeout} сек)")

    def log_clipboard_cleared(self, data):
        reason = data.get('reason', 'programmatic')

        if reason == 'timeout':
            print(f"[AUDIT] {datetime.utcnow()} — БУФЕР: автоматическая очистка по таймауту")
        elif reason == 'manual':
            print(f"[AUDIT] {datetime.utcnow()} — БУФЕР: ручная очистка пользователем")
        elif reason == 'lock':
            print(f"[AUDIT] {datetime.utcnow()} — БУФЕР: очистка при блокировке хранилища")
        elif reason == 'shutdown':
            print(f"[AUDIT] {datetime.utcnow()} — БУФЕР: очистка при завершении приложения")
        else:
            print(f"[AUDIT] {datetime.utcnow()} — БУФЕР: очистка (причина: {reason})")

    def log_suspicious_access(self, data):
        access_type = data.get('type', 'unknown')
        process = data.get('process')
        suspicious_count = data.get('suspicious_count', 0)

        if process:
            print(
                f"[AUDIT] {datetime.utcnow()} — БЕЗОПАСНОСТЬ: подозрительный доступ ({access_type}) от процесса '{process}' (счётчик: {suspicious_count})")
        else:
            print(
                f"[AUDIT] {datetime.utcnow()} — БЕЗОПАСНОСТЬ: подозрительный доступ ({access_type}) (счётчик: {suspicious_count})")

    def log_protection_enabled(self, data):
        reason = data.get('reason', 'suspicious_activity')
        suspicious_count = data.get('suspicious_count', 0)

        print(
            f"[AUDIT] {datetime.utcnow()} — БЕЗОПАСНОСТЬ: ВКЛЮЧЕН РЕЖИМ ЗАЩИТЫ! Причина: {reason}, подозрений: {suspicious_count}")


    def log_copy_blocked(self, data):
        reason = data.get('reason', 'unknown')
        entry_id = data.get('entry_id')
        data_type = data.get('data_type', 'password')

        if reason == 'allow_copy_disabled':
            print(
                f"[AUDIT] {datetime.utcnow()} — ОШИБКА: заблокировано копирование {data_type} из записи {entry_id} (запрещено настройками)")
        elif reason == 'vault_locked':
            print(f"[AUDIT] {datetime.utcnow()} — ОШИБКА: заблокировано копирование (хранилище заблокировано)")
        elif reason == 'session_inactive':
            print(f"[AUDIT] {datetime.utcnow()} — ОШИБКА: заблокировано копирование (сессия не активна)")
        elif reason == 'empty_data':
            print(f"[AUDIT] {datetime.utcnow()} — ОШИБКА: заблокировано копирование (пустые данные)")
        else:
            print(f"[AUDIT] {datetime.utcnow()} — ОШИБКА: заблокировано копирование (причина: {reason})")

    def log_clear_failed(self, data):
        reason = data.get('reason', 'unknown')
        print(f"[AUDIT] {datetime.utcnow()} — ОШИБКА: не удалось очистить буфер обмена (причина: {reason})")
        print(f"[AUDIT] {datetime.utcnow()} — РЕКОМЕНДАЦИЯ: очистите буфер вручную (Ctrl+C пустой строки)")

    def log_monitoring_failed(self, data):
        reason = data.get('reason', 'unknown')
        print(f"[AUDIT] {datetime.utcnow()} — ОШИБКА: не удалось запустить мониторинг буфера (причина: {reason})")
        print(f"[AUDIT] {datetime.utcnow()} — СОСТОЯНИЕ: функции безопасности ограничены")

    def log_monitoring_disabled(self, data):
        reason = data.get('reason', 'disabled_in_settings')
        print(f"[AUDIT] {datetime.utcnow()} — СОСТОЯНИЕ: мониторинг буфера обмена отключен (причина: {reason})")

    def log_exception(self, error_type: str, error_msg: str, include_traceback: bool = False):
        print(f"[AUDIT] {datetime.utcnow()} — ИСКЛЮЧЕНИЕ: {error_type} - {error_msg}")

        if include_traceback:
            tb = traceback.format_exc()

            safe_tb = self._sanitize_traceback(tb)
            print(f"[AUDIT] {datetime.utcnow()} — TRACEBACK: {safe_tb[:500]}")

    def _sanitize_traceback(self, tb: str) -> str:
        lines = tb.split('\n')
        sanitized = []
        for line in lines:
            if 'password' in line.lower() or 'secret' in line.lower() or 'token' in line.lower():
                sanitized.append('[СОДЕРЖИТ ЧУВСТВИТЕЛЬНЫЕ ДАННЫЕ - СКРЫТО]')
            else:
                sanitized.append(line)
        return '\n'.join(sanitized)

    def log(self, data):
        print(f"[AUDIT] {datetime.utcnow()} — {data}")