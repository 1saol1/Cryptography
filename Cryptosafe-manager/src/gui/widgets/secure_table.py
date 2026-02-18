import tkinter as tk
from tkinter import ttk


class SecureTable(ttk.Treeview):
    def __init__(self, parent):
        columns = ("Title", "Username", "URL")
        super().__init__(parent, columns=columns, show="headings")

        for col in columns:
            self.heading(col, text=col)
            self.column(col, width=200)

    def add_entry(self, title, username, url):
        self.insert("", tk.END, values=(title, username, url))