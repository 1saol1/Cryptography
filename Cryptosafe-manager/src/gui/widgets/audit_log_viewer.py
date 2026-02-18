import tkinter as tk


class AuditLogViewer(tk.Toplevel):
    def __init__(self, parent):
        super().__init__(parent)
        self.title("Audit Log")
        self.geometry("400x300")

        label = tk.Label(self, text="Audit Log Viewer (Sprint 5)")
        label.pack(pady=20)