import time


class StateManager:

    def __init__(self):
        self.encryption_key = None
        self.login_time = None
        self.last_activity = None
        self.failed_attempts = 0
        self.auto_lock_timeout = 3600
        self.is_locked = True
        self.current_user = None

    def start_session(self, key: bytes):
        self.encryption_key = key
        self.login_time = time.time()
        self.last_activity = time.time()

    def update_activity(self):
        self.last_activity = time.time()

    def is_active(self):
        if self.encryption_key is None:
            return False

        current_time = time.time()

        # авто-блокировка
        if current_time - self.last_activity > self.auto_lock_timeout:
            self.end_session()
            return False

        return True

    def end_session(self):
        self.encryption_key = None
        self.login_time = None
        self.last_activity = None

    def lock(self):
        self.is_locked = True

    def unlock(self, user:str):
        self.is_locked = False
        self.current_user = user