from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QFormLayout, QLineEdit,
                             QTextEdit, QPushButton, QHBoxLayout, QLabel,
                             QMessageBox, QComboBox, QWidget)

from .password_entry import PasswordEntry


class EntryDialog(QDialog):
    def __init__(self, parent, entry_manager, edit_mode=False, existing_data=None):
        super().__init__(parent)
        self.entry_manager = entry_manager
        self.edit_mode = edit_mode
        self.existing_data = existing_data

        self.setWindowTitle("Редактировать запись" if edit_mode else "Новая запись")
        self.setModal(True)
        self.setMinimumWidth(500)

        self._setup_ui()

        if edit_mode and existing_data:
            self._load_data(existing_data)

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        form_layout = QFormLayout()
        form_layout.setSpacing(10)

        self.title_input = QLineEdit()
        self.title_input.setPlaceholderText("Обязательное поле")
        form_layout.addRow("Название:*", self.title_input)

        self.username_input = QLineEdit()
        self.username_input.setPlaceholderText("user@example.com")
        form_layout.addRow("Логин/Email:", self.username_input)

        self.password_input = PasswordEntry()
        form_layout.addRow("Пароль:", self.password_input)

        self.strength_label = QLabel("")
        self.strength_label.setStyleSheet("font-size: 10px;")
        form_layout.addRow("", self.strength_label)

        gen_layout = QHBoxLayout()
        gen_btn = QPushButton("Сгенерировать пароль")
        gen_btn.clicked.connect(self._generate_password)
        gen_layout.addWidget(gen_btn)
        gen_layout.addStretch()
        form_layout.addRow("", gen_layout)

        self.url_input = QLineEdit()
        self.url_input.setPlaceholderText("https://example.com")
        form_layout.addRow("URL/Адрес:", self.url_input)

        self.notes_input = QTextEdit()
        self.notes_input.setMaximumHeight(80)
        form_layout.addRow("Заметки:", self.notes_input)

        self.category_input = QComboBox()
        self.category_input.addItems(["Общее", "Работа", "Личное", "Почта", "Соцсети", "Банки"])
        self.category_input.setEditable(True)
        form_layout.addRow("Категория:", self.category_input)

        layout.addLayout(form_layout)

        buttons_layout = QHBoxLayout()
        buttons_layout.addStretch()

        self.save_btn = QPushButton("Сохранить")
        self.save_btn.clicked.connect(self._accept)
        self.save_btn.setDefault(True)
        buttons_layout.addWidget(self.save_btn)

        cancel_btn = QPushButton("Отмена")
        cancel_btn.clicked.connect(self.reject)
        buttons_layout.addWidget(cancel_btn)

        layout.addLayout(buttons_layout)

        self.password_input.entry.textChanged.connect(self._check_password_strength)

    def _load_data(self, data):
        self.title_input.setText(data.get('title', ''))
        self.username_input.setText(data.get('username', ''))
        self.password_input.entry.setText(data.get('password', ''))
        self.url_input.setText(data.get('url', ''))
        self.notes_input.setPlainText(data.get('notes', ''))

        category = data.get('category', 'Общее')
        index = self.category_input.findText(category)
        if index >= 0:
            self.category_input.setCurrentIndex(index)
        else:
            self.category_input.setEditText(category)

        self._check_password_strength()

    def _generate_password(self):
        password = self.entry_manager.generate_password()
        self.password_input.entry.setText(password)
        self._check_password_strength()

    def _check_password_strength(self):
        password = self.password_input.get()

        if not password:
            self.strength_label.setText("")
            return

        strength = self.entry_manager.check_password_strength(password)

        if strength['score'] >= 3:
            color = "green"
            text = f"{strength['strength']} - {strength['feedback']}"
        elif strength['score'] >= 2:
            color = "orange"
            text = f"{strength['strength']} - {strength['feedback']}"
        else:
            color = "red"
            text = f"{strength['strength']} - {strength['feedback']}"

        self.strength_label.setText(text)
        self.strength_label.setStyleSheet(f"color: {color}; font-size: 10px;")

    def _validate(self) -> bool:
        title = self.title_input.text().strip()
        if not title:
            QMessageBox.warning(self, "Ошибка", "Название — обязательное поле")
            self.title_input.setFocus()
            return False

        password = self.password_input.get()
        if not password:
            QMessageBox.warning(self, "Ошибка", "Пароль — обязательное поле")
            self.password_input.entry.setFocus()
            return False

        strength = self.entry_manager.check_password_strength(password)
        if not strength['is_strong']:
            reply = QMessageBox.question(
                self,
                "Слабый пароль",
                f"Пароль: {strength['strength']}\n{strength['feedback']}\n\n"
                "Вы уверены, что хотите использовать этот пароль?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            if reply != QMessageBox.StandardButton.Yes:
                return False

        return True

    def _accept(self):
        if not self._validate():
            return

        self.accept()

    def get_data(self) -> dict:
        return {
            'title': self.title_input.text().strip(),
            'username': self.username_input.text().strip(),
            'password': self.password_input.get(),
            'url': self.url_input.text().strip(),
            'notes': self.notes_input.toPlainText().strip(),
            'category': self.category_input.currentText()
        }