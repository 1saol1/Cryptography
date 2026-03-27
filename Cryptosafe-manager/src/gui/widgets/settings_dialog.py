from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QTabWidget, QWidget,
                             QFormLayout, QLabel, QComboBox, QSpinBox,
                             QCheckBox, QPushButton, QHBoxLayout, QGroupBox,
                             QMessageBox)


class SettingsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)

        self.setWindowTitle("Настройки")
        self.setModal(True)
        self.setMinimumWidth(500)
        self.setMinimumHeight(450)

        layout = QVBoxLayout(self)

        self.tab_widget = QTabWidget()

        self.security_tab = self._create_security_tab()
        self.tab_widget.addTab(self.security_tab, "Безопасность")

        self.appearance_tab = self._create_appearance_tab()
        self.tab_widget.addTab(self.appearance_tab, "Внешний вид")

        self.advanced_tab = self._create_advanced_tab()
        self.tab_widget.addTab(self.advanced_tab, "Дополнительно")

        layout.addWidget(self.tab_widget)

        buttons_layout = QHBoxLayout()
        buttons_layout.addStretch()

        save_btn = QPushButton("Сохранить")
        save_btn.clicked.connect(self.save_settings)
        buttons_layout.addWidget(save_btn)

        cancel_btn = QPushButton("Отмена")
        cancel_btn.clicked.connect(self.reject)
        buttons_layout.addWidget(cancel_btn)

        layout.addLayout(buttons_layout)

        self.load_settings()

    def _create_security_tab(self):
        widget = QWidget()
        layout = QFormLayout(widget)
        layout.setSpacing(15)

        auto_lock_group = QGroupBox("Авто-блокировка")
        auto_lock_layout = QFormLayout(auto_lock_group)

        self.auto_lock_timeout = QSpinBox()
        self.auto_lock_timeout.setRange(1, 120)
        self.auto_lock_timeout.setSuffix(" мин")
        self.auto_lock_timeout.setToolTip("Время неактивности до автоматической блокировки")
        auto_lock_layout.addRow("Таймаут авто-блокировки:", self.auto_lock_timeout)

        self.session_timeout = QSpinBox()
        self.session_timeout.setRange(5, 480)
        self.session_timeout.setSuffix(" мин")
        self.session_timeout.setToolTip("Максимальное время сессии")
        auto_lock_layout.addRow("Максимальное время сессии:", self.session_timeout)

        layout.addRow(auto_lock_group)

        clipboard_group = QGroupBox("Буфер обмена")
        clipboard_layout = QFormLayout(clipboard_group)

        self.clipboard_timeout = QSpinBox()
        self.clipboard_timeout.setRange(5, 120)
        self.clipboard_timeout.setSuffix(" сек")
        self.clipboard_timeout.setToolTip("Время через которое пароль автоматически очистится из буфера обмена")
        clipboard_layout.addRow("Авто-очистка буфера:", self.clipboard_timeout)

        self.clipboard_auto_clear = QCheckBox("Автоматически очищать буфер обмена")
        self.clipboard_auto_clear.setChecked(True)
        clipboard_layout.addRow("", self.clipboard_auto_clear)

        layout.addRow(clipboard_group)

        password_group = QGroupBox("Политика паролей")
        password_layout = QFormLayout(password_group)

        self.password_min_length = QSpinBox()
        self.password_min_length.setRange(8, 64)
        self.password_min_length.setSuffix(" символов")
        password_layout.addRow("Минимальная длина пароля:", self.password_min_length)

        self.password_require_upper = QCheckBox("Требовать заглавные буквы (A-Z)")
        self.password_require_upper.setChecked(True)
        password_layout.addRow("", self.password_require_upper)

        self.password_require_lower = QCheckBox("Требовать строчные буквы (a-z)")
        self.password_require_lower.setChecked(True)
        password_layout.addRow("", self.password_require_lower)

        self.password_require_digit = QCheckBox("Требовать цифры (0-9)")
        self.password_require_digit.setChecked(True)
        password_layout.addRow("", self.password_require_digit)

        self.password_require_special = QCheckBox("Требовать спецсимволы (!@#$%^&*)")
        self.password_require_special.setChecked(True)
        password_layout.addRow("", self.password_require_special)

        layout.addRow(password_group)

        return widget

    def _create_appearance_tab(self):
        widget = QWidget()
        layout = QFormLayout(widget)
        layout.setSpacing(15)

        self.theme_combo = QComboBox()
        self.theme_combo.addItems(["Светлая", "Темная", "Системная"])
        layout.addRow("Тема:", self.theme_combo)

        self.language_combo = QComboBox()
        self.language_combo.addItems(["Русский", "English"])
        layout.addRow("Язык:", self.language_combo)

        layout.addRow(QLabel(""))
        layout.addRow(QLabel("Изменение темы и языка требует перезапуска приложения"))

        return widget

    def _create_advanced_tab(self):
        widget = QWidget()
        layout = QFormLayout(widget)
        layout.setSpacing(15)

        generator_group = QGroupBox("Генератор паролей")
        generator_layout = QFormLayout(generator_group)

        self.default_password_length = QSpinBox()
        self.default_password_length.setRange(8, 64)
        self.default_password_length.setSuffix(" символов")
        generator_layout.addRow("Длина пароля по умолчанию:", self.default_password_length)

        self.password_exclude_ambiguous = QCheckBox("Исключать неоднозначные символы (l, I, 1, O, 0)")
        self.password_exclude_ambiguous.setChecked(True)
        generator_layout.addRow("", self.password_exclude_ambiguous)

        layout.addRow(generator_group)

        trash_group = QGroupBox("Корзина")
        trash_layout = QFormLayout(trash_group)

        self.trash_retention_days = QSpinBox()
        self.trash_retention_days.setRange(1, 90)
        self.trash_retention_days.setSuffix(" дней")
        trash_layout.addRow("Хранение удаленных записей:", self.trash_retention_days)

        layout.addRow(trash_group)

        logs_group = QGroupBox("Журнал аудита")
        logs_layout = QFormLayout(logs_group)

        self.audit_log_enabled = QCheckBox("Включить журнал аудита")
        self.audit_log_enabled.setChecked(True)
        logs_layout.addRow("", self.audit_log_enabled)

        layout.addRow(logs_group)

        return widget

    def load_settings(self):
        try:
            from src.database.models import get_setting
            from src.database.db import Database
            import os

            db_path = os.path.join(
                os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
                "src", "database", "cryptosafe.db"
            )

            db = Database(db_path)
            conn = db.connect()

            self.auto_lock_timeout.setValue(int(get_setting(conn, 'auto_lock_timeout', '60')))
            self.session_timeout.setValue(int(get_setting(conn, 'session_timeout', '60')))
            self.clipboard_timeout.setValue(int(get_setting(conn, 'clipboard_clear_timeout', '30')))
            self.password_min_length.setValue(int(get_setting(conn, 'password_min_length', '12')))
            self.password_require_upper.setChecked(get_setting(conn, 'password_require_upper', 'true') == 'true')
            self.password_require_lower.setChecked(get_setting(conn, 'password_require_lower', 'true') == 'true')
            self.password_require_digit.setChecked(get_setting(conn, 'password_require_digit', 'true') == 'true')
            self.password_require_special.setChecked(get_setting(conn, 'password_require_special', 'true') == 'true')
            self.default_password_length.setValue(int(get_setting(conn, 'default_password_length', '16')))
            self.password_exclude_ambiguous.setChecked(
                get_setting(conn, 'password_exclude_ambiguous', 'true') == 'true')
            self.trash_retention_days.setValue(int(get_setting(conn, 'trash_retention_days', '30')))

            theme = get_setting(conn, 'theme', 'system')
            if theme == 'system':
                self.theme_combo.setCurrentIndex(2)
            elif theme == 'light':
                self.theme_combo.setCurrentIndex(0)
            elif theme == 'dark':
                self.theme_combo.setCurrentIndex(1)

            language = get_setting(conn, 'language', 'ru')
            if language == 'ru':
                self.language_combo.setCurrentIndex(0)
            else:
                self.language_combo.setCurrentIndex(1)

            db.close()

        except Exception as e:
            print(f"Ошибка загрузки настроек: {e}")
            self._set_default_values()

    def _set_default_values(self):
        self.auto_lock_timeout.setValue(60)
        self.session_timeout.setValue(60)
        self.clipboard_timeout.setValue(30)
        self.clipboard_auto_clear.setChecked(True)
        self.password_min_length.setValue(12)
        self.password_require_upper.setChecked(True)
        self.password_require_lower.setChecked(True)
        self.password_require_digit.setChecked(True)
        self.password_require_special.setChecked(True)
        self.default_password_length.setValue(16)
        self.password_exclude_ambiguous.setChecked(True)
        self.trash_retention_days.setValue(30)
        self.theme_combo.setCurrentIndex(2)
        self.language_combo.setCurrentIndex(0)

    def save_settings(self):
        try:
            from src.database.models import update_setting
            from src.database.db import Database
            import os

            db_path = os.path.join(
                os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
                "src", "database", "cryptosafe.db"
            )

            db = Database(db_path)
            conn = db.connect()

            update_setting(conn, 'auto_lock_timeout', str(self.auto_lock_timeout.value()))
            update_setting(conn, 'session_timeout', str(self.session_timeout.value()))
            update_setting(conn, 'clipboard_clear_timeout', str(self.clipboard_timeout.value()))
            update_setting(conn, 'password_min_length', str(self.password_min_length.value()))
            update_setting(conn, 'password_require_upper',
                           'true' if self.password_require_upper.isChecked() else 'false')
            update_setting(conn, 'password_require_lower',
                           'true' if self.password_require_lower.isChecked() else 'false')
            update_setting(conn, 'password_require_digit',
                           'true' if self.password_require_digit.isChecked() else 'false')
            update_setting(conn, 'password_require_special',
                           'true' if self.password_require_special.isChecked() else 'false')
            update_setting(conn, 'default_password_length', str(self.default_password_length.value()))
            update_setting(conn, 'password_exclude_ambiguous',
                           'true' if self.password_exclude_ambiguous.isChecked() else 'false')
            update_setting(conn, 'trash_retention_days', str(self.trash_retention_days.value()))

            theme = 'system'
            if self.theme_combo.currentIndex() == 0:
                theme = 'light'
            elif self.theme_combo.currentIndex() == 1:
                theme = 'dark'
            update_setting(conn, 'theme', theme)

            language = 'ru'
            if self.language_combo.currentIndex() == 1:
                language = 'en'
            update_setting(conn, 'language', language)

            db.close()

            QMessageBox.information(
                self,
                "Настройки сохранены",
                "Настройки успешно сохранены.\n\n"
                "Некоторые изменения вступят в силу после перезапуска приложения."
            )

            self.accept()

        except Exception as e:
            QMessageBox.critical(
                self,
                "Ошибка",
                f"Не удалось сохранить настройки: {e}"
            )