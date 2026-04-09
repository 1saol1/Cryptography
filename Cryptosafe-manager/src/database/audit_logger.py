from datetime import datetime
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
                f"[AUDIT] {datetime.utcnow()} — БУФЕР: заблокировано копирование пароля из записи {entry_id} (запрещено настройками)")
        elif reason == 'vault_locked':
            print(f"[AUDIT] {datetime.utcnow()} — БУФЕР: заблокировано копирование (хранилище заблокировано)")
        elif reason == 'session_inactive':
            print(f"[AUDIT] {datetime.utcnow()} — БУФЕР: заблокировано копирование (сессия не активна)")
        elif reason == 'empty_data':
            print(f"[AUDIT] {datetime.utcnow()} — БУФЕР: заблокировано копирование (пустые данные)")
        else:
            print(f"[AUDIT] {datetime.utcnow()} — БУФЕР: заблокировано копирование (причина: {reason})")

    def log(self, data):
        print(f"[AUDIT] {datetime.utcnow()} — {data}")