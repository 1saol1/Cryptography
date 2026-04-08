from enum import Enum


class SecurityLevel(Enum):
    STANDARD = "standard"
    SECURE = "secure"
    PARANOID = "paranoid"


class ClipboardSettings:
    KEY_TIMEOUT = "clipboard_clear_timeout"
    KEY_SECURITY_LEVEL = "clipboard_security_level"
    KEY_MONITOR_ENABLED = "clipboard_monitor_enabled"
    KEY_MONITOR_INTERVAL = "clipboard_monitor_interval"
    KEY_SUSPICIOUS_THRESHOLD = "clipboard_suspicious_threshold"
    KEY_NOTIFICATIONS_ENABLED = "clipboard_notifications_enabled"
    KEY_WARN_BEFORE_CLEAR = "clipboard_warn_before_clear"
    KEY_WHITELIST = "clipboard_whitelist"

    DEFAULT_TIMEOUT = 30
    DEFAULT_SECURITY_LEVEL = SecurityLevel.STANDARD.value
    DEFAULT_MONITOR_ENABLED = True
    DEFAULT_MONITOR_INTERVAL = 1
    DEFAULT_SUSPICIOUS_THRESHOLD = 3
    DEFAULT_NOTIFICATIONS_ENABLED = True
    DEFAULT_WARN_BEFORE_CLEAR = 5

    NEVER_TIMEOUT = 0

    def __init__(self, config_manager):
        self.config = config_manager
        self._load_all()

    def _load_all(self):
        timeout_str = self.config.get(self.KEY_TIMEOUT, str(self.DEFAULT_TIMEOUT))
        try:
            self.timeout = int(timeout_str)
            if self.timeout != self.NEVER_TIMEOUT:
                self.timeout = max(5, min(300, self.timeout))
        except:
            self.timeout = self.DEFAULT_TIMEOUT

        self.security_level = self.config.get(self.KEY_SECURITY_LEVEL, self.DEFAULT_SECURITY_LEVEL)
        self.monitor_enabled = self._get_bool(self.KEY_MONITOR_ENABLED, self.DEFAULT_MONITOR_ENABLED)
        self.monitor_interval = self._get_int(self.KEY_MONITOR_INTERVAL, self.DEFAULT_MONITOR_INTERVAL)
        self.suspicious_threshold = self._get_int(self.KEY_SUSPICIOUS_THRESHOLD, self.DEFAULT_SUSPICIOUS_THRESHOLD)
        self.notifications_enabled = self._get_bool(self.KEY_NOTIFICATIONS_ENABLED, self.DEFAULT_NOTIFICATIONS_ENABLED)
        self.warn_before_clear = self._get_int(self.KEY_WARN_BEFORE_CLEAR, self.DEFAULT_WARN_BEFORE_CLEAR)

    def _get_int(self, key: str, default: int) -> int:
        try:
            value = self.config.get(key, str(default))
            return int(value)
        except (ValueError, TypeError):
            return default

    def _get_bool(self, key: str, default: bool) -> bool:
        value = self.config.get(key, str(default).lower())
        return value.lower() in ('true', '1', 'yes', 'on')

    def save(self):
        self.config.set(self.KEY_TIMEOUT, str(self.timeout))
        self.config.set(self.KEY_SECURITY_LEVEL, self.security_level)
        self.config.set(self.KEY_MONITOR_ENABLED, str(self.monitor_enabled).lower())
        self.config.set(self.KEY_MONITOR_INTERVAL, str(self.monitor_interval))
        self.config.set(self.KEY_SUSPICIOUS_THRESHOLD, str(self.suspicious_threshold))
        self.config.set(self.KEY_NOTIFICATIONS_ENABLED, str(self.notifications_enabled).lower())
        self.config.set(self.KEY_WARN_BEFORE_CLEAR, str(self.warn_before_clear))

    def set_security_level(self, level: SecurityLevel):
        self.security_level = level.value

        if level == SecurityLevel.STANDARD:
            self.timeout = 30
            self.monitor_interval = 2
            self.warn_before_clear = 5
        elif level == SecurityLevel.SECURE:
            self.timeout = 15
            self.monitor_interval = 1
            self.warn_before_clear = 3
        elif level == SecurityLevel.PARANOID:
            self.timeout = 5
            self.monitor_interval = 0.5
            self.warn_before_clear = 1

        self.save()

    def add_default_settings(self):
        default_settings = [
            (self.KEY_TIMEOUT, str(self.DEFAULT_TIMEOUT)),
            (self.KEY_SECURITY_LEVEL, self.DEFAULT_SECURITY_LEVEL),
            (self.KEY_MONITOR_ENABLED, str(self.DEFAULT_MONITOR_ENABLED).lower()),
            (self.KEY_MONITOR_INTERVAL, str(self.DEFAULT_MONITOR_INTERVAL)),
            (self.KEY_SUSPICIOUS_THRESHOLD, str(self.DEFAULT_SUSPICIOUS_THRESHOLD)),
            (self.KEY_NOTIFICATIONS_ENABLED, str(self.DEFAULT_NOTIFICATIONS_ENABLED).lower()),
            (self.KEY_WARN_BEFORE_CLEAR, str(self.DEFAULT_WARN_BEFORE_CLEAR)),
            (self.KEY_WHITELIST, '[]'),
        ]

        for key, value in default_settings:
            existing = self.config.get(key)
            if existing is None:
                encrypted = (key == self.KEY_WHITELIST)
                self.config.set(key, value, encrypted=encrypted)

    def reload(self):
        self._load_all()

    def get_whitelist(self) -> list:
        import json
        whitelist_json = self.config.get(self.KEY_WHITELIST, '[]')
        try:
            return json.loads(whitelist_json)
        except:
            return []

    def save_whitelist(self, whitelist: list):
        import json
        self.config.set(self.KEY_WHITELIST, json.dumps(whitelist, ensure_ascii=False), encrypted=True)

    def is_whitelisted(self, process_path: str = None) -> bool:
        if not process_path:
            return False

        whitelist = self.get_whitelist()
        if not whitelist:
            return False

        process_path_lower = process_path.lower()
        import os

        for whitelisted_path in whitelist:
            whitelisted_lower = whitelisted_path.lower()
            if whitelisted_lower == process_path_lower:
                return True
            if os.path.basename(whitelisted_lower) == os.path.basename(process_path_lower):
                return True

        return False