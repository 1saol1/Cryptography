import sys
import os
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout,
                             QHBoxLayout, QPushButton, QMessageBox, QFileDialog,
                             QMenuBar, QMenu, QStatusBar, QLabel, QDialog,
                             QLineEdit, QDialogButtonBox, QFormLayout, QToolBar)
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QAction, QIcon

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, BASE_DIR)

from src.core.events import EventBus, ENTRY_ADDED
from src.database.audit_logger import AuditLogger
from src.database.db import Database
from src.gui.widgets.secure_table import SecureTable
from src.gui.widgets.audit_log_viewer import AuditLogViewer
from src.gui.widgets.settings_dialog import SettingsDialog
from src.gui.widgets.setup_window import SetupWindow
from src.gui.widgets.change_password_dialog import ChangePasswordDialog
from src.core.crypto.authentication import AuthenticationService
from src.core.crypto.key_manager import KeyManager
from src.core.crypto.abstract import VaultEncryptionService
from src.core.state_manager import StateManager


class LoginDialog(QDialog):
    def __init__(self, parent, auth, session):
        super().__init__(parent)
        self.auth = auth
        self.session = session
        self.success = False

        self.setWindowTitle("Вход в CryptoSafe")
        self.setModal(True)
        self.setFixedSize(340, 200)

        layout = QVBoxLayout(self)

        label = QLabel("Введите мастер-пароль")
        label.setStyleSheet("font-size: 12px; font-weight: bold;")
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(label)

        self.password_input = QLineEdit()
        self.password_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.password_input.setPlaceholderText("Введите пароль")
        layout.addWidget(self.password_input)

        button_layout = QHBoxLayout()
        button_layout.addStretch()

        login_btn = QPushButton("Войти")
        login_btn.clicked.connect(self.try_login)
        login_btn.setDefault(True)
        button_layout.addWidget(login_btn)

        cancel_btn = QPushButton("Отмена")
        cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(cancel_btn)

        layout.addLayout(button_layout)

        self.password_input.returnPressed.connect(self.try_login)

    def try_login(self):
        password = self.password_input.text()
        if not password:
            QMessageBox.critical(self, "Ошибка", "Пароль не может быть пустым")
            return

        key = self.auth.login(password)
        if key:
            self.session.start_session(key)
            self.success = True
            self.accept()
        else:
            QMessageBox.critical(self, "Ошибка", "Неверный мастер-пароль")
            self.password_input.clear()
            self.password_input.setFocus()


class AddEntryDialog(QDialog):
    def __init__(self, parent, encryption_service):
        super().__init__(parent)
        self.encryption_service = encryption_service
        self.result_data = None

        self.setWindowTitle("Добавить запись")
        self.setModal(True)
        self.setFixedSize(450, 350)

        layout = QFormLayout(self)
        layout.setSpacing(15)

        self.title_input = QLineEdit()
        self.title_input.setPlaceholderText("Обязательное поле")
        layout.addRow("Название:*", self.title_input)

        self.username_input = QLineEdit()
        self.username_input.setPlaceholderText("user@example.com")
        layout.addRow("Логин/Email:", self.username_input)

        self.password_input = QLineEdit()
        self.password_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.password_input.setPlaceholderText("••••••••")
        layout.addRow("Пароль:", self.password_input)

        self.url_input = QLineEdit()
        self.url_input.setPlaceholderText("https://")
        layout.addRow("URL/Адрес:", self.url_input)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok |
            QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        ok_btn = buttons.button(QDialogButtonBox.StandardButton.Ok)
        ok_btn.setText("Сохранить")

        cancel_btn = buttons.button(QDialogButtonBox.StandardButton.Cancel)
        cancel_btn.setText("Отмена")

        layout.addRow(buttons)

        self.title_input.setFocus()

    def accept(self):
        title = self.title_input.text().strip()
        if not title:
            QMessageBox.warning(self, "Внимание", "Название — обязательное поле")
            return

        self.result_data = {
            'title': title,
            'username': self.username_input.text().strip(),
            'password': self.password_input.text().strip(),
            'url': self.url_input.text().strip()
        }
        super().accept()


class CryptoSafeApp(QMainWindow):
    def __init__(self, state, auth):
        super().__init__()
        self.state = state
        self.auth = auth

        self.setWindowTitle("CryptoSafe Manager")
        self.setGeometry(100, 100, 960, 620)
        self.setMinimumSize(800, 500)

        self.center_window()

        self.event_bus = EventBus()
        self.audit_logger = AuditLogger(self.event_bus)

        db_path = os.path.join(BASE_DIR, "src", "database", "cryptosafe.db")
        self.db = Database(db_path)
        self.db.initialize()

        self.key_manager = KeyManager()

        encryption_key = self.state.get_key()
        if encryption_key:
            self.key_manager.cache_key(encryption_key)
            print("✓ Ключ шифрования закэширован в KeyManager")
        else:
            QMessageBox.critical(self, "Ошибка", "Не удалось получить ключ шифрования")
            sys.exit(1)

        self.encryption_service = VaultEncryptionService(self.key_manager)

        self.create_menu()
        self.create_main_table()
        self.create_toolbar()
        self.create_status_bar()

        self.event_bus.subscribe(ENTRY_ADDED, self.on_entry_added)

        self.timer = QTimer()
        self.timer.timeout.connect(self.check_session_timeout)
        self.timer.start(60000)

    def center_window(self):
        screen = QApplication.primaryScreen().geometry()
        x = (screen.width() - self.width()) // 2
        y = (screen.height() - self.height()) // 2
        self.move(x, y)

    def check_session_timeout(self):
        if not self.state.is_active():
            self.status_bar.showMessage("Сессия истекла. Требуется повторный вход")
            QMessageBox.information(self, "Сессия истекла",
                                    "Время сессии истекло. Пожалуйста, войдите снова.")
            self.close()

    def closeEvent(self, event):
        print("Завершение работы приложения")
        self.state.end_session()
        self.key_manager.clear_cache()
        self.db.close()
        event.accept()

    def create_menu(self):
        menubar = self.menuBar()

        file_menu = menubar.addMenu("Файл")
        new_action = QAction("Создать", self)
        new_action.triggered.connect(self.new_database)
        file_menu.addAction(new_action)
        open_action = QAction("Открыть", self)
        open_action.triggered.connect(self.open_database)
        file_menu.addAction(open_action)
        file_menu.addSeparator()
        backup_action = QAction("Резервная копия", self)
        backup_action.triggered.connect(self.create_backup)
        file_menu.addAction(backup_action)
        file_menu.addSeparator()
        exit_action = QAction("Выход", self)
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)

        edit_menu = menubar.addMenu("Правка")
        add_action = QAction("Добавить", self)
        add_action.triggered.connect(self.open_add_dialog)
        edit_menu.addAction(add_action)
        edit_action = QAction("Изменить", self)
        edit_action.triggered.connect(self.edit_selected)
        edit_menu.addAction(edit_action)
        delete_action = QAction("Удалить", self)
        delete_action.triggered.connect(self.delete_selected)
        edit_menu.addAction(delete_action)
        edit_menu.addSeparator()
        change_password_action = QAction("Сменить мастер-пароль", self)
        change_password_action.triggered.connect(self.open_change_password)
        edit_menu.addAction(change_password_action)

        view_menu = menubar.addMenu("Вид")
        logs_action = QAction("Логи", self)
        logs_action.triggered.connect(self.open_audit_logs)
        view_menu.addAction(logs_action)
        settings_action = QAction("Настройки", self)
        settings_action.triggered.connect(self.open_settings)
        view_menu.addAction(settings_action)

        help_menu = menubar.addMenu("Справка")
        about_action = QAction("О программе", self)
        about_action.triggered.connect(self.show_about)
        help_menu.addAction(about_action)

    def create_toolbar(self):
        toolbar = QToolBar("Инструменты")
        toolbar.setMovable(False)
        self.addToolBar(toolbar)

        add_action = QAction("Добавить", self)
        add_action.triggered.connect(self.open_add_dialog)
        toolbar.addAction(add_action)

        edit_action = QAction("Изменить", self)
        edit_action.triggered.connect(self.edit_selected)
        toolbar.addAction(edit_action)

        delete_action = QAction("Удалить", self)
        delete_action.triggered.connect(self.delete_selected)
        toolbar.addAction(delete_action)

        toolbar.addSeparator()

        change_password_action = QAction("Сменить пароль", self)
        change_password_action.triggered.connect(self.open_change_password)
        toolbar.addAction(change_password_action)

    def create_main_table(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        layout = QVBoxLayout(central_widget)
        layout.setContentsMargins(10, 10, 10, 10)

        self.table = SecureTable()
        layout.addWidget(self.table)

        self.table.add_entry("Google", "user@gmail.com", "https://accounts.google.com")
        self.table.add_entry("GitHub", "username", "https://github.com")
        self.table.add_entry("Localhost", "admin", "http://localhost")

    def create_status_bar(self):
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)

        session_info = self.state.get_session_info()
        if session_info['login_time']:
            import time
            login_time_str = time.ctime(session_info['login_time'])
            self.status_bar.showMessage(f"Готово | Сессия активна | Вход: {login_time_str}")
        else:
            self.status_bar.showMessage("Готово | Сессия активна")

    def new_database(self):
        QMessageBox.information(self, "Создать",
                                "Функция создания новой базы данных\n(будет реализована в следующих спринтах)")

    def open_database(self):
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Открыть базу данных",
            "",
            "SQLite Database (*.db);;All Files (*.*)"
        )
        if path:
            QMessageBox.information(self, "Открыть",
                                    f"Открыта база: {path}\n(реализация в следующих спринтах)")

    def create_backup(self):
        QMessageBox.information(self, "Резервная копия",
                                "Создание резервной копии\n(будет реализовано в спринте 8)")

    def edit_selected(self):
        selected = self.table.get_selected_values()
        if not selected:
            QMessageBox.information(self, "Информация", "Выберите запись для редактирования")
            return

        if not self.state.is_active():
            QMessageBox.critical(self, "Ошибка", "Сессия не активна. Выполните вход заново.")
            return

        QMessageBox.information(self, "Редактирование",
                                f"Редактирование записи: {selected[0]}\n(будет реализовано позже)")

        self.state.update_activity()
        self.key_manager._update_activity()

    def delete_selected(self):
        selected = self.table.selectedItems()
        if not selected:
            QMessageBox.information(self, "Информация", "Выберите запись для удаления")
            return

        if not self.state.is_active():
            QMessageBox.critical(self, "Ошибка", "Сессия не активна. Выполните вход заново.")
            return

        reply = QMessageBox.question(self, "Подтверждение",
                                     f"Удалить выбранные записи?",
                                     QMessageBox.StandardButton.Yes |
                                     QMessageBox.StandardButton.No)

        if reply == QMessageBox.StandardButton.Yes:
            self.table.delete_selected()
            self.state.update_activity()
            self.key_manager._update_activity()
            self.status_bar.showMessage("Записи удалены")

    def open_add_dialog(self):
        if not self.state.is_active():
            QMessageBox.critical(self, "Ошибка", "Сессия не активна. Выполните вход заново.")
            return

        dialog = AddEntryDialog(self, self.encryption_service)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            data = dialog.result_data

            try:
                if data['password']:
                    encrypted_pwd = self.encryption_service.encrypt(data['password'].encode())
                    print(f"Пароль зашифрован, длина: {len(encrypted_pwd)} байт")

                self.table.add_entry(data['title'], data['username'], data['url'])

                self.event_bus.publish(ENTRY_ADDED, {
                    "title": data['title'],
                    "username": data['username'],
                    "url": data['url']
                })

                self.state.update_activity()
                self.key_manager._update_activity()

            except ValueError as e:
                QMessageBox.critical(self, "Ошибка", f"Не удалось зашифровать данные: {e}")
            except Exception as e:
                QMessageBox.critical(self, "Ошибка", f"Ошибка при сохранении: {e}")

    def open_change_password(self):
        if not self.state.is_active():
            QMessageBox.critical(self, "Ошибка", "Сессия не активна. Выполните вход заново.")
            return

        dialog = ChangePasswordDialog(self, self.auth)
        if dialog.exec() == QDialog.DialogCode.Accepted and dialog.success:
            QMessageBox.information(self, "Успех", "Пароль успешно изменен!")

    def open_audit_logs(self):
        viewer = AuditLogViewer(self)
        viewer.exec()

    def open_settings(self):
        dialog = SettingsDialog(self)
        dialog.exec()

    def show_about(self):
        QMessageBox.information(
            self,
            "О программе",
            "CryptoSafe Manager\n\n"
            "Версия: 2.0 (Спринт 2)\n"
            "Локальный менеджер паролей с шифрованием\n\n"
            "Реализовано:\n"
            "• Аутентификация по мастер-паролю\n"
            "• Argon2id и PBKDF2\n"
            "• Безопасное кэширование ключей\n"
            "• Система миграций БД\n"
            "• Смена мастер-пароля (CHANGE-1)\n\n"
            f"База данных:\n{os.path.join(BASE_DIR, 'src', 'database', 'cryptosafe.db')}"
        )

    def on_entry_added(self, data):
        self.status_bar.showMessage(f"Добавлена запись: {data.get('title', 'без названия')}")
        self.state.update_activity()
        self.key_manager._update_activity()


def main():
    print("CryptoSafe Manager - Запуск")

    app = QApplication(sys.argv)

    db_path = os.path.join(BASE_DIR, "src", "database", "cryptosafe.db")
    print(f"База данных: {db_path}")

    os.makedirs(os.path.dirname(db_path), exist_ok=True)

    db = Database(db_path)
    db.initialize()

    auth = AuthenticationService(db_path)
    state = StateManager()

    if not auth.is_initialized():
        print("Первый запуск - окно регистрации")
        setup = SetupWindow(None, auth)
        if setup.exec() != QDialog.DialogCode.Accepted or not setup.completed:
            print("Регистрация отменена")
            sys.exit(0)
        print("Регистрация завершена")

    print("Окно входа...")
    login_dialog = LoginDialog(None, auth, state)
    if login_dialog.exec() != QDialog.DialogCode.Accepted or not login_dialog.success:
        print("Вход не выполнен")
        sys.exit(0)

    print("Вход выполнен успешно")
    print("Создание главного окна...")

    window = CryptoSafeApp(state, auth)
    window.show()

    print("Запуск главного цикла...")
    sys.exit(app.exec())


if __name__ == "__main__":
    main()