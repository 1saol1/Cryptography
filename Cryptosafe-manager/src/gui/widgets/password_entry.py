import tkinter as tk


class PasswordEntry(tk.Frame):
    def __init__(self, parent):
        super().__init__(parent)

        self.entry = tk.Entry(self, show="*")
        self.entry.pack(side=tk.LEFT)

        self.show_var = tk.BooleanVar()

        self.checkbox = tk.Checkbutton(
            self,
            text="Show",
            variable=self.show_var,
            command=self.toggle_password
        )
        self.checkbox.pack(side=tk.LEFT)

    def toggle_password(self):
        if self.show_var.get():
            self.entry.config(show="")
        else:
            self.entry.config(show="*")

    def get(self):
        return self.entry.get()