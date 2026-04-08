from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QTabWidget, QWidget,
                             QFormLayout, QLabel, QComboBox, QSpinBox,
                             QCheckBox, QPushButton, QHBoxLayout, QGroupBox,
                             QMessageBox, QListWidget, QFileDialog)
import json
import os
from src.core.config import ConfigManager


class SettingsDialog(QDialog):
    def __init__(self, parent=None, db_path=None):
        super().__init__(parent)

        if db_path:
            self.db_path = db_path
        else:
            current_dir = os.path.dirname(os.path.abspath(__file__))
            project_root = os.path.dirname(os.path.dirname(os.path.dirname(current_dir)))
            self.db_path = os.path.join(project_root, "src", "database", "cryptosafe.db")

        print(f"[SettingsDialog] Путь к БД: {self.db_path}")

        self.setWindowTitle("Настройки")
        self.setModal(True)
        self.setMinimumWidth(600)
        self.setMinimumHeight(550)

        layout = QVBoxLayout(self)

        self.tab_widget = QTabWidget()

        self.security_tab = self._create_security_tab()
        self.tab_widget.addTab(self.security_tab, "Безопасность")

        self.clipboard_tab = self._create_clipboard_tab()
        self.tab_widget.addTab(self.clipboard_tab, "Буфер обмена")

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

    def _create_clipboard_tab(self):
        widget = QWidget()
        layout = QFormLayout(widget)
        layout.setSpacing(15)

        # 1. Таймаут авто-очистки
        timeout_group = QGroupBox("Авто-очистка буфера обмена")
        timeout_layout = QFormLayout(timeout_group)

        self.clipboard_timeout = QSpinBox()
        self.clipboard_timeout.setRange(5, 300)
        self.clipboard_timeout.setSuffix(" сек")
        self.clipboard_timeout.setToolTip("Время через которое буфер автоматически очистится")
        timeout_layout.addRow("Таймаут авто-очистки:", self.clipboard_timeout)

        self.clipboard_never_clear = QCheckBox("Никогда не очищать автоматически")
        self.clipboard_never_clear.setToolTip("Отключить авто-очистку (не рекомендуется)")
        timeout_layout.addRow("", self.clipboard_never_clear)

        layout.addRow(timeout_group)

        # 2. Уровень безопасности
        security_group = QGroupBox("Уровень безопасности")
        security_layout = QFormLayout(security_group)

        self.security_level = QComboBox()
        self.security_level.addItems(["Стандартный (30 сек)", "Усиленный (15 сек)", "Параноидальный (5 сек)"])
        self.security_level.setToolTip("Предустановленные профили безопасности")
        security_layout.addRow("Профиль безопасности:", self.security_level)

        layout.addRow(security_group)

        # 3. Настройки уведомлений
        notifications_group = QGroupBox("Уведомления")
        notifications_layout = QFormLayout(notifications_group)

        self.notifications_enabled = QCheckBox("Показывать всплывающие уведомления")
        self.notifications_enabled.setToolTip("Показывать уведомления при копировании и очистке")
        notifications_layout.addRow("", self.notifications_enabled)

        self.warn_before_clear = QSpinBox()
        self.warn_before_clear.setRange(1, 10)
        self.warn_before_clear.setSuffix(" сек")
        self.warn_before_clear.setToolTip("Показать предупреждение за N секунд до очистки")
        notifications_layout.addRow("Предупреждение за:", self.warn_before_clear)

        layout.addRow(notifications_group)

        # 4. Мониторинг безопасности
        monitor_group = QGroupBox("Мониторинг безопасности")
        monitor_layout = QFormLayout(monitor_group)

        self.monitor_enabled = QCheckBox("Включить мониторинг буфера обмена")
        self.monitor_enabled.setToolTip("Обнаружение внешнего доступа к буферу обмена")
        monitor_layout.addRow("", self.monitor_enabled)

        self.suspicious_threshold = QSpinBox()
        self.suspicious_threshold.setRange(1, 10)
        self.suspicious_threshold.setToolTip("Количество подозрительных действий до включения защиты")
        monitor_layout.addRow("Порог подозрений:", self.suspicious_threshold)

        layout.addRow(monitor_group)

        # 5. Белый список приложений
        whitelist_group = self._create_whitelist_group()
        layout.addRow(whitelist_group)

        return widget

    def _create_whitelist_group(self):
        group = QGroupBox("Белый список приложений")
        layout = QVBoxLayout(group)

        info_label = QLabel(
            "Приложения из белого списка могут читать буфер обмена без предупреждений.\n"
            "Укажите пути к исполняемым файлам (.exe)."
        )
        info_label.setWordWrap(True)
        info_label.setStyleSheet("color: gray; font-size: 10px;")
        layout.addWidget(info_label)

        self.whitelist_list = QListWidget()
        self.whitelist_list.setMaximumHeight(150)
        self.whitelist_list.setToolTip("Приложения, которым разрешён доступ к буферу обмена")
        layout.addWidget(self.whitelist_list)

        buttons_layout = QHBoxLayout()

        add_btn = QPushButton("➕ Добавить приложение")
        add_btn.clicked.connect(self._add_to_whitelist)
        buttons_layout.addWidget(add_btn)

        remove_btn = QPushButton("➖ Удалить выбранное")
        remove_btn.clicked.connect(self._remove_from_whitelist)
        buttons_layout.addWidget(remove_btn)

        clear_btn = QPushButton("🗑️ Очистить список")
        clear_btn.clicked.connect(self._clear_whitelist)
        buttons_layout.addWidget(clear_btn)

        layout.addLayout(buttons_layout)

        return group

    def _add_to_whitelist(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Выберите приложение для добавления в белый список",
            "C:\\Program Files",
            "Исполняемые файлы (*.exe);;Все файлы (*.*)"
        )

        if file_path:
            existing_items = [self.whitelist_list.item(i).text() for i in range(self.whitelist_list.count())]
            if file_path not in existing_items:
                self.whitelist_list.addItem(file_path)

    def _remove_from_whitelist(self):
        current_item = self.whitelist_list.currentItem()
        if current_item:
            reply = QMessageBox.question(
                self,
                "Подтверждение",
                f"Удалить '{current_item.text()}' из белого списка?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            if reply == QMessageBox.StandardButton.Yes:
                self.whitelist_list.takeItem(self.whitelist_list.row(current_item))

    def _clear_whitelist(self):
        if self.whitelist_list.count() > 0:
            reply = QMessageBox.question(
                self,
                "Подтверждение",
                "Очистить весь белый список приложений?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            if reply == QMessageBox.StandardButton.Yes:
                self.whitelist_list.clear()

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


            config = ConfigManager(self.db_path)

            # Основные настройки
            self.auto_lock_timeout.setValue(int(config.get('auto_lock_timeout', '60')))
            self.session_timeout.setValue(int(config.get('session_timeout', '60')))
            self.password_min_length.setValue(int(config.get('password_min_length', '12')))
            self.password_require_upper.setChecked(config.get('password_require_upper', 'true') == 'true')
            self.password_require_lower.setChecked(config.get('password_require_lower', 'true') == 'true')
            self.password_require_digit.setChecked(config.get('password_require_digit', 'true') == 'true')
            self.password_require_special.setChecked(config.get('password_require_special', 'true') == 'true')
            self.default_password_length.setValue(int(config.get('default_password_length', '16')))
            self.password_exclude_ambiguous.setChecked(config.get('password_exclude_ambiguous', 'true') == 'true')
            self.trash_retention_days.setValue(int(config.get('trash_retention_days', '30')))

            # Настройки буфера обмена
            timeout_value = config.get('clipboard_clear_timeout', '30')
            if timeout_value == '0':
                self.clipboard_never_clear.setChecked(True)
                self.clipboard_timeout.setValue(30)
                self.clipboard_timeout.setEnabled(False)
            else:
                self.clipboard_never_clear.setChecked(False)
                self.clipboard_timeout.setValue(int(timeout_value))
                self.clipboard_timeout.setEnabled(True)

            self.clipboard_never_clear.toggled.connect(
                lambda checked: self.clipboard_timeout.setEnabled(not checked)
            )

            security_level = config.get('clipboard_security_level', 'standard')
            if security_level == 'standard':
                self.security_level.setCurrentIndex(0)
            elif security_level == 'secure':
                self.security_level.setCurrentIndex(1)
            else:
                self.security_level.setCurrentIndex(2)

            self.notifications_enabled.setChecked(config.get('clipboard_notifications_enabled', 'true') == 'true')
            self.warn_before_clear.setValue(int(config.get('clipboard_warn_before_clear', '5')))
            self.monitor_enabled.setChecked(config.get('clipboard_monitor_enabled', 'true') == 'true')
            self.suspicious_threshold.setValue(int(config.get('clipboard_suspicious_threshold', '3')))

            # Загрузка белого списка
            whitelist_json = config.get('clipboard_whitelist', '[]')
            try:
                whitelist = json.loads(whitelist_json)
                self.whitelist_list.clear()
                for app_path in whitelist:
                    self.whitelist_list.addItem(app_path)
            except:
                pass

            # Внешний вид
            theme = config.get('theme', 'system')
            if theme == 'system':
                self.theme_combo.setCurrentIndex(2)
            elif theme == 'light':
                self.theme_combo.setCurrentIndex(0)
            elif theme == 'dark':
                self.theme_combo.setCurrentIndex(1)

            language = config.get('language', 'ru')
            if language == 'ru':
                self.language_combo.setCurrentIndex(0)
            else:
                self.language_combo.setCurrentIndex(1)

            print("[DEBUG] Настройки успешно загружены")

        except Exception as e:
            print(f"Ошибка загрузки настроек: {e}")
            import traceback
            traceback.print_exc()
            self._set_default_values()

    def _set_default_values(self):
        self.auto_lock_timeout.setValue(60)
        self.session_timeout.setValue(60)
        self.clipboard_timeout.setValue(30)
        self.clipboard_never_clear.setChecked(False)
        self.clipboard_timeout.setEnabled(True)
        self.security_level.setCurrentIndex(0)
        self.notifications_enabled.setChecked(True)
        self.warn_before_clear.setValue(5)
        self.monitor_enabled.setChecked(True)
        self.suspicious_threshold.setValue(3)
        self.whitelist_list.clear()
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
            import json

            config = ConfigManager(self.db_path)

            config.set('auto_lock_timeout', str(self.auto_lock_timeout.value()))
            config.set('session_timeout', str(self.session_timeout.value()))
            config.set('password_min_length', str(self.password_min_length.value()))
            config.set('password_require_upper', 'true' if self.password_require_upper.isChecked() else 'false')
            config.set('password_require_lower', 'true' if self.password_require_lower.isChecked() else 'false')
            config.set('password_require_digit', 'true' if self.password_require_digit.isChecked() else 'false')
            config.set('password_require_special', 'true' if self.password_require_special.isChecked() else 'false')
            config.set('default_password_length', str(self.default_password_length.value()))
            config.set('password_exclude_ambiguous', 'true' if self.password_exclude_ambiguous.isChecked() else 'false')
            config.set('trash_retention_days', str(self.trash_retention_days.value()))

            # Настройки буфера обмена
            if self.clipboard_never_clear.isChecked():
                config.set('clipboard_clear_timeout', '0')
            else:
                config.set('clipboard_clear_timeout', str(self.clipboard_timeout.value()))

            security_level = 'standard'
            if self.security_level.currentIndex() == 1:
                security_level = 'secure'
            elif self.security_level.currentIndex() == 2:
                security_level = 'paranoid'
            config.set('clipboard_security_level', security_level)

            config.set('clipboard_notifications_enabled', 'true' if self.notifications_enabled.isChecked() else 'false')
            config.set('clipboard_warn_before_clear', str(self.warn_before_clear.value()))
            config.set('clipboard_monitor_enabled', 'true' if self.monitor_enabled.isChecked() else 'false')
            config.set('clipboard_suspicious_threshold', str(self.suspicious_threshold.value()))

            # Сохранение белого списка
            whitelist = []
            for i in range(self.whitelist_list.count()):
                whitelist.append(self.whitelist_list.item(i).text())
            whitelist_json = json.dumps(whitelist, ensure_ascii=False)
            config.set('clipboard_whitelist', whitelist_json)

            # Внешний вид
            theme = 'system'
            if self.theme_combo.currentIndex() == 0:
                theme = 'light'
            elif self.theme_combo.currentIndex() == 1:
                theme = 'dark'
            config.set('theme', theme)

            language = 'ru'
            if self.language_combo.currentIndex() == 1:
                language = 'en'
            config.set('language', language)

            print("[DEBUG] Настройки успешно сохранены")

            QMessageBox.information(
                self,
                "Настройки сохранены",
                "Настройки успешно сохранены.\n\nНекоторые изменения вступят в силу после перезапуска приложения."
            )
            self.accept()

        except Exception as e:
            print(f"Ошибка сохранения настроек: {e}")
            import traceback
            traceback.print_exc()
            QMessageBox.critical(
                self,
                "Ошибка",
                f"Не удалось сохранить настройки: {e}"
            )