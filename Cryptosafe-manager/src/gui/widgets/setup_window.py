import tkinter as tk
from tkinter import messagebox
from .password_entry import PasswordEntry


class SetupWindow(tk.Toplevel):
    def __init__(self, parent, auth):
        super().__init__(parent)
        self.auth = auth
        self.completed = False

        self.title("Initial Setup")
        self.geometry("400x350")

        tk.Label(self, text="Create Master Password").pack(pady=10)

        self.password1 = PasswordEntry(self)
        self.password1.pack(pady=5)

        tk.Label(self, text="Confirm Password").pack(pady=10)

        self.password2 = PasswordEntry(self)
        self.password2.pack(pady=5)

        tk.Label(self, text="Database location (stub)").pack(pady=10)
        self.db_entry = tk.Entry(self)
        self.db_entry.insert(0, "src/database/cryptosafe.db")
        self.db_entry.pack()

        save_btn = tk.Button(self, text="Save", command=self.save)
        save_btn.pack(pady=15)

    def save(self):
        password1 = self.password1.get()
        password2 = self.password2.get()

        if password1 != password2:
            messagebox.showerror("Error", "Passwords do not match")
            return

        if not password1:
            messagebox.showerror("Error", "Password cannot be empty")
            return

        self.auth.register(password1)
        self.completed = True
        self.destroy()