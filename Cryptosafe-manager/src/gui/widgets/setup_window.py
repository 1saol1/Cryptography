import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import os
from .password_entry import PasswordEntry


class SetupWindow(tk.Toplevel):
    def __init__(self, parent, auth):
        super().__init__(parent)
        self.auth = auth
        self.completed = False

        self.title("Первоначальная настройка CryptoSafe")
        self.geometry("600x750")
        self.minsize(600, 750)
        self.resizable(False, False)

        # Стили
        style = ttk.Style(self)
        style.configure("Title.TLabel", font=("Helvetica", 16, "bold"))
        style.configure("Header.TLabel", font=("Helvetica", 13, "bold"))
        style.configure("Normal.TLabel", font=("Helvetica", 11))
        style.configure("Action.TButton", font=("Helvetica", 12), padding=10)
        style.configure("Accent.TButton", font=("Helvetica", 13, "bold"), padding=(30, 15))

        # Настройка grid для основного окна
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)

        self.create_widgets()
        self.center_window()

    def center_window(self):
        self.update_idletasks()
        width = self.winfo_width()
        height = self.winfo_height()
        x = (self.winfo_screenwidth() // 2) - (width // 2)
        y = (self.winfo_screenheight() // 2) - (height // 2)
        self.geometry(f"{width}x{height}+{x}+{y}")

    def create_widgets(self):
        # Главный контейнер с grid
        main_container = ttk.Frame(self, padding="30 20")
        main_container.grid(row=0, column=0, sticky="nsew")
        main_container.grid_columnconfigure(0, weight=1)
        main_container.grid_rowconfigure(0, weight=1)  # Верхняя часть растягивается
        main_container.grid_rowconfigure(1, weight=0)  # Нижняя часть фиксирована

        # Верхний контейнер с содержимым (растягивается)
        content_frame = ttk.Frame(main_container)
        content_frame.grid(row=0, column=0, sticky="nsew")
        content_frame.grid_columnconfigure(0, weight=1)

        # Заголовок
        ttk.Label(
            content_frame,
            text="Добро пожаловать в CryptoSafe Manager",
            style="Title.TLabel"
        ).grid(row=0, column=0, pady=(0, 15), sticky="ew")

        ttk.Label(
            content_frame,
            text="Создайте мастер-пароль и выберите место для базы данных",
            wraplength=520,
            justify="center",
            style="Normal.TLabel"
        ).grid(row=1, column=0, pady=(0, 20), sticky="ew")

        # Мастер-пароль
        pwd_frame = ttk.LabelFrame(content_frame, text="Мастер-пароль", padding=20)
        pwd_frame.grid(row=2, column=0, sticky="ew", pady=(0, 15))
        pwd_frame.grid_columnconfigure(1, weight=1)

        ttk.Label(pwd_frame, text="Пароль:", style="Normal.TLabel").grid(
            row=0, column=0, sticky="w", pady=10, padx=(0, 15)
        )
        self.password1 = PasswordEntry(pwd_frame)
        self.password1.grid(row=0, column=1, sticky="ew", pady=10)

        ttk.Label(pwd_frame, text="Подтверждение:", style="Normal.TLabel").grid(
            row=1, column=0, sticky="w", pady=10, padx=(0, 15)
        )
        self.password2 = PasswordEntry(pwd_frame)
        self.password2.grid(row=1, column=1, sticky="ew", pady=10)

        # Путь к БД
        db_frame = ttk.LabelFrame(content_frame, text="Расположение базы данных", padding=20)
        db_frame.grid(row=3, column=0, sticky="ew", pady=(0, 15))
        db_frame.grid_columnconfigure(1, weight=1)

        self.db_path = tk.StringVar(value=os.path.abspath("cryptosafe.db"))

        ttk.Label(db_frame, text="Путь:", style="Normal.TLabel").grid(
            row=0, column=0, sticky="w", padx=(0, 15), pady=10
        )

        # Рамка для поля ввода и кнопки
        path_entry_frame = ttk.Frame(db_frame)
        path_entry_frame.grid(row=0, column=1, sticky="ew", pady=10)
        path_entry_frame.grid_columnconfigure(0, weight=1)

        ttk.Entry(
            path_entry_frame,
            textvariable=self.db_path,
            font=("Helvetica", 11)
        ).grid(row=0, column=0, sticky="ew", padx=(0, 10))

        ttk.Button(
            path_entry_frame,
            text="Обзор…",
            style="Action.TButton",
            command=self.choose_db_path
        ).grid(row=0, column=1, sticky="e")

        # Параметры шифрования
        crypto_frame = ttk.LabelFrame(content_frame, text="Параметры шифрования (заглушка)", padding=20)
        crypto_frame.grid(row=4, column=0, sticky="ew", pady=(0, 15))

        ttk.Label(
            crypto_frame,
            text="В следующих спринтах здесь будет выбор алгоритма,\nколичества итераций, типа соли и других настроек",
            justify="center",
            style="Normal.TLabel"
        ).grid(row=0, column=0, pady=25)

        # Нижний контейнер с кнопками (фиксированный)
        button_frame = ttk.Frame(main_container)
        button_frame.grid(row=1, column=0, sticky="ew", pady=(20, 0))
        button_frame.grid_columnconfigure(0, weight=1)
        button_frame.grid_columnconfigure(1, weight=1)

        ttk.Button(
            button_frame,
            text="Отмена",
            style="Action.TButton",
            command=self.cancel
        ).grid(row=0, column=0, padx=(0, 10), sticky="e")

        ttk.Button(
            button_frame,
            text="Завершить настройку",
            style="Accent.TButton",
            command=self.try_save
        ).grid(row=0, column=1, padx=(10, 0), sticky="w")

    def choose_db_path(self):
        path = filedialog.asksaveasfilename(
            defaultextension=".db",
            filetypes=[("SQLite Database", "*.db"), ("All Files", "*.*")],
            title="Выберите место для базы данных"
        )
        if path:
            self.db_path.set(path)

    def try_save(self):
        password1 = self.password1.get()
        password2 = self.password2.get()

        if password1 != password2:
            messagebox.showerror("Ошибка", "Пароли не совпадают")
            return

        if not password1:
            messagebox.showerror("Ошибка", "Пароль не может быть пустым")
            return

        db_path = self.db_path.get()
        if not db_path:
            messagebox.showerror("Ошибка", "Укажите путь к базе данных")
            return

        try:
            self.auth.register(password1)
            self.completed = True
            self.destroy()
        except Exception as e:
            messagebox.showerror("Ошибка", str(e))

    def cancel(self):
        self.completed = False
        self.destroy()