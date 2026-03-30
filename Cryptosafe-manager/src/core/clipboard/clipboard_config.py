from enum import Enum


class SecurityLevel(Enum):
    STANDARD = "standard"
    SECURE = "secure"
    PARANOID = "paranoid"


class ClipboardSettings:
    KEY_TIMEOUT = "clipboard_timeout"
    KEY_SECURITY_LEVEL = "clipboard_security_level"
    KEY_MONITOR_ENABLED = "clipboard_monitor_enabled"
    KEY_MONITOR_INTERVAL = "clipboard_monitor_interval"
    KEY_SUSPICIOUS_THRESHOLD = "clipboard_suspicious_threshold"
    KEY_NOTIFICATIONS_ENABLED = "clipboard_notifications_enabled"
    KEY_WARN_BEFORE_CLEAR = "clipboard_warn_before_clear"

    DEFAULT_TIMEOUT = 30
    DEFAULT_SECURITY_LEVEL = SecurityLevel.STANDARD.value
    DEFAULT_MONITOR_ENABLED = True
    DEFAULT_MONITOR_INTERVAL = 1
    DEFAULT_SUSPICIOUS_THRESHOLD = 3
    DEFAULT_NOTIFICATIONS_ENABLED = True
    DEFAULT_WARN_BEFORE_CLEAR = 5

    def __init__(self, config_manager):
        self.config = config_manager
        self._load_all()

    def _load_all(self):
        self.timeout = self._get_int(self.KEY_TIMEOUT, self.DEFAULT_TIMEOUT)
        self.security_level = self.config.get(
            self.KEY_SECURITY_LEVEL,
            self.DEFAULT_SECURITY_LEVEL
        )
        self.monitor_enabled = self._get_bool(
            self.KEY_MONITOR_ENABLED,
            self.DEFAULT_MONITOR_ENABLED
        )
        self.monitor_interval = self._get_int(
            self.KEY_MONITOR_INTERVAL,
            self.DEFAULT_MONITOR_INTERVAL
        )
        self.suspicious_threshold = self._get_int(
            self.KEY_SUSPICIOUS_THRESHOLD,
            self.DEFAULT_SUSPICIOUS_THRESHOLD
        )
        self.notifications_enabled = self._get_bool(
            self.KEY_NOTIFICATIONS_ENABLED,
            self.DEFAULT_NOTIFICATIONS_ENABLED
        )
        self.warn_before_clear = self._get_int(
            self.KEY_WARN_BEFORE_CLEAR,
            self.DEFAULT_WARN_BEFORE_CLEAR
        )

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
            self.monitor_enabled = True
            self.monitor_interval = 2
            self.warn_before_clear = 5
        elif level == SecurityLevel.SECURE:
            self.timeout = 15
            self.monitor_enabled = True
            self.monitor_interval = 1
            self.warn_before_clear = 3
        elif level == SecurityLevel.PARANOID:
            self.timeout = 5
            self.monitor_enabled = True
            self.monitor_interval = 0.5
            self.warn_before_clear = 1

        self.save()

    def get_preset_profile(self, profile_name: str) -> dict:
        profiles = {
            "standard": {
                "timeout": 30,
                "monitor_enabled": True,
                "notifications_enabled": True,
                "warn_before_clear": 5,
                "description": "Стандартный режим"
            },
            "secure": {
                "timeout": 15,
                "monitor_enabled": True,
                "notifications_enabled": True,
                "warn_before_clear": 3,
                "description": "Усиленная безопасность"
            },
            "public_computer": {
                "timeout": 5,
                "monitor_enabled": True,
                "notifications_enabled": True,
                "warn_before_clear": 1,
                "description": "Общедоступный компьютер"
            }
        }

        return profiles.get(profile_name, profiles["standard"])

    def apply_profile(self, profile_name: str):
        profile = self.get_preset_profile(profile_name)

        self.timeout = profile["timeout"]
        self.monitor_enabled = profile["monitor_enabled"]
        self.notifications_enabled = profile["notifications_enabled"]
        self.warn_before_clear = profile["warn_before_clear"]

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
        ]

        for key, value in default_settings:
            existing = self.config.get(key)
            if existing is None:
                self.config.set(key, value)
                print(f"Добавлена настройка {key} = {value}")