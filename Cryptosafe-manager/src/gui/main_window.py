import tkinter as tk
from tkinter import messagebox

from src.core.events import EventBus, ENTRY_ADDED
from src.database.audit_logger import AuditLogger
from src.core.state_manager import StateManager
from src.core.config import ConfigManager
from src.database.db import Database

from src.gui.widgets.secure_table import SecureTable
from src.gui.widgets.audit_log_viewer import AuditLogViewer
from src.gui.widgets.settings_dialog import SettingsDialog
from src.gui.widgets.setup_window import SetupWindow


class CryptoSafeApp:

    def __init__(self, root):
        self.root = root
        self.root.title("CryptoSafe Manager")
        self.root.geometry("900x600")

        # ============================
        # Core initialization
        # ============================

        self.event_bus = EventBus()
        self.audit_logger = AuditLogger(self.event_bus)

        self.state = StateManager()
        self.config = ConfigManager("src/database/cryptosafe.db")

        self.db = Database("src/database/cryptosafe.db")
        self.db.initialize()

        # ============================
        # UI setup
        # ============================

        self.create_menu()
        self.create_table()
        self.create_buttons()
        self.create_status_bar()


    # ============================
    # MENU
    # ============================

    def create_menu(self):
        menu_bar = tk.Menu(self.root)

        # File
        file_menu = tk.Menu(menu_bar, tearoff=0)
        file_menu.add_command(label="New")
        file_menu.add_command(label="Open")
        file_menu.add_command(label="Backup")
        file_menu.add_separator()
        file_menu.add_command(label="Exit", command=self.root.quit)
        menu_bar.add_cascade(label="File", menu=file_menu)

        # Edit
        edit_menu = tk.Menu(menu_bar, tearoff=0)
        edit_menu.add_command(label="Add", command=self.open_add_dialog)
        edit_menu.add_command(label="Edit")
        edit_menu.add_command(label="Delete", command=self.delete_selected)
        menu_bar.add_cascade(label="Edit", menu=edit_menu)

        # View
        view_menu = tk.Menu(menu_bar, tearoff=0)
        view_menu.add_command(label="Logs", command=self.open_logs)
        view_menu.add_command(label="Settings", command=self.open_settings)
        menu_bar.add_cascade(label="View", menu=view_menu)

        # Help
        help_menu = tk.Menu(menu_bar, tearoff=0)
        help_menu.add_command(label="About", command=self.show_about)
        menu_bar.add_cascade(label="Help", menu=help_menu)

        self.root.config(menu=menu_bar)

    # ============================
    # TABLE
    # ============================

    def create_table(self):
        self.table = SecureTable(self.root)
        self.table.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

    # ============================
    # BUTTONS
    # ============================

    def create_buttons(self):
        frame = tk.Frame(self.root)
        frame.pack(pady=5)

        add_btn = tk.Button(frame, text="Add Entry", command=self.open_add_dialog)
        add_btn.pack(side=tk.LEFT, padx=5)

        delete_btn = tk.Button(frame, text="Delete Entry", command=self.delete_selected)
        delete_btn.pack(side=tk.LEFT, padx=5)

    # ============================
    # STATUS BAR
    # ============================

    def create_status_bar(self):
        self.status_var = tk.StringVar()
        self.status_var.set("Status: Locked | Clipboard: --")

        status_bar = tk.Label(
            self.root,
            textvariable=self.status_var,
            relief=tk.SUNKEN,
            anchor="w"
        )
        status_bar.pack(fill=tk.X, side=tk.BOTTOM)

    # ============================
    # ADD ENTRY
    # ============================

    def open_add_dialog(self):
        dialog = tk.Toplevel(self.root)
        dialog.title("Add Entry")
        dialog.geometry("350x250")

        tk.Label(dialog, text="Title").pack()
        title_entry = tk.Entry(dialog)
        title_entry.pack()

        tk.Label(dialog, text="Username").pack()
        username_entry = tk.Entry(dialog)
        username_entry.pack()

        tk.Label(dialog, text="URL").pack()
        url_entry = tk.Entry(dialog)
        url_entry.pack()

        def save():
            title = title_entry.get()
            username = username_entry.get()
            url = url_entry.get()

            if not title:
                messagebox.showerror("Error", "Title is required")
                return

            self.table.add_entry(title, username, url)

            # публикуем событие
            self.event_bus.publish(ENTRY_ADDED, {"title": title})

            dialog.destroy()

        tk.Button(dialog, text="Save", command=save).pack(pady=10)

    # ============================
    # DELETE
    # ============================

    def delete_selected(self):
        selected = self.table.selection()
        for item in selected:
            self.table.delete(item)

    # ============================
    # OTHER WINDOWS
    # ============================

    def open_logs(self):
        AuditLogViewer(self.root)

    def open_settings(self):
        SettingsDialog(self.root)

    def show_about(self):
        messagebox.showinfo("About", "CryptoSafe Manager\nSprint 1")


# ============================
# MAIN
# ============================

def main():
    root = tk.Tk()
    root.withdraw()  # скрываем главное окно

    setup = SetupWindow(root)
    root.wait_window(setup)  # ждём закрытия setup

    if not setup.completed:
        root.destroy()
        return

    root.deiconify()  # показываем главное окно

    app = CryptoSafeApp(root)
    root.mainloop()

if __name__ == "__main__":
    main()