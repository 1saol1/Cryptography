from PyQt6.QtWidgets import (QWidget, QHBoxLayout, QLabel, QPushButton,
                             QDialog, QVBoxLayout, QTextEdit, QMessageBox,
                             QLineEdit, QFormLayout)
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QFont


class PasswordDialog(QDialog):
    """Диалог для ввода мастер-пароля"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Аутентификация")
        self.setModal(True)
        self.setFixedSize(350, 150)

        layout = QVBoxLayout(self)

        label = QLabel("Для просмотра содержимого буфера введите мастер-пароль:")
        label.setWordWrap(True)
        layout.addWidget(label)

        form_layout = QFormLayout()
        self.password_input = QLineEdit()
        self.password_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.password_input.setPlaceholderText("Введите мастер-пароль")
        form_layout.addRow("Мастер-пароль:", self.password_input)
        layout.addLayout(form_layout)

        buttons_layout = QHBoxLayout()
        buttons_layout.addStretch()

        self.ok_btn = QPushButton("Подтвердить")
        self.ok_btn.clicked.connect(self.accept)
        self.ok_btn.setDefault(True)
        buttons_layout.addWidget(self.ok_btn)

        cancel_btn = QPushButton("Отмена")
        cancel_btn.clicked.connect(self.reject)
        buttons_layout.addWidget(cancel_btn)

        layout.addLayout(buttons_layout)

        self.password_input.returnPressed.connect(self.accept)

    def get_password(self) -> str:
        return self.password_input.text()


class ClipboardPreviewWidget(QWidget):
    """Виджет для отображения предпросмотра буфера обмена"""

    def __init__(self, parent=None):
        super().__init__(parent)

        self.parent_app = parent
        self.setup_ui()

        # Таймер для обновления (каждые 500 мс)
        self.update_timer = QTimer()
        self.update_timer.timeout.connect(self.update_preview)
        self.update_timer.start(500)

        self.setMaximumHeight(36)

    def setup_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(5, 2, 10, 2)
        layout.setSpacing(8)

        # Иконка
        self.icon_label = QLabel("📋")
        self.icon_label.setFixedWidth(24)
        self.icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.icon_label)

        # Информация (маскированный предпросмотр)
        self.info_label = QLabel("Буфер пуст")
        self.info_label.setStyleSheet("color: gray; font-size: 11px;")
        self.info_label.setMinimumWidth(250)
        layout.addWidget(self.info_label, 1)

        # Кнопка раскрытия (глаз)
        self.reveal_btn = QPushButton("👁")
        self.reveal_btn.setFixedSize(28, 24)
        self.reveal_btn.setToolTip("Показать полное содержимое (требуется пароль)")
        self.reveal_btn.setEnabled(False)
        self.reveal_btn.clicked.connect(self.reveal_content)
        layout.addWidget(self.reveal_btn)

        # Кнопка очистки
        self.clear_btn = QPushButton("🗑️")
        self.clear_btn.setFixedSize(28, 24)
        self.clear_btn.setToolTip("Очистить буфер обмена")
        self.clear_btn.setEnabled(False)
        self.clear_btn.clicked.connect(self.clear_clipboard)
        layout.addWidget(self.clear_btn)

        self.setVisible(False)

    def update_preview(self):
        """Обновляет отображение предпросмотра"""
        if not self.parent_app or not hasattr(self.parent_app, 'clipboard_service'):
            return

        status = self.parent_app.clipboard_service.get_current_status()

        if status.get('active', False):
            # Получаем маскированный предпросмотр
            preview = self.parent_app.clipboard_service.get_current_data_preview(reveal=False)
            data_type = status.get('data_type', 'текст')
            remaining = status.get('remaining_seconds', 0)
            source_entry_id = status.get('source_entry_id')

            # Получаем название записи-источника
            source_name = ""
            if source_entry_id and hasattr(self.parent_app, 'entry_manager'):
                try:
                    entry = self.parent_app.entry_manager.get_entry(source_entry_id)
                    if entry:
                        source_name = f" из '{entry.get('title', '?')}'"
                except:
                    pass

            # Формируем текст
            if remaining > 0:
                time_text = f"очистится через {remaining} сек"
            elif remaining == -1:
                time_text = "авто-очистка отключена"
            else:
                time_text = ""

            # Отображаем тип данных, маскированный предпросмотр и источник
            self.info_label.setText(f"{data_type}{source_name}: {preview} | {time_text}")
            self.info_label.setStyleSheet("color: #333; font-size: 11px;")
            self.reveal_btn.setEnabled(True)
            self.clear_btn.setEnabled(True)

            # Меняем иконку в зависимости от типа данных
            if data_type == 'password':
                self.icon_label.setText("🔒")
                self.icon_label.setToolTip("Пароль в буфере")
            elif data_type == 'username':
                self.icon_label.setText("👤")
                self.icon_label.setToolTip("Логин в буфере")
            elif data_type == 'url':
                self.icon_label.setText("🔗")
                self.icon_label.setToolTip("URL в буфере")
            elif data_type == 'title':
                self.icon_label.setText("📄")
                self.icon_label.setToolTip("Название в буфере")
            elif data_type == 'credentials':
                self.icon_label.setText("🔐")
                self.icon_label.setToolTip("Учётные данные в буфере")
            else:
                self.icon_label.setText("📋")
                self.icon_label.setToolTip("Текст в буфере")

            self.setVisible(True)
        else:
            self.info_label.setText("Буфер пуст")
            self.info_label.setStyleSheet("color: gray; font-size: 11px;")
            self.reveal_btn.setEnabled(False)
            self.clear_btn.setEnabled(False)
            self.icon_label.setText("📋")
            self.icon_label.setToolTip("Буфер пуст")
            self.setVisible(False)

    def reveal_content(self):
        """Показывает полное содержимое буфера (требует аутентификацию)"""
        if not self.parent_app:
            return

        # Проверяем, активна ли сессия
        if self.parent_app.state.is_locked or not self.parent_app.state.logged_in:
            QMessageBox.warning(
                self,
                "Хранилище заблокировано",
                "Хранилище заблокировано. Пожалуйста, разблокируйте приложение."
            )
            return

        # Запрашиваем мастер-пароль для дополнительной безопасности
        password_dialog = PasswordDialog(self)
        if password_dialog.exec() != QDialog.DialogCode.Accepted:
            return

        entered_password = password_dialog.get_password()

        # Проверяем пароль
        if not self.parent_app.auth.verify_password(entered_password):
            QMessageBox.critical(
                self,
                "Ошибка аутентификации",
                "Неверный мастер-пароль. Доступ к содержимому буфера запрещён."
            )
            return

        # Получаем полное содержимое
        full_content = self.parent_app.clipboard_service.get_current_data_preview(reveal=True)
        status = self.parent_app.clipboard_service.get_current_status()

        if full_content:
            # Показываем в отдельном диалоге
            dialog = QDialog(self)
            dialog.setWindowTitle("Содержимое буфера обмена")
            dialog.setMinimumSize(450, 250)

            layout = QVBoxLayout(dialog)

            # Информация о содержимом
            info_label = QLabel()
            data_type = status.get('data_type', 'текст')
            remaining = status.get('remaining_seconds', 0)
            source_entry_id = status.get('source_entry_id')

            source_text = ""
            if source_entry_id and hasattr(self.parent_app, 'entry_manager'):
                try:
                    entry = self.parent_app.entry_manager.get_entry(source_entry_id)
                    if entry:
                        source_text = f" (из записи: {entry.get('title', '?')})"
                except:
                    pass

            if remaining > 0:
                time_text = f"Очистится через {remaining} секунд"
            elif remaining == -1:
                time_text = "Авто-очистка отключена"
            else:
                time_text = ""

            info_label.setText(f"Тип: {data_type}{source_text}\n{time_text}")
            info_label.setStyleSheet("color: gray; font-size: 10px;")
            layout.addWidget(info_label)

            # Поле с содержимым
            text_edit = QTextEdit()
            text_edit.setPlainText(full_content)
            text_edit.setReadOnly(True)
            text_edit.setFont(QFont("Consolas", 10))
            layout.addWidget(text_edit)

            # Кнопка копирования
            copy_btn = QPushButton("📋 Копировать в буфер (как текст)")
            copy_btn.clicked.connect(lambda: self._copy_to_clipboard(full_content, dialog))
            layout.addWidget(copy_btn)

            # Кнопка закрытия
            close_btn = QPushButton("Закрыть")
            close_btn.clicked.connect(dialog.accept)
            layout.addWidget(close_btn)

            dialog.exec()

    def _copy_to_clipboard(self, text: str, dialog: QDialog):
        """Копирует текст в буфер обмена"""
        if hasattr(self.parent_app, 'copy_to_clipboard'):
            self.parent_app.copy_to_clipboard(text, data_type="text")
            self.parent_app.status_bar.showMessage("Содержимое скопировано в буфер обмена")
            dialog.accept()

    def clear_clipboard(self):
        """Очищает буфер обмена"""
        if self.parent_app and hasattr(self.parent_app, 'clipboard_service'):
            self.parent_app.clipboard_service.clear_clipboard(manual=True)
            self.parent_app.status_bar.showMessage("Буфер обмена очищен")