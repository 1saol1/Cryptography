import tkinter as tk
from tkinter import messagebox

from src.core.events import EventBus, ENTRY_ADDED
from src.database.audit_logger import AuditLogger
from src.database.db import Database

from src.gui.widgets.secure_table import SecureTable
from src.gui.widgets.audit_log_viewer import AuditLogViewer
from src.gui.widgets.settings_dialog import SettingsDialog
from src.gui.widgets.setup_window import SetupWindow

from src.core.crypto.authentication import AuthenticationService
from src.core.state_manager import StateManager

# login window

def show_login_window(root, auth, session):
    login_window = tk.Toplevel(root)
    login_window.title("Login")
    login_window.geometry("300x200")

    tk.Label(login_window, text="Enter Master Password").pack(pady=10)
    entry = tk.Entry(login_window, show="*")
    entry.pack(pady=5)

    result = {"success": False}

    def login():
        password = entry.get()
        key = auth.login(password)

        if key:
            session.start_session(key)
            result["success"] = True
            login_window.destroy()
        else:
            messagebox.showerror("Error", "Wrong password")

    tk.Button(login_window, text="Login", command=login).pack(pady=10)

    root.wait_window(login_window)
    return result["success"]


# main application

class CryptoSafeApp:

    def __init__(self, root):
        self.root = root
        self.root.title("CryptoSafe Manager")
        self.root.geometry("900x600")

        # Core
        self.event_bus = EventBus()
        self.audit_logger = AuditLogger(self.event_bus)

        self.db = Database("src/database/cryptosafe.db")
        self.db.initialize()

        # UI
        self.create_menu()
        self.create_table()
        self.create_buttons()
        self.create_status_bar()


    # Menu


    def create_menu(self):
        menu_bar = tk.Menu(self.root)

        file_menu = tk.Menu(menu_bar, tearoff=0)
        file_menu.add_command(label="Exit", command=self.root.quit)
        menu_bar.add_cascade(label="File", menu=file_menu)

        edit_menu = tk.Menu(menu_bar, tearoff=0)
        edit_menu.add_command(label="Add", command=self.open_add_dialog)
        edit_menu.add_command(label="Delete", command=self.delete_selected)
        menu_bar.add_cascade(label="Edit", menu=edit_menu)

        view_menu = tk.Menu(menu_bar, tearoff=0)
        view_menu.add_command(label="Logs", command=self.open_logs)
        view_menu.add_command(label="Settings", command=self.open_settings)
        menu_bar.add_cascade(label="View", menu=view_menu)

        help_menu = tk.Menu(menu_bar, tearoff=0)
        help_menu.add_command(label="About", command=self.show_about)
        menu_bar.add_cascade(label="Help", menu=help_menu)

        self.root.config(menu=menu_bar)

    # table

    def create_table(self):
        self.table = SecureTable(self.root)
        self.table.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)


    # buttons


    def create_buttons(self):
        frame = tk.Frame(self.root)
        frame.pack(pady=5)

        tk.Button(frame, text="Add Entry", command=self.open_add_dialog).pack(side=tk.LEFT, padx=5)
        tk.Button(frame, text="Delete Entry", command=self.delete_selected).pack(side=tk.LEFT, padx=5)

    # status bar

    def create_status_bar(self):
        self.status_var = tk.StringVar()
        self.status_var.set("Status: Unlocked")

        status_bar = tk.Label(
            self.root,
            textvariable=self.status_var,
            relief=tk.SUNKEN,
            anchor="w"
        )
        status_bar.pack(fill=tk.X, side=tk.BOTTOM)


    # add entry

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

            self.event_bus.publish(ENTRY_ADDED, {"title": title})

            dialog.destroy()

        tk.Button(dialog, text="Save", command=save).pack(pady=5)

    # delete

    def delete_selected(self):
        selected = self.table.selection()
        for item in selected:
            self.table.delete(item)

    # other windows

    def open_logs(self):
        AuditLogViewer(self.root)

    def open_settings(self):
        SettingsDialog(self.root)

    def show_about(self):
        messagebox.showinfo("About", "CryptoSafe Manager\nSprint 2")


def main():
    root = tk.Tk()
    root.withdraw()

    db = Database("src/database/cryptosafe.db")
    db.initialize()   # ← ВАЖНО

    auth = AuthenticationService("src/database/cryptosafe.db")
    session = StateManager()

    if not auth.is_initialized():
        setup = SetupWindow(root, auth)
        root.wait_window(setup)

        if not setup.completed:
            root.destroy()
            return

    login_success = show_login_window(root, auth, session)

    if not login_success:
        root.destroy()
        return

    root.deiconify()
    app = CryptoSafeApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()