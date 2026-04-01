import sys
import os
from datetime import datetime
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout,
                             QHBoxLayout, QPushButton, QMessageBox, QFileDialog,
                             QStatusBar, QLabel, QDialog,
                             QLineEdit, QToolBar)
from PyQt6.QtCore import Qt, QTimer, QEvent
from PyQt6.QtGui import QAction, QKeySequence

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, BASE_DIR)

from src.core.events import EventBus, ENTRY_ADDED, CLIPBOARD_COPIED, CLIPBOARD_CLEARED
from src.database.audit_logger import AuditLogger
from src.database.db import Database
from src.gui.widgets.secure_table import SecureTable
from src.gui.widgets.audit_log_viewer import AuditLogViewer
from src.gui.widgets.settings_dialog import SettingsDialog
from src.gui.widgets.setup_window import SetupWindow
from src.gui.widgets.change_password_dialog import ChangePasswordDialog
from src.gui.widgets.filter_dialog import FilterDialog
from src.core.crypto.authentication import AuthenticationService
from src.core.crypto.key_manager import KeyManager
from src.core.crypto.abstract import VaultEncryptionService
from src.core.state_manager import StateManager
from src.core.config import ConfigManager

from src.core.clipboard.clipboard_service import ClipboardService
from src.core.clipboard.clipboard_monitor import ClipboardMonitor
from src.core.clipboard.clipboard_config import ClipboardSettings
from src.core.events import (CLIPBOARD_SUSPICIOUS_ACCESS,
                             CLIPBOARD_PROTECTION_ENABLED)

from src.core.vault.entry_manager import EntryManager
from src.gui.widgets.entry_dialog import EntryDialog


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


class CryptoSafeApp(QMainWindow):
    def __init__(self, state, auth):
        super().__init__()
        self.state = state
        self.auth = auth
        self.current_filters = {}
        self._saved_entry_ids = []

        self.setWindowTitle("CryptoSafe Manager")
        self.setGeometry(100, 100, 960, 620)
        self.setMinimumSize(800, 500)

        self.center_window()

        self.event_bus = EventBus()
        self.audit_logger = AuditLogger(self.event_bus)

        db_path = os.path.join(BASE_DIR, "src", "database", "cryptosafe.db")
        self.db = Database(db_path)
        self.db.initialize()

        self.config_manager = ConfigManager(db_path)

        self.key_manager = KeyManager()

        encryption_key = self.state.get_key()
        if encryption_key:
            self.key_manager.cache_key(encryption_key)
            print("Ключ шифрования закэширован в KeyManager")
        else:
            QMessageBox.critical(self, "Ошибка", "Не удалось получить ключ шифрования")
            sys.exit(1)

        self.encryption_service = VaultEncryptionService(self.key_manager)

        self.entry_manager = EntryManager(
            db_connection=self.db,
            key_manager=self.key_manager,
            auth_service=self.auth,
            event_system=self.event_bus
        )

        self.create_menu()
        self.create_main_table()
        self.create_toolbar()
        self.create_status_bar()

        self.load_entries()

        self.event_bus.subscribe(ENTRY_ADDED, self.on_entry_added)

        self.timer = QTimer()
        self.timer.timeout.connect(self.check_session_timeout)
        self.timer.start(60000)

        self.clipboard_settings = ClipboardSettings(self.config_manager)

        self.clipboard_settings.add_default_settings()

        self.clipboard_service = ClipboardService(
            event_bus=self.event_bus,
            state_manager=self.state,
            config_manager=self.config_manager
        )

        self.clipboard_monitor = ClipboardMonitor(
            clipboard_service=self.clipboard_service,
            event_bus=self.event_bus,
            config_manager=self.config_manager
        )

        self._load_clipboard_settings()

        self.event_bus.subscribe(CLIPBOARD_COPIED, self.on_clipboard_copied_event)
        self.event_bus.subscribe(CLIPBOARD_CLEARED, self.on_clipboard_cleared_event)
        self.event_bus.subscribe(CLIPBOARD_SUSPICIOUS_ACCESS, self.on_suspicious_access)
        self.event_bus.subscribe(CLIPBOARD_PROTECTION_ENABLED, self.on_protection_enabled)

        self.clipboard_monitor.start_monitoring()

        print("[APP] Сервис буфера обмена инициализирован")

    def _load_clipboard_settings(self):
        try:
            timeout = self.clipboard_settings.timeout
            self.clipboard_service.set_timeout(timeout)

            security_level = self.clipboard_settings.security_level
            self.clipboard_service.set_security_level(security_level)

            print(f"[APP] Загружены настройки буфера: таймаут={timeout}с, уровень={security_level}")
        except Exception as e:
            print(f"[APP] Ошибка загрузки настроек буфера: {e}")

    def copy_to_clipboard(self, text: str, data_type: str = "text", entry_id: str = None):
        print(f"[DEBUG] main_window.copy_to_clipboard вызван: type={data_type}, text={text[:20]}...")

        if not self.state.is_active():
            QMessageBox.warning(self, "Доступ запрещен", "Хранилище заблокировано. Выполните вход.")
            return False

        if not text:
            return False

        success = self.clipboard_service.copy_to_clipboard(
            data=text,
            data_type=data_type,
            source_entry_id=entry_id
        )

        print(f"[DEBUG] Результат копирования: {success}")

        if success:
            self.state.update_activity()

        return success

    def manual_clear_clipboard(self):
        if hasattr(self, 'clipboard_service'):
            self.clipboard_service.clear_clipboard(manual=True)
            self.status_bar.showMessage("Буфер обмена очищен вручную")
            print("[APP] Ручная очистка буфера")
        else:
            print("[APP] Сервис буфера не доступен")

    def changeEvent(self, event):
        if event.type() == QEvent.Type.WindowStateChange:
            if self.windowState() & Qt.WindowState.WindowMinimized:
                print("Окно свернуто - очищаем ключи и данные")
                self.key_manager.on_app_minimize()
                self._clear_decrypted_data()
                self.status_bar.showMessage("Приложение свернуто - данные защищены")
            else:
                print("Окно развернуто - восстанавливаем данные")
                self._restore_decrypted_data()
        super().changeEvent(event)

    def _clear_decrypted_data(self):
        self._saved_entry_ids = []
        for i in range(self.table.topLevelItemCount()):
            item = self.table.topLevelItem(i)
            for idx, it in enumerate(self.table._items):
                if it is item:
                    self._saved_entry_ids.append(self.table._item_ids[idx])
                    break

        self.table.clear_all()
        self.status_bar.showMessage("Данные защищены - окно свернуто")

    def _restore_decrypted_data(self):
        if self._saved_entry_ids:
            try:
                entries = []
                for entry_id in self._saved_entry_ids:
                    try:
                        entry = self.entry_manager.get_entry(entry_id)
                        entries.append(entry)
                    except Exception as e:
                        print(f"Ошибка загрузки {entry_id}: {e}")

                self._display_entries(entries)
                self.status_bar.showMessage(f"Восстановлено {len(entries)} записей")
                self._saved_entry_ids = []
            except Exception as e:
                print(f"Ошибка восстановления: {e}")
                self.load_entries()
        else:
            self.load_entries()

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

        if hasattr(self, 'clipboard_monitor'):
            self.clipboard_monitor.stop_monitoring()
        if hasattr(self, 'clipboard_service'):
            self.clipboard_service.shutdown()

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

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Поиск... (title:работа, username:ivan)")
        self.search_input.setMinimumWidth(250)
        self.search_input.textChanged.connect(self.on_search_text_changed)
        toolbar.addWidget(self.search_input)

        clear_search_btn = QPushButton("✖")
        clear_search_btn.setFixedSize(25, 25)
        clear_search_btn.setToolTip("Очистить поиск")
        clear_search_btn.clicked.connect(self.clear_search)
        toolbar.addWidget(clear_search_btn)

        toolbar.addSeparator()

        filter_btn = QPushButton("Фильтры")
        filter_btn.setToolTip("Открыть диалог фильтров")
        filter_btn.clicked.connect(self.open_filter_dialog)
        toolbar.addWidget(filter_btn)

        clear_filter_btn = QPushButton("✖ Фильтры")
        clear_filter_btn.setToolTip("Очистить все фильтры")
        clear_filter_btn.clicked.connect(self.clear_filters)
        toolbar.addWidget(clear_filter_btn)

        toolbar.addSeparator()

        self.show_password_action = QAction("Показать пароли", self)
        self.show_password_action.setCheckable(True)
        self.show_password_action.setChecked(False)
        self.show_password_action.triggered.connect(self.toggle_show_passwords)
        self.show_password_action.setShortcut(QKeySequence("Ctrl+Shift+P"))
        toolbar.addAction(self.show_password_action)

        toolbar.addSeparator()

        change_password_action = QAction("Сменить пароль", self)
        change_password_action.triggered.connect(self.open_change_password)
        toolbar.addAction(change_password_action)

        toolbar.addSeparator()

        clear_clipboard_btn = QPushButton("🗑️ Очистить буфер")
        clear_clipboard_btn.setToolTip("Очистить буфер обмена")
        clear_clipboard_btn.clicked.connect(self.manual_clear_clipboard)
        toolbar.addWidget(clear_clipboard_btn)

    def create_main_table(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        layout = QVBoxLayout(central_widget)
        layout.setContentsMargins(10, 10, 10, 10)

        self.table = SecureTable()
        layout.addWidget(self.table)

        self.table.item_double_clicked.connect(self.on_entry_double_clicked)
        self.table.item_delete_requested.connect(self.on_delete_requested)

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

    def load_entries(self):
        self.table.clear_all()
        self.search_input.clear()
        self.current_filters = {}

        try:
            entries = self.entry_manager.get_all_entries()
            for entry in entries:
                self.table.add_entry(
                    entry_id=entry.get('id', ''),
                    title=entry.get('title', ''),
                    username=entry.get('username', ''),
                    password=entry.get('password', ''),
                    url=entry.get('url', ''),
                    updated_at=entry.get('updated_at', '')[:10]
                )
            self.status_bar.showMessage(f"Загружено {len(entries)} записей")
        except Exception as e:
            print(f"Ошибка загрузки записей: {e}")
            self.status_bar.showMessage("Ошибка загрузки записей")

    def on_search_text_changed(self, text: str):
        if not text.strip():
            if self.current_filters:
                self.apply_filters()
            else:
                self.load_entries()
        else:
            self.search_entries(text)

    def search_entries(self, query: str):
        try:
            if self.current_filters:
                entries = self.entry_manager.get_filtered_entries(self.current_filters)
            else:
                entries = self.entry_manager.search_entries(query)

            self._display_entries(entries)
            self.status_bar.showMessage(f"Найдено {len(entries)} записей")

        except Exception as e:
            print(f"Ошибка поиска: {e}")
            self.status_bar.showMessage("Ошибка поиска")

    def clear_search(self):
        self.search_input.clear()
        if self.current_filters:
            self.apply_filters()
        else:
            self.load_entries()

    def open_filter_dialog(self):
        dialog = FilterDialog(self, self.entry_manager)

        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.current_filters = dialog.get_filters()
            self.apply_filters()

    def apply_filters(self):
        try:
            if self.current_filters:
                entries = self.entry_manager.get_filtered_entries(self.current_filters)
                self._display_entries(entries)

                filter_count = len(self.current_filters)
                self.status_bar.showMessage(f"Фильтры активны ({filter_count}) | Найдено {len(entries)} записей")
            else:
                self.load_entries()
                self.status_bar.showMessage("Фильтры отключены")

        except Exception as e:
            print(f"Ошибка применения фильтров: {e}")
            self.status_bar.showMessage("Ошибка применения фильтров")

    def clear_filters(self):
        self.current_filters = {}
        self.load_entries()
        self.status_bar.showMessage("Фильтры очищены")

    def _display_entries(self, entries):
        self.table.clear_all()
        for entry in entries:
            self.table.add_entry(
                entry_id=entry.get('id', ''),
                title=entry.get('title', ''),
                username=entry.get('username', ''),
                password=entry.get('password', ''),
                url=entry.get('url', ''),
                updated_at=entry.get('updated_at', '')[:10]
            )

    def toggle_show_passwords(self):
        show = self.show_password_action.isChecked()
        self.table.set_show_all_passwords(show)
        if show:
            self.show_password_action.setText("Скрыть пароли")
            self.status_bar.showMessage("Пароли отображаются")
        else:
            self.show_password_action.setText("Показать пароли")
            self.status_bar.showMessage("Пароли скрыты")

    def on_entry_double_clicked(self, data):
        entry_id = data.get('id')
        if entry_id:
            self.edit_entry(entry_id)

    def on_delete_requested(self, data):
        entry_id = data.get('id')
        if not entry_id:
            return
        self.delete_single_entry(entry_id)

    def delete_single_entry(self, entry_id: str):
        if not self.state.is_active():
            QMessageBox.critical(self, "Ошибка", "Сессия не активна.")
            return

        reply = QMessageBox.question(
            self,
            "Подтверждение",
            "Удалить эту запись?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )

        if reply == QMessageBox.StandardButton.Yes:
            try:
                self.entry_manager.delete_entry(entry_id, soft_delete=True)
                self.table.remove_entry(entry_id)
                self.status_bar.showMessage("Запись удалена")
                self.state.update_activity()
            except Exception as e:
                QMessageBox.critical(self, "Ошибка", f"Не удалось удалить запись")

    def edit_entry(self, entry_id: str):
        if not self.state.is_active():
            QMessageBox.critical(self, "Ошибка", "Сессия не активна.")
            return

        try:
            current_data = self.entry_manager.get_entry(entry_id)

            dialog = EntryDialog(self, self.entry_manager, edit_mode=True, existing_data=current_data)

            if dialog.exec() == QDialog.DialogCode.Accepted:
                new_data = dialog.get_data()

                updated = self.entry_manager.update_entry(entry_id, new_data)

                self.table.update_entry(
                    entry_id=entry_id,
                    title=updated.get('title', ''),
                    username=updated.get('username', ''),
                    password=updated.get('password', ''),
                    url=updated.get('url', ''),
                    updated_at=updated.get('updated_at', '')[:10]
                )

                self.status_bar.showMessage(f"Запись обновлена: {updated.get('title')}")
                self.state.update_activity()

        except Exception as e:
            QMessageBox.critical(self, "Ошибка", f"Ошибка при редактировании")

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
        selected_ids = self.table.get_selected_entries()
        if not selected_ids:
            QMessageBox.information(self, "Информация", "Выберите запись для редактирования")
            return

        if not self.state.is_active():
            QMessageBox.critical(self, "Ошибка", "Сессия не активна.")
            return

        self.edit_entry(selected_ids[0])

    def delete_selected(self):
        selected_ids = self.table.get_selected_entries()
        if not selected_ids:
            QMessageBox.information(self, "Информация", "Выберите записи для удаления")
            return

        if not self.state.is_active():
            QMessageBox.critical(self, "Ошибка", "Сессия не активна.")
            return

        count = len(selected_ids)
        reply = QMessageBox.question(
            self,
            "Подтверждение удаления",
            f"Удалить выбранные записи ({count} шт.)?\n\nЭто действие нельзя отменить.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )

        if reply != QMessageBox.StandardButton.Yes:
            return

        ids_to_delete = list(selected_ids)

        deleted_count = 0
        try:
            for entry_id in ids_to_delete:
                self.entry_manager.delete_entry(entry_id, soft_delete=True)
                deleted_count += 1

            self.table.remove_entries(ids_to_delete)

            self.status_bar.showMessage(f"Успешно удалено {deleted_count} записей")
            self.state.update_activity()

        except Exception as e:
            QMessageBox.critical(self, "Ошибка", f"Не удалось удалить выбранные записи")

    def open_add_dialog(self):
        if not self.state.is_active():
            QMessageBox.critical(self, "Ошибка", "Сессия не активна. Выполните вход заново.")
            return

        dialog = EntryDialog(self, self.entry_manager, edit_mode=False)

        if dialog.exec() == QDialog.DialogCode.Accepted:
            data = dialog.get_data()

            try:
                entry_id = self.entry_manager.create_entry(data)

                self.table.add_entry(
                    entry_id=entry_id,
                    title=data['title'],
                    username=data.get('username', ''),
                    password=data.get('password', ''),
                    url=data.get('url', ''),
                    updated_at=datetime.now().strftime("%Y-%m-%d")
                )

                self.status_bar.showMessage(f"Запись добавлена: {data['title']}")
                self.state.update_activity()

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
            "Версия: 4.0 (Спринт 4)\n"
            "Локальный менеджер паролей с шифрованием\n\n"
            "Реализовано в Спринте 4:\n"
            "• Безопасный буфер обмена с авто-очисткой\n"
            "• Платформозависимые адаптеры (Windows/Mac/Linux)\n"
            "• Мониторинг и защита от перехвата\n"
            "• Шифрование данных в памяти\n\n"
            f"База данных:\n{os.path.join(BASE_DIR, 'src', 'database', 'cryptosafe.db')}"
        )

    def on_entry_added(self, data):
        self.status_bar.showMessage(f"Добавлена запись: {data.get('title', 'без названия')}")
        self.state.update_activity()

    def on_clipboard_copied_event(self, data):
        if data:
            data_type = data.get('data_type', 'текст')
            timeout = data.get('timeout', 30)
            self.status_bar.showMessage(
                f"Скопирован {data_type} в буфер обмена (очистится через {timeout} сек)"
            )

    def on_clipboard_cleared_event(self, data):
        reason = data.get('reason', 'programmatic') if data else 'programmatic'
        if reason == 'timeout':
            self.status_bar.showMessage("Буфер обмена автоматически очищен")
        elif reason == 'manual':
            self.status_bar.showMessage("Буфер обмена очищен пользователем")
        else:
            self.status_bar.showMessage("Буфер обмена очищен")

    def on_suspicious_access(self, data):
        if data:
            access_type = data.get('type', 'unknown')
            count = data.get('suspicious_count', 0)

            if access_type == 'external_change':
                self.status_bar.showMessage(
                    f"ВНИМАНИЕ: Обнаружено внешнее изменение буфера обмена! (счетчик: {count})"
                )
                print(f"Подозрительная активность: внешнее изменение, счетчик={count}")

            elif access_type == 'read_detected':
                self.status_bar.showMessage(
                    f"ВНИМАНИЕ: Обнаружено чтение буфера обмена! (счетчик: {count})"
                )
                print(f"[APP] Подозрительная активность: чтение буфера, счетчик={count}")

            threshold = self.clipboard_settings.suspicious_threshold if hasattr(self, 'clipboard_settings') else 3
            if count >= threshold // 2 and count < threshold:
                QMessageBox.warning(
                    self,
                    "Предупреждение о безопасности",
                    f"Обнаружена подозрительная активность с буфером обмена!\n\n"
                    f"Тип: {'внешнее изменение' if access_type == 'external_change' else 'чтение буфера'}\n"
                    f"Счетчик подозрений: {count}/{threshold}\n\n"
                    f"При достижении {threshold} подозрений будет активирован режим защиты."
                )

    def on_protection_enabled(self, data):
        self.status_bar.showMessage("РЕЖИМ ЗАЩИТЫ АКТИВИРОВАН! Буфер очищен, таймаут = 5 сек")

        if data:
            count = data.get('suspicious_count', 0)
            print(f"[APP] Режим защиты активирован, подозрений: {count}")

        QMessageBox.warning(
            self,
            "Режим защиты активирован",
            "РЕЖИМ ЗАЩИТЫ БУФЕРА ОБМЕНА АКТИВИРОВАН 🔒\n\n"
            "Обнаружена подозрительная активность с буфером обмена.\n\n"
            "Принятые меры:\n"
            "• Буфер обмена немедленно очищен\n"
            "• Таймаут авто-очистки установлен на 5 секунд\n"
            "• Все новые копирования будут очищаться через 5 секунд\n\n"
            "Будьте внимательны при копировании паролей!"
        )


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
    state.key_manager = window.key_manager

    window.show()

    print("Запуск главного цикла...")
    sys.exit(app.exec())


if __name__ == "__main__":
    main()