import time
from typing import Optional


class StateManager:
    def __init__(self, key_manager=None):
        self.encryption_key = None
        self.login_time = None
        self.last_activity = None
        self.failed_attempts = 0
        self.auto_lock_timeout = 3600
        self.is_locked = True
        self.current_user = None
        self.logged_in = False
        self.key_manager = key_manager

    def start_session(self, key: bytes, user: str = None):
        self.encryption_key = key
        self.current_user = user
        self.login_time = time.time()
        self.last_activity = time.time()
        self.is_locked = False
        self.logged_in = True
        self.failed_attempts = 0

    def update_activity(self):
        self.last_activity = time.time()

    def get_key(self) -> Optional[bytes]:
        if self.is_active():
            return self.encryption_key
        return None

    def get_current_user(self) -> Optional[str]:
        return self.current_user

    def is_active(self):
        if self.encryption_key is None:
            return False

        if time.time() - self.last_activity > self.auto_lock_timeout:
            self.end_session()
            return False

        if self.login_time and time.time() - self.login_time > 3600:
            self.end_session()
            return False

        return True

    def end_session(self):
        if self.key_manager:
            self.key_manager.clear_cache()
        self.encryption_key = None
        self.login_time = None
        self.last_activity = None
        self.is_locked = True
        self.logged_in = False
        self.current_user = None

    def lock(self):
        if self.key_manager:
            self.key_manager.clear_cache()
        self.encryption_key = None
        self.is_locked = True
        self.logged_in = False

    def unlock(self, user: str, key: bytes):
        self.is_locked = False
        self.current_user = user
        self.encryption_key = key
        self.login_time = time.time()
        self.last_activity = time.time()
        self.logged_in = True

    def get_session_info(self) -> dict:
        return {
            "logged_in": self.logged_in,
            "is_locked": self.is_locked,
            "login_time": self.login_time,
            "last_activity": self.last_activity,
            "current_user": self.current_user,
            "failed_attempts": self.failed_attempts
        }