from PyQt6.QtWidgets import (QWidget, QHBoxLayout, QLabel, QPushButton,
                             QDialog, QVBoxLayout, QTextEdit, QMessageBox,
                             QLineEdit, QFormLayout)
from PyQt6.QtCore import Qt, QTimer


class PasswordDialog(QDialog):
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

        ok_btn = QPushButton("Подтвердить")
        ok_btn.clicked.connect(self.accept)
        ok_btn.setDefault(True)
        buttons_layout.addWidget(ok_btn)

        cancel_btn = QPushButton("Отмена")
        cancel_btn.clicked.connect(self.reject)
        buttons_layout.addWidget(cancel_btn)

        layout.addLayout(buttons_layout)

    def get_password(self):
        return self.password_input.text()


class ClipboardPreviewWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent_app = parent
        self.setup_ui()

        self.update_timer = QTimer()
        self.update_timer.timeout.connect(self.update_preview)
        self.update_timer.start(500)

        self.setMaximumHeight(36)

    def setup_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(5, 2, 10, 2)
        layout.setSpacing(8)

        self.icon_label = QLabel("📋")
        self.icon_label.setFixedWidth(24)
        layout.addWidget(self.icon_label)

        self.info_label = QLabel("Буфер пуст")
        self.info_label.setStyleSheet("color: gray; font-size: 11px;")
        self.info_label.setMinimumWidth(250)
        layout.addWidget(self.info_label, 1)

        self.reveal_btn = QPushButton("👁")
        self.reveal_btn.setFixedSize(28, 24)
        self.reveal_btn.setToolTip("Показать полное содержимое (требуется пароль)")
        self.reveal_btn.setEnabled(False)
        self.reveal_btn.clicked.connect(self.reveal_content)
        layout.addWidget(self.reveal_btn)

        self.clear_btn = QPushButton("🗑️")
        self.clear_btn.setFixedSize(28, 24)
        self.clear_btn.setToolTip("Очистить буфер обмена")
        self.clear_btn.setEnabled(False)
        self.clear_btn.clicked.connect(self.clear_clipboard)
        layout.addWidget(self.clear_btn)

        self.setVisible(False)

    def update_preview(self):
        if not self.parent_app or not hasattr(self.parent_app, 'clipboard_service'):
            return

        status = self.parent_app.clipboard_service.get_current_status()

        if status.get('active', False):
            preview = self.parent_app.clipboard_service.get_current_data_preview(reveal=False)
            data_type = status.get('data_type', 'текст')
            remaining = status.get('remaining_seconds', 0)
            source_entry_id = status.get('source_entry_id')

            source_name = ""
            if source_entry_id and hasattr(self.parent_app, 'entry_manager'):
                try:
                    entry = self.parent_app.entry_manager.get_entry(source_entry_id)
                    if entry:
                        source_name = f" из '{entry.get('title', '?')}'"
                except:
                    pass

            if remaining > 0:
                time_text = f"очистится через {remaining} сек"
            elif remaining == -1:
                time_text = "авто-очистка отключена"
            else:
                time_text = ""

            self.info_label.setText(f"{data_type}{source_name}: {preview} | {time_text}")
            self.info_label.setStyleSheet("color: #333; font-size: 11px;")
            self.reveal_btn.setEnabled(True)
            self.clear_btn.setEnabled(True)

            self.setVisible(True)
        else:
            self.info_label.setText("Буфер пуст")
            self.info_label.setStyleSheet("color: gray; font-size: 11px;")
            self.reveal_btn.setEnabled(False)
            self.clear_btn.setEnabled(False)
            self.setVisible(False)

    def reveal_content(self):
        if not self.parent_app:
            return

        if self.parent_app.state.is_locked or not self.parent_app.state.logged_in:
            QMessageBox.warning(
                self,
                "Хранилище заблокировано",
                "Хранилище заблокировано. Пожалуйста, разблокируйте приложение."
            )
            return

        password_dialog = PasswordDialog(self)
        if password_dialog.exec() != QDialog.DialogCode.Accepted:
            return

        entered_password = password_dialog.get_password()

        if not self.parent_app.auth.verify_password(entered_password):
            QMessageBox.critical(
                self,
                "Ошибка аутентификации",
                "Неверный мастер-пароль. Доступ к содержимому буфера запрещён."
            )
            return

        full_content = self.parent_app.clipboard_service.get_current_data_preview(reveal=True)

        if full_content:
            dialog = QDialog(self)
            dialog.setWindowTitle("Содержимое буфера обмена")
            dialog.setMinimumSize(450, 250)

            layout = QVBoxLayout(dialog)

            text_edit = QTextEdit()
            text_edit.setPlainText(full_content)
            text_edit.setReadOnly(True)
            layout.addWidget(text_edit)

            close_btn = QPushButton("Закрыть")
            close_btn.clicked.connect(dialog.accept)
            layout.addWidget(close_btn)

            dialog.exec()

    def clear_clipboard(self):
        if self.parent_app and hasattr(self.parent_app, 'clipboard_service'):
            self.parent_app.clipboard_service.clear_clipboard(manual=True)