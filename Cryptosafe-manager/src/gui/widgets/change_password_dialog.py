import os
import sys
from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel,
                             QPushButton, QMessageBox, QGridLayout, QGroupBox)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, BASE_DIR)

from .password_entry import PasswordEntry


class ChangePasswordDialog(QDialog):

    def __init__(self, parent, auth):
        super().__init__(parent)
        self.auth = auth
        self.success = False

        self.setWindowTitle("Смена мастер-пароля")
        self.setFixedSize(500, 500)
        self.setModal(True)

        self.center_window()

        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(15)
        main_layout.setContentsMargins(25, 20, 25, 20)

        title = QLabel("Смена мастер-пароля")
        title.setFont(QFont("Arial", 14, QFont.Weight.Bold))
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        main_layout.addWidget(title)

        info_label = QLabel(
            "Все сохраненные записи будут автоматически\n"
            "перешифрованы с новым паролем."
        )
        info_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        info_label.setStyleSheet("color: gray; font-style: italic; padding: 10px;")
        main_layout.addWidget(info_label)

        pwd_group = QGroupBox("Введите пароли")
        pwd_group.setFont(QFont("Arial", 11, QFont.Weight.Bold))

        pwd_layout = QGridLayout(pwd_group)
        pwd_layout.setVerticalSpacing(10)
        pwd_layout.setHorizontalSpacing(15)

        pwd_layout.addWidget(QLabel("Текущий пароль:"), 0, 0, Qt.AlignmentFlag.AlignRight)
        self.current_password = PasswordEntry()
        pwd_layout.addWidget(self.current_password, 0, 1)

        pwd_layout.addWidget(QLabel("Новый пароль:"), 1, 0, Qt.AlignmentFlag.AlignRight)
        self.new_password = PasswordEntry()
        self.new_password.entry.textChanged.connect(self.update_strength_indicator)
        pwd_layout.addWidget(self.new_password, 1, 1)

        self.strength_label = QLabel("Введите новый пароль")
        self.strength_label.setStyleSheet("color: orange; font-size: 10px;")
        pwd_layout.addWidget(self.strength_label, 2, 1)

        pwd_layout.addWidget(QLabel("Подтверждение:"), 3, 0, Qt.AlignmentFlag.AlignRight)
        self.confirm_password = PasswordEntry()
        self.confirm_password.entry.textChanged.connect(self.check_passwords_match)
        pwd_layout.addWidget(self.confirm_password, 3, 1)

        self.match_label = QLabel("")
        self.match_label.setStyleSheet("font-size: 10px;")
        pwd_layout.addWidget(self.match_label, 4, 1)

        main_layout.addWidget(pwd_group)

        req_group = QGroupBox("Требования к новому паролю")
        req_group.setFont(QFont("Arial", 10, QFont.Weight.Bold))

        req_layout = QVBoxLayout(req_group)

        self.req_length = QLabel("Минимум 12 символов")
        self.req_length.setStyleSheet("color: red;")
        req_layout.addWidget(self.req_length)

        self.req_upper = QLabel("Заглавная буква")
        self.req_upper.setStyleSheet("color: red;")
        req_layout.addWidget(self.req_upper)

        self.req_lower = QLabel("Строчная буква")
        self.req_lower.setStyleSheet("color: red;")
        req_layout.addWidget(self.req_lower)

        self.req_digit = QLabel("Цифра")
        self.req_digit.setStyleSheet("color: red;")
        req_layout.addWidget(self.req_digit)

        self.req_special = QLabel("Спецсимвол (!@#$%^&*)")
        self.req_special.setStyleSheet("color: red;")
        req_layout.addWidget(self.req_special)

        main_layout.addWidget(req_group)

        button_layout = QHBoxLayout()
        button_layout.addStretch()

        cancel_btn = QPushButton("Отмена")
        cancel_btn.setFixedSize(120, 35)
        cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(cancel_btn)

        change_btn = QPushButton("Сменить пароль")
        change_btn.setFixedSize(150, 35)
        change_btn.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                border-radius: 5px;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
        """)
        change_btn.clicked.connect(self.change_password)
        button_layout.addWidget(change_btn)

        main_layout.addLayout(button_layout)

    def center_window(self):
        screen = self.screen().geometry()
        x = (screen.width() - self.width()) // 2
        y = (screen.height() - self.height()) // 2
        self.move(x, y)

    def update_strength_indicator(self):
        password = self.new_password.get()

        if not password:
            text = "Введите новый пароль"
            color = "orange"
        elif len(password) < 8:
            text = "Очень слабый"
            color = "red"
        elif len(password) < 12:
            text = "Слабый"
            color = "orange"
        else:
            has_upper = any(c.isupper() for c in password)
            has_lower = any(c.islower() for c in password)
            has_digit = any(c.isdigit() for c in password)
            has_special = any(not c.isalnum() for c in password)

            if has_upper and has_lower and has_digit and has_special:
                text = "Надежный"
                color = "green"
            else:
                text = "Средний"
                color = "orange"

        self.strength_label.setText(text)
        self.strength_label.setStyleSheet(f"color: {color}; font-size: 10px; font-weight: bold;")

        if len(password) >= 12:
            self.req_length.setText("Минимум 12 символов")
            self.req_length.setStyleSheet("color: green;")
        else:
            self.req_length.setText(f"Минимум 12 символов (сейчас {len(password)})")
            self.req_length.setStyleSheet("color: red;")

        has_upper = any(c.isupper() for c in password)
        self.req_upper.setText("Заглавная буква")
        self.req_upper.setStyleSheet("color: green;" if has_upper else "color: red;")

        has_lower = any(c.islower() for c in password)
        self.req_lower.setText("Строчная буква")
        self.req_lower.setStyleSheet("color: green;" if has_lower else "color: red;")

        has_digit = any(c.isdigit() for c in password)
        self.req_digit.setText("Цифра")
        self.req_digit.setStyleSheet("color: green;" if has_digit else "color: red;")

        has_special = any(not c.isalnum() for c in password)
        self.req_special.setText("Спецсимвол (!@#$%^&*)")
        self.req_special.setStyleSheet("color: green;" if has_special else "color: red;")

        self.check_passwords_match()

    def check_passwords_match(self):
        new = self.new_password.get()
        confirm = self.confirm_password.get()

        if not confirm:
            self.match_label.setText("")
        elif new == confirm:
            self.match_label.setText("Пароли совпадают")
            self.match_label.setStyleSheet("color: green; font-size: 10px; font-weight: bold;")
        else:
            self.match_label.setText("Пароли не совпадают")
            self.match_label.setStyleSheet("color: red; font-size: 10px; font-weight: bold;")

    def change_password(self):
        current = self.current_password.get()
        new = self.new_password.get()
        confirm = self.confirm_password.get()

        if not current:
            QMessageBox.critical(self, "Ошибка", "Введите текущий пароль")
            self.current_password.entry.setFocus()
            return

        if not new:
            QMessageBox.critical(self, "Ошибка", "Введите новый пароль")
            self.new_password.entry.setFocus()
            return

        if not confirm:
            QMessageBox.critical(self, "Ошибка", "Подтвердите новый пароль")
            self.confirm_password.entry.setFocus()
            return

        if new != confirm:
            QMessageBox.critical(self, "Ошибка", "Новый пароль и подтверждение не совпадают")
            self.confirm_password.entry.setFocus()
            return

        is_strong, errors = self.auth._check_password_strength(new)
        if not is_strong:
            error_message = "Пароль не соответствует требованиям:\n\n"
            for error in errors:
                error_message += f"• {error}\n"
            QMessageBox.critical(self, "Ошибка", error_message)
            self.new_password.entry.setFocus()
            return

        success, errors = self.auth.change_password(current, new)

        if success:
            QMessageBox.information(
                self,
                "Успех",
                "Пароль успешно изменен!\n\nВсе записи были перешифрованы."
            )
            self.success = True
            self.accept()
        else:
            error_message = "Ошибка при смене пароля:\n\n"
            for error in errors:
                error_message += f"• {error}\n"
            QMessageBox.critical(self, "Ошибка", error_message)