from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QFormLayout, QLineEdit,
                             QTextEdit, QPushButton, QHBoxLayout, QLabel,
                             QMessageBox, QComboBox)

from .password_entry import PasswordEntry
from .password_generator_dialog import PasswordGeneratorDialog


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

        self.gen_btn = QPushButton("Сгенерировать пароль")
        self.gen_btn.clicked.connect(self._generate_password_simple)
        gen_layout.addWidget(self.gen_btn)

        self.settings_btn = QPushButton("⚙️")
        self.settings_btn.setFixedSize(30, 30)
        self.settings_btn.setToolTip("Настройки генерации пароля")
        self.settings_btn.clicked.connect(self._open_generator_dialog)
        gen_layout.addWidget(self.settings_btn)

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

        self.tags_input = QLineEdit()
        self.tags_input.setPlaceholderText("тег1, тег2, тег3")
        form_layout.addRow("Теги:", self.tags_input)

        layout.addLayout(form_layout)

        buttons_layout = QHBoxLayout()
        buttons_layout.addStretch()

        save_btn = QPushButton("Сохранить")
        save_btn.clicked.connect(self._accept)
        save_btn.setDefault(True)
        buttons_layout.addWidget(save_btn)

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

        tags = data.get('tags', [])
        if isinstance(tags, list):
            self.tags_input.setText(', '.join(tags))
        elif isinstance(tags, str):
            self.tags_input.setText(tags)

        self._check_password_strength()

    def _generate_password_simple(self):
        password = self.entry_manager.generate_password()
        self.password_input.entry.setText(password)
        self._check_password_strength()

    def _open_generator_dialog(self):
        dialog = PasswordGeneratorDialog(self, self.entry_manager)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            password = dialog.get_password()
            if password:
                self.password_input.entry.setText(password)
                self._check_password_strength()

    def _check_password_strength(self):
        try:
            password = self.password_input.get()

            if not password:
                self.strength_label.setText("")
                return

            strength = self.entry_manager.check_password_strength(password)

            if isinstance(strength, dict) and 'score' in strength and 'strength' in strength and 'feedback' in strength:
                if strength['score'] >= 3:
                    color = "green"
                    text = f"{strength['strength']} - {strength['feedback']}"
                elif strength['score'] >= 2:
                    color = "orange"
                    text = f"{strength['strength']} - {strength['feedback']}"
                else:
                    color = "red"
                    text = f"{strength['strength']} - {strength['feedback']}"
            else:
                if len(password) >= 12:
                    color = "green"
                    text = f"Длина: {len(password)} символов (хорошо)"
                elif len(password) >= 8:
                    color = "orange"
                    text = f"Длина: {len(password)} символов (минимум 12 для надежного)"
                else:
                    color = "red"
                    text = f"Длина: {len(password)} символов (минимум 8)"

            self.strength_label.setText(text)
            self.strength_label.setStyleSheet(f"color: {color}; font-size: 10px;")

        except Exception as e:
            print(f"Ошибка в _check_password_strength: {e}")
            password = self.password_input.get()
            if password:
                self.strength_label.setText(f"Длина пароля: {len(password)} символов")
            else:
                self.strength_label.setText("")

    def _validate_url(self, url: str) -> bool:
        if not url:
            return True

        if not url.startswith(('http://', 'https://')):
            reply = QMessageBox.question(
                self,
                "Нестандартный URL",
                f"URL должен начинаться с http:// или https://\n\n"
                f"Текущий URL: {url}\n\n"
                "Продолжить с этим URL?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            return reply == QMessageBox.StandardButton.Yes

        return True

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

        url = self.url_input.text().strip()
        if not self._validate_url(url):
            self.url_input.setFocus()
            return False

        strength = self.entry_manager.check_password_strength(password)
        if not strength.get('is_strong', False):
            reply = QMessageBox.question(
                self,
                "Слабый пароль",
                f"Пароль: {strength.get('strength', 'Слабый')}\n"
                f"{strength.get('feedback', '')}\n\n"
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
        tags_text = self.tags_input.text().strip()
        if tags_text:
            tags = [t.strip() for t in tags_text.split(',') if t.strip()]
        else:
            tags = []

        return {
            'title': self.title_input.text().strip(),
            'username': self.username_input.text().strip(),
            'password': self.password_input.get(),
            'url': self.url_input.text().strip(),
            'notes': self.notes_input.toPlainText().strip(),
            'category': self.category_input.currentText(),
            'tags': tags
        }