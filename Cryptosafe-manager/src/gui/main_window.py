import tkinter as tk

from src.core.events import EventBus, ENTRY_ADDED
from src.database.audit_logger import AuditLogger


def main():
    # 1️⃣ Создаём ЕДИНЫЙ EventBus для всего приложения
    event_bus = EventBus()

    # 2️⃣ Подключаем audit log (он сам подпишется на события)
    audit_logger = AuditLogger(event_bus)

    # 3️⃣ Создаём главное окно
    root = tk.Tk()
    root.title("CryptoSafe Manager")
    root.geometry("800x600")

    label = tk.Label(root, text="CryptoSafe Manager — Sprint 1")
    label.pack(pady=20)

    # 4️⃣ Кнопка для теста EventBus
    def add_entry_test():
        data = {
            "title": "Test entry",
            "username": "test_user"
        }
        event_bus.publish(ENTRY_ADDED, data)

    test_button = tk.Button(
        root,
        text="Add test entry",
        command=add_entry_test
    )
    test_button.pack(pady=10)

    root.mainloop()


if __name__ == "__main__":
    main()
