# src/gui/main_window.py

import tkinter as tk
from tkinter import ttk, messagebox, filedialog

from src.core.events import EventBus, ENTRY_ADDED
from src.database.audit_logger import AuditLogger
from src.database.db import Database
from src.gui.widgets.secure_table import SecureTable
from src.gui.widgets.audit_log_viewer import AuditLogViewer
from src.gui.widgets.settings_dialog import SettingsDialog
from src.gui.widgets.setup_window import SetupWindow
from src.core.crypto.authentication import AuthenticationService
from src.core.state_manager import StateManager


def show_login_window(root, auth: AuthenticationService, session: StateManager):
    login_window = tk.Toplevel(root)
    login_window.title("Вход в CryptoSafe")
    login_window.geometry("340x220")
    login_window.resizable(False, False)

    tk.Label(login_window, text="Введите мастер-пароль", font=("Helvetica", 12)).pack(pady=20)

    pwd_entry = tk.Entry(login_window, show="*", width=35)
    pwd_entry.pack(pady=10)

    result = {"success": False}

    def try_login():
        password = pwd_entry.get()
        if not password:
            messagebox.showerror("Ошибка", "Пароль не может быть пустым")
            return

        key = auth.login(password)
        if key:
            session.start_session(key)
            result["success"] = True
            login_window.destroy()
        else:
            messagebox.showerror("Ошибка", "Неверный мастер-пароль")

    tk.Button(login_window, text="Войти", command=try_login, width=15).pack(pady=10)

    root.wait_window(login_window)
    return result["success"]


class CryptoSafeApp:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("CryptoSafe Manager")
        self.root.geometry("960x620")
        self.root.minsize(800, 500)

        # Core
        self.event_bus = EventBus()
        self.audit_logger = AuditLogger(self.event_bus)
        self.db = Database("src/database/cryptosafe.db")
        self.db.initialize()

        self.state = StateManager()

        self.create_menu()
        self.create_main_table()
        self.create_toolbar()
        self.create_status_bar()

        self.event_bus.subscribe(ENTRY_ADDED, self.on_entry_added)

    def create_menu(self):
        menubar = tk.Menu(self.root)

        # Файл
        file_menu = tk.Menu(menubar, tearoff=0)
        file_menu.add_command(label="Создать", command=self.new_database)
        file_menu.add_command(label="Открыть", command=self.open_database)
        file_menu.add_separator()
        file_menu.add_command(label="Резервная копия", command=self.create_backup)
        file_menu.add_separator()
        file_menu.add_command(label="Выход", command=self.root.quit)
        menubar.add_cascade(label="Файл", menu=file_menu)

        # Правка
        edit_menu = tk.Menu(menubar, tearoff=0)
        edit_menu.add_command(label="Добавить", command=self.open_add_dialog)
        edit_menu.add_command(label="Изменить", command=self.edit_selected)
        edit_menu.add_command(label="Удалить", command=self.delete_selected)
        menubar.add_cascade(label="Правка", menu=edit_menu)

        # Вид
        view_menu = tk.Menu(menubar, tearoff=0)
        view_menu.add_command(label="Логи", command=self.open_audit_logs)
        view_menu.add_command(label="Настройки", command=self.open_settings)
        menubar.add_cascade(label="Вид", menu=view_menu)

        # Справка
        help_menu = tk.Menu(menubar, tearoff=0)
        help_menu.add_command(label="О программе", command=self.show_about)
        menubar.add_cascade(label="Справка", menu=help_menu)

        self.root.config(menu=menubar)

    # ── Функции меню Файл ───────────────────────────────────────────────────────

    def new_database(self):
        messagebox.showinfo("Создать", "Функция создания новой базы данных\n(будет реализована в следующих спринтах)")

    def open_database(self):
        path = filedialog.askopenfilename(
            title="Открыть базу данных",
            filetypes=[("SQLite Database", "*.db"), ("All Files", "*.*")]
        )
        if path:
            messagebox.showinfo("Открыть", f"Открыта база: {path}\n(реализация в следующих спринтах)")

    def create_backup(self):
        messagebox.showinfo("Резервная копия", "Создание резервной копии\n(будет реализовано в спринте 8)")

    # ── Функции меню Правка ─────────────────────────────────────────────────────

    def edit_selected(self):
        selected = self.table.selection()
        if not selected:
            messagebox.showinfo("Информация", "Выберите запись для редактирования")
            return

        # Пока заглушка
        messagebox.showinfo("Редактирование", "Функция редактирования записи\n(будет реализована позже)")

    # ── Остальные функции (уже были) ───────────────────────────────────────────

    def create_toolbar(self):
        toolbar = ttk.Frame(self.root)
        toolbar.pack(fill=tk.X, padx=10, pady=(10, 5))

        ttk.Button(toolbar, text="Добавить", command=self.open_add_dialog).pack(side=tk.LEFT, padx=(0, 6))
        ttk.Button(toolbar, text="Удалить", command=self.delete_selected).pack(side=tk.LEFT, padx=6)

    def create_main_table(self):
        self.table = SecureTable(self.root)
        self.table.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        # тестовые данные
        self.table.add_entry("Google", "user@gmail.com", "https://accounts.google.com")
        self.table.add_entry("GitHub", "username", "https://github.com")

    def create_status_bar(self):
        self.status_var = tk.StringVar(value="Готово | Сессия активна")
        status_bar = ttk.Label(
            self.root,
            textvariable=self.status_var,
            relief=tk.SUNKEN,
            anchor="w"
        )
        status_bar.pack(side=tk.BOTTOM, fill=tk.X)

    def open_add_dialog(self):
        dialog = tk.Toplevel(self.root)
        dialog.title("Новая запись")
        dialog.geometry("420x320")
        dialog.resizable(False, False)

        ttk.Label(dialog, text="Название:").pack(anchor="w", padx=20, pady=(20, 5))
        title_entry = ttk.Entry(dialog, width=50)
        title_entry.pack(padx=20)

        ttk.Label(dialog, text="Логин/Email:").pack(anchor="w", padx=20, pady=(12, 5))
        user_entry = ttk.Entry(dialog, width=50)
        user_entry.pack(padx=20)

        ttk.Label(dialog, text="URL/Адрес:").pack(anchor="w", padx=20, pady=(12, 5))
        url_entry = ttk.Entry(dialog, width=50)
        url_entry.pack(padx=20)

        def save_entry():
            title = title_entry.get().strip()
            username = user_entry.get().strip()
            url = url_entry.get().strip()

            if not title:
                messagebox.showwarning("Внимание", "Название — обязательное поле")
                return

            self.table.add_entry(title, username, url)
            self.event_bus.publish(ENTRY_ADDED, {"title": title, "username": username, "url": url})
            dialog.destroy()

        ttk.Button(dialog, text="Сохранить", command=save_entry).pack(pady=25)

    def delete_selected(self):
        selected = self.table.selection()
        if not selected:
            messagebox.showinfo("Информация", "Выберите запись для удаления")
            return

        if messagebox.askyesno("Подтверждение", "Удалить выбранные записи?"):
            for item in selected:
                self.table.delete(item)

    def open_audit_logs(self):
        AuditLogViewer(self.root)

    def open_settings(self):
        SettingsDialog(self.root)

    def show_about(self):
        messagebox.showinfo(
            "О программе",
            "CryptoSafe Manager\n\n"
            "Учебный проект — Спринт 1\n"
            "Локальный менеджер паролей с шифрованием\n"
            "2025–2026"
        )

    def on_entry_added(self, data):
        self.status_var.set(f"Добавлена запись: {data.get('title', 'без названия')}")

    def new_database(self):
        pass  # уже есть выше

    def open_database(self):
        pass  # уже есть выше

    def create_backup(self):
        pass  # уже есть выше


def main():
    root = tk.Tk()
    root.withdraw()

    db = Database("src/database/cryptosafe.db")
    db.initialize()

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