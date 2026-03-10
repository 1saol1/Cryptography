
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import sys
import os

# Добавляем путь к проекту для правильных импортов при запуске через -m
if __name__ == "__main__":
    # При запуске как основной модуль
    BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    sys.path.insert(0, BASE_DIR)
else:
    # При запуске как модуль (python -m)
    BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))

print(f"🔧 Базовая директория: {BASE_DIR}")

# Теперь импортируем наши модули
try:
    from src.core.events import EventBus, ENTRY_ADDED
    from src.database.audit_logger import AuditLogger
    from src.database.db import Database
    from src.gui.widgets.secure_table import SecureTable
    from src.gui.widgets.audit_log_viewer import AuditLogViewer
    from src.gui.widgets.settings_dialog import SettingsDialog
    from src.gui.widgets.setup_window import SetupWindow
    from src.core.crypto.authentication import AuthenticationService
    from src.core.crypto.key_manager import KeyManager
    from src.core.crypto.abstract import VaultEncryptionService
    from src.core.state_manager import StateManager

    print("✅ Все импорты успешны")
except Exception as e:
    print(f"❌ Ошибка импорта: {e}")
    import traceback

    traceback.print_exc()
    input("Нажмите Enter для выхода...")
    sys.exit(1)


def show_login_window(root, auth: AuthenticationService, session: StateManager):
    """Окно входа в систему"""
    login_window = tk.Toplevel(root)
    login_window.title("Вход в CryptoSafe")
    login_window.geometry("340x220")
    login_window.resizable(False, False)

    # Центрируем окно
    login_window.transient(root)
    login_window.grab_set()

    # Принудительно показываем окно
    login_window.lift()
    login_window.focus_force()

    tk.Label(login_window, text="Введите мастер-пароль", font=("Helvetica", 12)).pack(pady=20)

    pwd_entry = tk.Entry(login_window, show="*", width=35)
    pwd_entry.pack(pady=10)
    pwd_entry.focus()

    result = {"success": False}

    def try_login(event=None):
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
            pwd_entry.delete(0, tk.END)
            pwd_entry.focus()

    tk.Button(login_window, text="Войти", command=try_login, width=15).pack(pady=10)

    # Привязываем Enter к кнопке входа
    pwd_entry.bind("<Return>", try_login)

    root.wait_window(login_window)
    return result["success"]


class CryptoSafeApp:
    """Главное приложение CryptoSafe Manager"""

    def __init__(self, root: tk.Tk, state: StateManager):
        self.root = root
        self.root.title("CryptoSafe Manager")
        self.root.geometry("960x620")
        self.root.minsize(800, 500)

        # Принудительно показываем окно
        self.root.lift()
        self.root.focus_force()

        # Core компоненты
        self.event_bus = EventBus()
        self.audit_logger = AuditLogger(self.event_bus)

        # Используем абсолютный путь к БД
        db_path = os.path.join(BASE_DIR, "src", "database", "cryptosafe.db")
        print(f"📁 База данных: {db_path}")

        self.db = Database(db_path)
        self.db.initialize()

        self.state = state  # Состояние сессии

        # Инициализация криптографии
        self.key_manager = KeyManager()

        # Получаем ключ из state и кэшируем
        encryption_key = self.state.get_key()
        if encryption_key:
            self.key_manager.cache_key(encryption_key)
            print("✓ Ключ шифрования закэширован в KeyManager")
        else:
            print("✗ Ошибка: ключ шифрования не найден в state!")
            messagebox.showerror("Ошибка", "Не удалось получить ключ шифрования")
            self.root.quit()
            return

        # Создаем сервис шифрования с нашим KeyManager (ARC-2)
        self.encryption_service = VaultEncryptionService(self.key_manager)

        # Создаем интерфейс
        self.create_menu()
        self.create_main_table()
        self.create_toolbar()
        self.create_status_bar()

        # Подписываемся на события
        self.event_bus.subscribe(ENTRY_ADDED, self.on_entry_added)

        # Запускаем таймер для проверки сессии (каждую минуту)
        self.check_session_timeout()

        # Привязываем событие сворачивания окна
        self.root.bind("<Unmap>", self.on_app_minimize)

        # Привязываем событие закрытия окна
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)

    def check_session_timeout(self):
        """Проверяет не истекла ли сессия (CACHE-2)"""
        try:
            if not self.state.is_active():
                self.status_var.set("Сессия истекла. Требуется повторный вход")
                messagebox.showinfo("Сессия истекла",
                                    "Время сессии истекло. Пожалуйста, войдите снова.")
                self.root.quit()
                return

            # Обновляем статус
            session_info = self.state.get_session_info()
            user_text = f" | Пользователь: {session_info['current_user'] or 'unknown'}"
            self.status_var.set(f"Готово{user_text} | Сессия активна")
        except Exception as e:
            print(f"Ошибка в check_session_timeout: {e}")

        # Проверяем каждую минуту
        self.root.after(60000, self.check_session_timeout)

    def on_app_minimize(self, event=None):
        """Вызывается при сворачивании приложения (CACHE-2)"""
        print("📱 Приложение свернуто - блокируем сессию")
        self.state.lock()
        self.key_manager.clear_cache()
        self.status_var.set("Приложение свернуто - данные защищены")

    def on_closing(self):
        """Вызывается при закрытии приложения"""
        print("👋 Завершение работы приложения")
        self.state.end_session()
        self.key_manager.clear_cache()
        self.db.close()
        self.root.destroy()

    def create_menu(self):
        """Создает меню приложения"""
        menubar = tk.Menu(self.root)

        # Файл
        file_menu = tk.Menu(menubar, tearoff=0)
        file_menu.add_command(label="Создать", command=self.new_database)
        file_menu.add_command(label="Открыть", command=self.open_database)
        file_menu.add_separator()
        file_menu.add_command(label="Резервная копия", command=self.create_backup)
        file_menu.add_separator()
        file_menu.add_command(label="Выход", command=self.on_closing)
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

    def create_toolbar(self):
        """Создает панель инструментов"""
        toolbar = ttk.Frame(self.root)
        toolbar.pack(fill=tk.X, padx=10, pady=(10, 5))

        ttk.Button(toolbar, text="➕ Добавить", command=self.open_add_dialog).pack(side=tk.LEFT, padx=(0, 6))
        ttk.Button(toolbar, text="✏️ Изменить", command=self.edit_selected).pack(side=tk.LEFT, padx=6)
        ttk.Button(toolbar, text="🗑️ Удалить", command=self.delete_selected).pack(side=tk.LEFT, padx=6)

    def create_main_table(self):
        """Создает основную таблицу с записями"""
        self.table = SecureTable(self.root)
        self.table.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        # Тестовые данные (потом будем загружать из БД)
        self.table.add_entry("Google", "user@gmail.com", "https://accounts.google.com")
        self.table.add_entry("GitHub", "username", "https://github.com")
        self.table.add_entry("Localhost", "admin", "http://localhost")

    def create_status_bar(self):
        """Создает строку состояния"""
        self.status_var = tk.StringVar(value="Готово | Сессия активна")
        status_bar = ttk.Label(
            self.root,
            textvariable=self.status_var,
            relief=tk.SUNKEN,
            anchor="w"
        )
        status_bar.pack(side=tk.BOTTOM, fill=tk.X)

    def new_database(self):
        """Создает новую базу данных"""
        messagebox.showinfo("Создать", "Функция создания новой базы данных\n(будет реализована в следующих спринтах)")

    def open_database(self):
        """Открывает существующую базу данных"""
        path = filedialog.askopenfilename(
            title="Открыть базу данных",
            filetypes=[("SQLite Database", "*.db"), ("All Files", "*.*")]
        )
        if path:
            messagebox.showinfo("Открыть", f"Открыта база: {path}\n(реализация в следующих спринтах)")

    def create_backup(self):
        """Создает резервную копию"""
        messagebox.showinfo("Резервная копия", "Создание резервной копии\n(будет реализовано в спринте 8)")

    def edit_selected(self):
        """Редактирует выбранную запись"""
        selected = self.table.selection()
        if not selected:
            messagebox.showinfo("Информация", "Выберите запись для редактирования")
            return

        # Проверяем активность сессии
        if not self.state.is_active():
            messagebox.showerror("Ошибка", "Сессия не активна. Выполните вход заново.")
            return

        # Пока заглушка
        messagebox.showinfo("Редактирование", "Функция редактирования записи\n(будет реализована позже)")

        # Обновляем активность
        self.state.update_activity()
        self.key_manager._update_activity()

    def delete_selected(self):
        """Удаляет выбранные записи"""
        selected = self.table.selection()
        if not selected:
            messagebox.showinfo("Информация", "Выберите запись для удаления")
            return

        # Проверяем активность сессии
        if not self.state.is_active():
            messagebox.showerror("Ошибка", "Сессия не активна. Выполните вход заново.")
            return

        if messagebox.askyesno("Подтверждение", "Удалить выбранные записи?"):
            for item in selected:
                self.table.delete(item)

            # Обновляем активность
            self.state.update_activity()
            self.key_manager._update_activity()

            self.status_var.set("Записи удалены")

    def open_add_dialog(self):
        """Открывает диалог добавления новой записи"""
        # Проверяем активность сессии
        if not self.state.is_active():
            messagebox.showerror("Ошибка", "Сессия не активна. Выполните вход заново.")
            return

        dialog = tk.Toplevel(self.root)
        dialog.title("➕ Новая запись")
        dialog.geometry("450x400")
        dialog.resizable(False, False)

        # Делаем окно модальным
        dialog.transient(self.root)
        dialog.grab_set()

        # Принудительно показываем
        dialog.lift()
        dialog.focus_force()

        # Поля ввода
        ttk.Label(dialog, text="Название:", font=("Helvetica", 10, "bold")).pack(anchor="w", padx=20, pady=(20, 5))
        title_entry = ttk.Entry(dialog, width=50)
        title_entry.pack(padx=20)
        title_entry.focus()

        ttk.Label(dialog, text="Логин/Email:", font=("Helvetica", 10, "bold")).pack(anchor="w", padx=20, pady=(12, 5))
        user_entry = ttk.Entry(dialog, width=50)
        user_entry.pack(padx=20)

        ttk.Label(dialog, text="Пароль:", font=("Helvetica", 10, "bold")).pack(anchor="w", padx=20, pady=(12, 5))
        pwd_entry = ttk.Entry(dialog, width=50, show="*")
        pwd_entry.pack(padx=20)

        ttk.Label(dialog, text="URL/Адрес:", font=("Helvetica", 10, "bold")).pack(anchor="w", padx=20, pady=(12, 5))
        url_entry = ttk.Entry(dialog, width=50)
        url_entry.pack(padx=20)

        def save_entry():
            title = title_entry.get().strip()
            username = user_entry.get().strip()
            password = pwd_entry.get().strip()
            url = url_entry.get().strip()

            if not title:
                messagebox.showwarning("Внимание", "Название — обязательное поле")
                return

            try:
                # Пример использования шифрования (ARC-2)
                encrypted_pwd = None
                if password:
                    # Шифруем пароль перед сохранением
                    encrypted_pwd = self.encryption_service.encrypt(password.encode())
                    print(f"🔐 Пароль зашифрован, длина: {len(encrypted_pwd)} байт")

                    # TODO: здесь будет сохранение в БД

                # Добавляем в таблицу (пока без шифрования)
                self.table.add_entry(title, username, url)

                # Публикуем событие
                self.event_bus.publish(ENTRY_ADDED, {
                    "title": title,
                    "username": username,
                    "url": url
                })

                # Обновляем активность
                self.state.update_activity()
                self.key_manager._update_activity()

                dialog.destroy()

            except ValueError as e:
                messagebox.showerror("Ошибка", f"Не удалось зашифровать данные: {e}")
            except Exception as e:
                messagebox.showerror("Ошибка", f"Ошибка при сохранении: {e}")

        # Кнопки
        btn_frame = ttk.Frame(dialog)
        btn_frame.pack(pady=25)

        ttk.Button(btn_frame, text="Сохранить", command=save_entry, width=15).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Отмена", command=dialog.destroy, width=15).pack(side=tk.LEFT, padx=5)

        # Привязываем Enter к сохранению
        dialog.bind("<Return>", lambda e: save_entry())
        dialog.bind("<Escape>", lambda e: dialog.destroy())

    def open_audit_logs(self):
        """Открывает просмотр логов"""
        AuditLogViewer(self.root)

    def open_settings(self):
        """Открывает настройки"""
        SettingsDialog(self.root)

    def show_about(self):
        """Показывает информацию о программе"""
        messagebox.showinfo(
            "О программе",
            "🔐 CryptoSafe Manager\n\n"
            "Версия: 2.0 (Спринт 2)\n"
            "Локальный менеджер паролей с шифрованием\n\n"
            "Реализовано:\n"
            "✓ Аутентификация по мастер-паролю\n"
            "✓ Argon2id и PBKDF2\n"
            "✓ Безопасное кэширование ключей\n"
            "✓ Система миграций БД\n"
        )

    def on_entry_added(self, data):
        """Обработчик добавления записи"""
        self.status_var.set(f"✅ Добавлена запись: {data.get('title', 'без названия')}")
        self.state.update_activity()
        self.key_manager._update_activity()


def main():
    """Точка входа в приложение"""
    print("🚀 Запуск CryptoSafe Manager...")

    # Создаем корневое окно
    root = tk.Tk()
    root.withdraw()  # Скрываем главное окно до входа

    # Принудительно инициализируем Tkinter
    root.update()

    # Инициализация БД с миграциями (ARC-3)
    db_path = os.path.join(BASE_DIR, "src", "database", "cryptosafe.db")
    print(f"📁 База данных: {db_path}")

    # Создаем папку для БД если её нет
    os.makedirs(os.path.dirname(db_path), exist_ok=True)

    db = Database(db_path)
    db.initialize()

    # Сервис аутентификации
    auth = AuthenticationService(db_path)

    # Состояние сессии
    state = StateManager()

    # Проверяем, инициализировано ли приложение (есть ли мастер-пароль)
    if not auth.is_initialized():
        print("🆕 Первый запуск - окно регистрации")
        setup = SetupWindow(root, auth)
        root.wait_window(setup)

        if not setup.completed:
            print("❌ Регистрация отменена")
            root.destroy()
            return

    # Показываем окно входа
    print("🔑 Окно входа...")
    login_success = show_login_window(root, auth, state)

    if not login_success:
        print("❌ Вход не выполнен")
        root.destroy()
        return

    print("✅ Вход выполнен успешно")

    # Показываем главное окно
    root.deiconify()

    # Принудительно показываем окно поверх всех
    root.lift()
    root.focus_force()
    root.attributes('-topmost', True)
    root.after(100, lambda: root.attributes('-topmost', False))

    # Создаем и запускаем приложение
    print("🪟 Создание главного окна...")
    app = CryptoSafeApp(root, state)

    print("🔄 Запуск главного цикла...")
    root.mainloop()
    print("👋 Программа завершена")


if __name__ == "__main__":
    print("=" * 50)
    print("CryptoSafe Manager - Запуск")
    print("=" * 50)
    main()