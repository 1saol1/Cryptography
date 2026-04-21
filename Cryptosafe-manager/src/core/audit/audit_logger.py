import json
import hashlib
import sqlite3
import threading
import os
from datetime import datetime, timezone
from typing import Dict, Any, Optional, List
from dataclasses import dataclass
from enum import Enum

import logging

logger = logging.getLogger(__name__)


class EventSeverity(Enum):
    INFO = "INFO"
    WARN = "WARN"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


class EventType(Enum):
    AUTH_LOGIN_SUCCESS = "AUTH_LOGIN_SUCCESS"
    AUTH_LOGIN_FAILURE = "AUTH_LOGIN_FAILURE"
    AUTH_LOGOUT = "AUTH_LOGOUT"
    AUTH_PASSWORD_CHANGE = "AUTH_PASSWORD_CHANGE"
    AUTH_PASSWORD_CHANGE_FAILURE = "AUTH_PASSWORD_CHANGE_FAILURE"

    VAULT_ENTRY_CREATE = "VAULT_ENTRY_CREATE"
    VAULT_ENTRY_READ = "VAULT_ENTRY_READ"
    VAULT_ENTRY_UPDATE = "VAULT_ENTRY_UPDATE"
    VAULT_ENTRY_DELETE = "VAULT_ENTRY_DELETE"
    VAULT_SEARCH = "VAULT_SEARCH"
    VAULT_UNLOCK = "VAULT_UNLOCK"
    VAULT_LOCK = "VAULT_LOCK"

    CLIPBOARD_COPY = "CLIPBOARD_COPY"
    CLIPBOARD_CLEAR = "CLIPBOARD_CLEAR"
    CLIPBOARD_AUTO_CLEAR = "CLIPBOARD_AUTO_CLEAR"

    SYSTEM_STARTUP = "SYSTEM_STARTUP"
    SYSTEM_SHUTDOWN = "SYSTEM_SHUTDOWN"
    SYSTEM_LOCK = "SYSTEM_LOCK"
    SYSTEM_UNLOCK = "SYSTEM_UNLOCK"
    SYSTEM_GENESIS = "SYSTEM_GENESIS"

    SECURITY_FAILED_ATTEMPT = "SECURITY_FAILED_ATTEMPT"
    SECURITY_SUSPICIOUS_ACTIVITY = "SECURITY_SUSPICIOUS_ACTIVITY"
    SECURITY_TAMPER_DETECTED = "SECURITY_TAMPER_DETECTED"

    CONFIG_CHANGE = "CONFIG_CHANGE"


@dataclass
class LogEntry:
    timestamp: str
    event_type: str
    severity: str
    user_id: str
    source: str
    details: Dict[str, Any]
    sequence_number: int
    previous_hash: str
    entry_id: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        result = {
            'timestamp': self.timestamp,
            'event_type': self.event_type,
            'severity': self.severity,
            'user_id': self.user_id,
            'source': self.source,
            'details': self.details,
            'sequence_number': self.sequence_number,
            'previous_hash': self.previous_hash
        }
        if self.entry_id:
            result['entry_id'] = self.entry_id
        return result


class AuditLogger:

    def __init__(self, db_connection: Optional[sqlite3.Connection], signer, config: Dict[str, Any]):
        self.external_connection = db_connection
        self.signer = signer
        self.config = config
        self._async_queue: List[LogEntry] = []
        self._lock = threading.Lock()

        if self.external_connection is None:
            base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            self.db_path = os.path.join(base_dir, "src", "database", "cryptosafe.db")
        else:
            self.db_path = None

        self._init_log_structure()

    def _get_connection(self):
        if self.external_connection is not None:
            return self.external_connection

        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _close_connection(self, conn):
        if self.external_connection is None and conn is not None:
            conn.close()

    def _init_log_structure(self):
        conn = self._get_connection()
        try:
            cursor = conn.execute("SELECT COUNT(*) FROM audit_log")
            count = cursor.fetchone()[0]

            if count == 0:
                self._create_genesis_entry()
                logger.info("Audit log initialized with genesis entry")
        finally:
            self._close_connection(conn)

    def _create_genesis_entry(self):
        genesis_entry = LogEntry(
            timestamp=datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z'),
            event_type=EventType.SYSTEM_GENESIS.value,
            severity=EventSeverity.INFO.value,
            user_id='system',
            source='audit_logger',
            details={'message': 'Audit log initialized'},
            sequence_number=0,
            previous_hash='0' * 64
        )
        self._write_entry(genesis_entry)

    def _get_next_sequence(self, conn) -> int:
        cursor = conn.execute("SELECT MAX(sequence_number) FROM audit_log")
        max_seq = cursor.fetchone()[0]
        return (max_seq or -1) + 1

    def _get_latest_hash(self, conn) -> str:
        cursor = conn.execute(
            "SELECT entry_hash FROM audit_log ORDER BY sequence_number DESC LIMIT 1"
        )
        row = cursor.fetchone()
        return row[0] if row else '0' * 64

    def _sanitize_details(self, details: Dict[str, Any]) -> Dict[str, Any]:
        if not details:
            return {}

        sensitive_keys = {'password', 'key', 'secret', 'token', 'pin',
                          'master_password', 'encryption_key', 'private_key'}

        sanitized = {}
        for key, value in details.items():
            if key.lower() in sensitive_keys or 'password' in key.lower():
                sanitized[key] = '[REDACTED]'
            elif isinstance(value, dict):
                sanitized[key] = self._sanitize_details(value)
            elif isinstance(value, list):
                sanitized[key] = ['[REDACTED]' if isinstance(v, str) and
                                                  any(sk in str(v).lower() for sk in sensitive_keys) else v
                                  for v in value]
            else:
                sanitized[key] = value
        return sanitized

    def log_event(
            self,
            event_type: str,
            severity: str,
            source: str,
            details: Dict[str, Any],
            user_id: Optional[str] = None,
            entry_id: Optional[str] = None
    ):
        conn = self._get_connection()
        try:
            previous_hash = self._get_latest_hash(conn)
            sequence_number = self._get_next_sequence(conn)
        finally:
            self._close_connection(conn)

        entry = LogEntry(
            timestamp=datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z'),
            event_type=event_type,
            severity=severity,
            user_id=user_id or 'anonymous',
            source=source,
            details=self._sanitize_details(details),
            sequence_number=sequence_number,
            previous_hash=previous_hash,
            entry_id=entry_id
        )

        if self.config.get('async_logging', True):
            self._async_log(entry)
        else:
            self._write_entry(entry)

    def _async_log(self, entry: LogEntry):
        with self._lock:
            self._async_queue.append(entry)
            # Если очередь большая, можно сразу записать
            if len(self._async_queue) > 10:
                self.flush_async_queue()

    def flush_async_queue(self):
        with self._lock:
            for entry in self._async_queue:
                self._write_entry(entry)
            self._async_queue.clear()

    def _write_entry(self, entry: LogEntry):
        conn = self._get_connection()
        try:
            entry_dict = entry.to_dict()
            entry_json = json.dumps(entry_dict, sort_keys=True, default=str)
            entry_hash = hashlib.sha256(entry_json.encode()).hexdigest()
            signature = self.signer.sign(entry_json.encode())
            entry_data_blob = entry_json.encode('utf-8')

            conn.execute(
                """
                INSERT INTO audit_log
                (sequence_number, previous_hash, event_type, entry_data, entry_hash, signature, timestamp)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    entry.sequence_number,
                    entry.previous_hash,
                    entry.event_type,
                    entry_data_blob,
                    entry_hash,
                    signature.hex(),
                    entry.timestamp
                )
            )
            conn.commit()
        except Exception as e:
            logger.error(f"Failed to write audit entry: {e}")
        finally:
            self._close_connection(conn)

    def get_entry_count(self) -> int:
        conn = self._get_connection()
        try:
            cursor = conn.execute("SELECT COUNT(*) FROM audit_log")
            return cursor.fetchone()[0]
        finally:
            self._close_connection(conn)