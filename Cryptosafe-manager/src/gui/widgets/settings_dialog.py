import tkinter as tk
from tkinter import ttk, messagebox


class SettingsDialog(tk.Toplevel):
    def __init__(self, parent):
        super().__init__(parent)
        self.title("Настройки CryptoSafe Manager")
        self.geometry("620x520")
        self.resizable(False, False)

        self.create_notebook()
        self.center_on_screen()

    def center_on_screen(self):
        self.update_idletasks()
        w = self.winfo_width()
        h = self.winfo_height()
        x = (self.winfo_screenwidth() // 2) - (w // 2)
        y = (self.winfo_screenheight() // 2) - (h // 2)
        self.geometry(f'{w}x{h}+{x}+{y}')

    def create_notebook(self):
        notebook = ttk.Notebook(self)
        notebook.pack(fill="both", expand=True, padx=10, pady=10)

        # Вкладка 1 — Безопасность
        sec = ttk.Frame(notebook, padding=15)
        notebook.add(sec, text="Безопасность")

        ttk.Label(sec, text="Очистка буфера обмена через (секунды):").grid(row=0, column=0, sticky="w", pady=8)
        self.clip_timeout = ttk.Spinbox(sec, from_=10, to=600, increment=10, width=8)
        self.clip_timeout.grid(row=0, column=1, sticky="w", padx=(10, 0))
        self.clip_timeout.set(90)

        ttk.Label(sec, text="Автоматическая блокировка после (минут):").grid(row=1, column=0, sticky="w", pady=8)
        self.autolock = ttk.Spinbox(sec, from_=1, to=120, increment=5, width=8)
        self.autolock.grid(row=1, column=1, sticky="w", padx=(10, 0))
        self.autolock.set(10)

        ttk.Label(sec, text="(Значения будут сохраняться в следующих спринтах)").grid(
            row=2, column=0, columnspan=2, pady=30, sticky="w")

        # Вкладка 2 — Внешний вид
        appear = ttk.Frame(notebook, padding=15)
        notebook.add(appear, text="Внешний вид")

        ttk.Label(appear, text="Тема оформления:").pack(anchor="w", pady=(10, 5))
        self.theme = tk.StringVar(value="system")
        ttk.Radiobutton(appear, text="Системная", variable=self.theme, value="system").pack(anchor="w", padx=10)
        ttk.Radiobutton(appear, text="Светлая",   variable=self.theme, value="light").pack(anchor="w", padx=10)
        ttk.Radiobutton(appear, text="Тёмная",    variable=self.theme, value="dark").pack(anchor="w", padx=10)

        ttk.Label(appear, text="Язык интерфейса:").pack(anchor="w", pady=(20, 5))
        self.lang = ttk.Combobox(appear, values=["Русский", "English"], state="readonly", width=20)
        self.lang.set("Русский")
        self.lang.pack(anchor="w", padx=10)

        ttk.Label(appear, text="(Применение темы и языка — в следующих спринтах)").pack(anchor="w", pady=30)

        # Вкладка 3 — Дополнительно
        adv = ttk.Frame(notebook, padding=15)
        notebook.add(adv, text="Дополнительно")

        ttk.Button(adv, text="Создать резервную копию хранилища…", state="disabled").pack(fill="x", pady=6)
        ttk.Button(adv, text="Восстановить из резервной копии…",   state="disabled").pack(fill="x", pady=6)
        ttk.Button(adv, text="Экспортировать записи…",             state="disabled").pack(fill="x", pady=6)
        ttk.Button(adv, text="Импортировать записи…",              state="disabled").pack(fill="x", pady=6)

        ttk.Label(adv, text="Функции резервного копирования и импорта/экспорта\n"
                            "будут реализованы в спринтах 6–8", justify="center").pack(pady=40)

        # Нижние кнопки
        btn_frame = ttk.Frame(self)
        btn_frame.pack(pady=15)

        ttk.Button(btn_frame, text="Отмена", command=self.destroy).pack(side="left", padx=12)
        ttk.Button(btn_frame, text="Сохранить", command=self.on_save).pack(side="right", padx=12)

    def on_save(self):
        # Пока просто заглушка — в будущем сохранять в таблицу settings
        messagebox.showinfo(
            "Настройки",
            "Настройки сохранены (заглушка).\nЗначения вступят в силу после реализации в следующих спринтах."
        )
        self.destroy()