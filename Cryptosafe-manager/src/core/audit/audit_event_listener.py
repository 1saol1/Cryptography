import logging
from typing import Any, Optional

from src.core.events import (
    EventBus,
    ENTRY_ADDED,
    ENTRY_UPDATED,
    ENTRY_DELETED,
    USER_LOGGED_IN,
    USER_LOGGED_OUT,
    CLIPBOARD_COPIED,
    CLIPBOARD_CLEARED,
    CLIPBOARD_SUSPICIOUS_ACCESS,
    CLIPBOARD_PROTECTION_ENABLED,
    USER_LOGIN_FAILED
)

logger = logging.getLogger(__name__)


class AuditEventListener:
    def __init__(self, event_bus: EventBus, audit_logger):
        self.event_bus = event_bus
        self.audit_logger = audit_logger
        self._current_user_id: Optional[str] = None
        self._register_handlers()

    def _register_handlers(self):

        self.event_bus.subscribe(ENTRY_ADDED, self._on_entry_added)
        self.event_bus.subscribe(ENTRY_UPDATED, self._on_entry_updated)
        self.event_bus.subscribe(ENTRY_DELETED, self._on_entry_deleted)

        self.event_bus.subscribe(USER_LOGGED_IN, self._on_user_logged_in)
        self.event_bus.subscribe(USER_LOGGED_OUT, self._on_user_logged_out)

        self.event_bus.subscribe(CLIPBOARD_COPIED, self._on_clipboard_copied)
        self.event_bus.subscribe(CLIPBOARD_CLEARED, self._on_clipboard_cleared)
        self.event_bus.subscribe(
            CLIPBOARD_SUSPICIOUS_ACCESS,
            self._on_clipboard_suspicious
        )
        self.event_bus.subscribe(
            CLIPBOARD_PROTECTION_ENABLED,
            self._on_clipboard_protection_enabled
        )
        self.event_bus.subscribe(USER_LOGIN_FAILED, self._on_user_login_failed)

        logger.info("AuditEventListener registered all handlers")

    def set_current_user(self, user_id: Optional[str]):
        self._current_user_id = user_id

    def _on_entry_added(self, data: Any):
        entry_id = self._extract_entry_id(data)

        self.audit_logger.log_event(
            event_type="VAULT_ENTRY_CREATE",
            severity="INFO",
            source="vault.entry_manager",
            details={
                "operation": "create",
                "entry_id": entry_id,
                "action": "entry_added"
            },
            user_id=self._current_user_id,
            entry_id=entry_id
        )
        logger.debug(f"Audit logged: entry added {entry_id}")

    def _on_entry_updated(self, data: Any):
        entry_id = self._extract_entry_id(data)

        self.audit_logger.log_event(
            event_type="VAULT_ENTRY_UPDATE",
            severity="INFO",
            source="vault.entry_manager",
            details={
                "operation": "update",
                "entry_id": entry_id,
                "action": "entry_updated"
            },
            user_id=self._current_user_id,
            entry_id=entry_id
        )
        logger.debug(f"Audit logged: entry updated {entry_id}")

    def _on_entry_deleted(self, data: Any):
        entry_id = self._extract_entry_id(data)

        self.audit_logger.log_event(
            event_type="VAULT_ENTRY_DELETE",
            severity="WARN",  # Deletion is warning level
            source="vault.entry_manager",
            details={
                "operation": "delete",
                "entry_id": entry_id,
                "action": "entry_deleted"
            },
            user_id=self._current_user_id,
            entry_id=entry_id
        )
        logger.debug(f"Audit logged: entry deleted {entry_id}")


    def _on_user_logged_in(self, data: Any):
        username = self._extract_username(data)
        self.set_current_user(username)

        self.audit_logger.log_event(
            event_type="AUTH_LOGIN_SUCCESS",
            severity="INFO",
            source="auth_service",
            details={
                "username": username,
                "result": "success"
            },
            user_id=username
        )
        logger.info(f"Audit logged: user {username} logged in")

    def _on_user_login_failed(self, data: Any):
        username = self._extract_username(data)

        self.audit_logger.log_event(
            event_type="AUTH_LOGIN_FAILURE",
            severity="WARN",
            source="auth_service",
            details={
                "username": username or "unknown",
                "result": "failure",
                "reason": "invalid_credentials"
            },
            user_id=username
        )
        logger.warning(f"Audit logged: failed login attempt for {username}")

    def _on_user_logged_out(self, data: Any):
        username = self._extract_username(data) or self._current_user_id

        self.audit_logger.log_event(
            event_type="AUTH_LOGOUT",
            severity="INFO",
            source="auth_service",
            details={
                "username": username,
                "action": "logout"
            },
            user_id=username
        )
        self.set_current_user(None)
        logger.info(f"Audit logged: user {username} logged out")

    def _on_clipboard_copied(self, data: Any):
        content_type = self._extract_clipboard_content_type(data)

        self.audit_logger.log_event(
            event_type="CLIPBOARD_COPY",
            severity="INFO",
            source="clipboard.service",
            details={
                "operation": "copy",
                "content_type": content_type,
                "action": "copied_to_clipboard"
            },
            user_id=self._current_user_id
        )
        logger.debug(f"Audit logged: clipboard copy ({content_type})")

    def _on_clipboard_cleared(self, data: Any):
        clear_type = "manual" if data is None else str(data)

        self.audit_logger.log_event(
            event_type="CLIPBOARD_CLEAR",
            severity="INFO",
            source="clipboard.monitor",
            details={
                "operation": "clear",
                "clear_type": clear_type,
                "action": "clipboard_cleared"
            },
            user_id=self._current_user_id
        )
        logger.debug(f"Audit logged: clipboard cleared ({clear_type})")

    def _on_clipboard_suspicious(self, data: Any):
        details = data if isinstance(data, dict) else {"info": str(data) if data else {}}

        self.audit_logger.log_event(
            event_type="SECURITY_SUSPICIOUS_ACTIVITY",
            severity="WARN",
            source="clipboard.monitor",
            details={
                "operation": "suspicious_access",
                "reason": details.get("reason", "unknown"),
                "action": "suspicious_clipboard_access"
            },
            user_id=self._current_user_id
        )
        logger.warning(f"Audit logged: suspicious clipboard access")

    def _on_clipboard_protection_enabled(self, data: Any):
        self.audit_logger.log_event(
            event_type="CONFIG_CHANGE",
            severity="INFO",
            source="clipboard.config",
            details={
                "setting": "clipboard_protection",
                "new_value": "enabled",
                "action": "config_changed"
            },
            user_id=self._current_user_id
        )
        logger.debug("Audit logged: clipboard protection enabled")


    def _extract_entry_id(self, data: Any) -> Optional[str]:
        if isinstance(data, dict):
            return data.get("entry_id") or data.get("id")
        elif hasattr(data, "id"):
            return str(data.id)
        elif isinstance(data, str):
            return data
        return None

    def _extract_username(self, data: Any) -> Optional[str]:
        if isinstance(data, dict):
            return data.get("username") or data.get("user")
        elif hasattr(data, "username"):
            return data.username
        elif isinstance(data, str):
            return data
        return None

    def _extract_clipboard_content_type(self, data: Any) -> str:
        if isinstance(data, dict):
            return data.get("content_type", "unknown")
        return "text" if data is not None else "unknown"