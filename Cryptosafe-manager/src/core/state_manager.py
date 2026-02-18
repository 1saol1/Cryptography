class StateManager:


    def __init__(self):

        self.is_authenticated = False
        self.is_locked = True


        self.clipboard_content = None
        self.clipboard_timer = None
        self.inactivity_timer = None


    def login(self):
        self.is_authenticated = True
        self.is_locked = False

    def logout(self):
        self.is_authenticated = False
        self.is_locked = True

    def lock(self):
        self.is_locked = True

    def unlock(self):
        if self.is_authenticated:
            self.is_locked = False