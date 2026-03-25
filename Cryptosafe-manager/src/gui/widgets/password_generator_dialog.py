from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QFormLayout, QSpinBox,
                             QCheckBox, QPushButton, QHBoxLayout, QLabel,
                             QGroupBox, QMessageBox)
from PyQt6.QtCore import Qt


class PasswordGeneratorDialog(QDialog):

    def __init__(self, parent=None, entry_manager=None):
        super().__init__(parent)
        self.entry_manager = entry_manager
        self.generated_password = ""

        self.setWindowTitle("Настройки генерации пароля")
        self.setModal(True)
        self.setFixedSize(400, 380)

        layout = QVBoxLayout(self)

        settings_group = QGroupBox("Настройки пароля")
        form_layout = QFormLayout(settings_group)

        self.length_spin = QSpinBox()
        self.length_spin.setRange(8, 64)
        self.length_spin.setValue(16)
        form_layout.addRow("Длина пароля:", self.length_spin)

        self.use_uppercase = QCheckBox("Заглавные буквы (A-Z)")
        self.use_uppercase.setChecked(True)
        form_layout.addRow("", self.use_uppercase)

        self.use_lowercase = QCheckBox("Строчные буквы (a-z)")
        self.use_lowercase.setChecked(True)
        form_layout.addRow("", self.use_lowercase)

        self.use_digits = QCheckBox("Цифры (0-9)")
        self.use_digits.setChecked(True)
        form_layout.addRow("", self.use_digits)

        self.use_special = QCheckBox("Спецсимволы (!@#$%^&*)")
        self.use_special.setChecked(True)
        form_layout.addRow("", self.use_special)

        self.exclude_ambiguous = QCheckBox("Исключить неоднозначные символы (l, I, 1, O, 0)")
        self.exclude_ambiguous.setChecked(True)
        form_layout.addRow("", self.exclude_ambiguous)

        layout.addWidget(settings_group)

        self.password_label = QLabel("")
        self.password_label.setStyleSheet(
            "font-family: monospace; font-size: 13px; background-color: #f8f8f8; padding: 8px; border: 1px solid #ddd;")
        self.password_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.password_label.setWordWrap(True)
        layout.addWidget(self.password_label)

        self.length_spin.valueChanged.connect(self.generate)
        self.use_uppercase.stateChanged.connect(self.generate)
        self.use_lowercase.stateChanged.connect(self.generate)
        self.use_digits.stateChanged.connect(self.generate)
        self.use_special.stateChanged.connect(self.generate)
        self.exclude_ambiguous.stateChanged.connect(self.generate)

        buttons_layout = QHBoxLayout()

        generate_btn = QPushButton("Сгенерировать заново")
        generate_btn.clicked.connect(self.generate)
        buttons_layout.addWidget(generate_btn)

        use_btn = QPushButton("Использовать этот пароль")
        use_btn.clicked.connect(self.accept)
        use_btn.setDefault(True)
        buttons_layout.addWidget(use_btn)

        cancel_btn = QPushButton("Отмена")
        cancel_btn.clicked.connect(self.reject)
        buttons_layout.addWidget(cancel_btn)

        layout.addLayout(buttons_layout)

        self.generate()

    def generate(self):
        if not self.entry_manager:
            self.password_label.setText("Ошибка: генератор не доступен")
            return

        try:
            password = self.entry_manager.generate_with_settings(
                length=self.length_spin.value(),
                use_uppercase=self.use_uppercase.isChecked(),
                use_lowercase=self.use_lowercase.isChecked(),
                use_digits=self.use_digits.isChecked(),
                use_special=self.use_special.isChecked(),
                exclude_ambiguous=self.exclude_ambiguous.isChecked()
            )
            self.generated_password = password
            self.password_label.setText(password)
        except Exception as e:
            self.password_label.setText(f"Ошибка: {e}")

    def get_password(self) -> str:
        return self.generated_password