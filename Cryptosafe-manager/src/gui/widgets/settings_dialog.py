import tkinter as tk
from tkinter import ttk


class SettingsDialog(tk.Toplevel):
    def __init__(self, parent):
        super().__init__(parent)

        self.title("Settings")
        self.geometry("400x300")

        notebook = ttk.Notebook(self)
        notebook.pack(fill="both", expand=True)

        security_tab = tk.Frame(notebook)
        appearance_tab = tk.Frame(notebook)
        advanced_tab = tk.Frame(notebook)

        notebook.add(security_tab, text="Security")
        notebook.add(appearance_tab, text="Appearance")
        notebook.add(advanced_tab, text="Advanced")

        tk.Label(security_tab, text="Clipboard timeout (stub)").pack(pady=10)
        tk.Label(appearance_tab, text="Theme (stub)").pack(pady=10)
        tk.Label(advanced_tab, text="Backup / Export (stub)").pack(pady=10)