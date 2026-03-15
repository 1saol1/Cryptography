import os
import sys
from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel,
                             QLineEdit, QPushButton, QMessageBox, QFileDialog,
                             QGroupBox, QGridLayout)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, BASE_DIR)

from .password_entry import PasswordEntry


class SetupWindow(QDialog):

    def __init__(self, parent, auth):
        super().__init__(parent)
        self.auth = auth
        self.completed = False

        self.setWindowTitle("Первоначальная настройка CryptoSafe")
        self.setFixedSize(650, 800)
        self.setModal(True)

        self.center_window()

        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(20)
        main_layout.setContentsMargins(30, 25, 30, 25)

        title = QLabel("Добро пожаловать в CryptoSafe Manager")
        title.setFont(QFont("Arial", 18, QFont.Weight.Bold))
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setWordWrap(True)
        main_layout.addWidget(title)

        subtitle = QLabel("Создайте мастер-пароль и выберите место для базы данных")
        subtitle.setFont(QFont("Arial", 12))
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        subtitle.setWordWrap(True)
        main_layout.addWidget(subtitle)

        pwd_group = QGroupBox("Мастер-пароль")
        pwd_group.setFont(QFont("Arial", 12, QFont.Weight.Bold))

        pwd_layout = QGridLayout(pwd_group)
        pwd_layout.setVerticalSpacing(10)
        pwd_layout.setHorizontalSpacing(15)

        pwd_layout.addWidget(QLabel("Пароль:"), 0, 0, Qt.AlignmentFlag.AlignRight)
        self.password1 = PasswordEntry()
        self.password1.entry.textChanged.connect(self.update_strength_indicator)
        pwd_layout.addWidget(self.password1, 0, 1)

        self.strength_label = QLabel("Введите пароль")
        self.strength_label.setStyleSheet("color: orange; font-size: 10px;")
        pwd_layout.addWidget(self.strength_label, 1, 1)

        pwd_layout.addWidget(QLabel("Подтверждение:"), 2, 0, Qt.AlignmentFlag.AlignRight)
        self.password2 = PasswordEntry()
        self.password2.entry.textChanged.connect(self.check_passwords_match)
        pwd_layout.addWidget(self.password2, 2, 1)

        self.match_label = QLabel("")
        self.match_label.setStyleSheet("font-size: 10px;")
        pwd_layout.addWidget(self.match_label, 3, 1)

        req_label = QLabel("Требования к паролю:")
        req_label.setFont(QFont("Arial", 10, QFont.Weight.Bold))
        pwd_layout.addWidget(req_label, 4, 0, 1, 2)

        req_grid = QGridLayout()

        self.req_length = QLabel("Минимум 12 символов")
        self.req_length.setStyleSheet("color: red;")
        req_grid.addWidget(self.req_length, 0, 0)

        self.req_upper = QLabel("Заглавная буква")
        self.req_upper.setStyleSheet("color: red;")
        req_grid.addWidget(self.req_upper, 0, 1)

        self.req_lower = QLabel("Строчная буква")
        self.req_lower.setStyleSheet("color: red;")
        req_grid.addWidget(self.req_lower, 1, 0)

        self.req_digit = QLabel("Цифра")
        self.req_digit.setStyleSheet("color: red;")
        req_grid.addWidget(self.req_digit, 1, 1)

        self.req_special = QLabel("Спецсимвол (!@#$%^&*)")
        self.req_special.setStyleSheet("color: red;")
        req_grid.addWidget(self.req_special, 2, 0, 1, 2)

        pwd_layout.addLayout(req_grid, 5, 0, 1, 2)

        main_layout.addWidget(pwd_group)

        db_group = QGroupBox("Расположение базы данных")
        db_group.setFont(QFont("Arial", 12, QFont.Weight.Bold))

        db_layout = QVBoxLayout(db_group)

        path_layout = QHBoxLayout()

        self.db_path = QLineEdit()
        self.db_path.setText(os.path.abspath("cryptosafe.db"))
        self.db_path.setFont(QFont("Arial", 10))
        self.db_path.setMinimumHeight(30)
        path_layout.addWidget(self.db_path)

        browse_btn = QPushButton("Обзор")
        browse_btn.setFont(QFont("Arial", 10))
        browse_btn.setFixedSize(100, 30)
        browse_btn.clicked.connect(self.choose_db_path)
        path_layout.addWidget(browse_btn)

        db_layout.addLayout(path_layout)

        db_info = QLabel("База данных будет создана автоматически")
        db_info.setStyleSheet("color: gray; font-style: italic;")
        db_info.setAlignment(Qt.AlignmentFlag.AlignCenter)
        db_layout.addWidget(db_info)

        main_layout.addWidget(db_group)

        crypto_group = QGroupBox("Параметры шифрования")
        crypto_group.setFont(QFont("Arial", 12, QFont.Weight.Bold))

        crypto_layout = QVBoxLayout(crypto_group)

        crypto_text = QLabel(
            "В следующих спринтах здесь будет выбор алгоритма,\n"
            "количества итераций, типа соли и других настроек"
        )
        crypto_text.setAlignment(Qt.AlignmentFlag.AlignCenter)
        crypto_text.setStyleSheet("color: gray; padding: 20px;")
        crypto_text.setWordWrap(True)
        crypto_layout.addWidget(crypto_text)

        main_layout.addWidget(crypto_group)

        button_layout = QHBoxLayout()
        button_layout.addStretch()

        cancel_btn = QPushButton("Отмена")
        cancel_btn.setFont(QFont("Arial", 11))
        cancel_btn.setFixedSize(150, 40)
        cancel_btn.clicked.connect(self.cancel)
        button_layout.addWidget(cancel_btn)

        save_btn = QPushButton("Завершить настройку")
        save_btn.setFont(QFont("Arial", 11, QFont.Weight.Bold))
        save_btn.setFixedSize(200, 40)
        save_btn.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                border-radius: 5px;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
        """)
        save_btn.clicked.connect(self.try_save)
        button_layout.addWidget(save_btn)

        main_layout.addLayout(button_layout)

    def center_window(self):
        screen = self.screen().geometry()
        x = (screen.width() - self.width()) // 2
        y = (screen.height() - self.height()) // 2
        self.move(x, y)

    def update_strength_indicator(self):
        password = self.password1.get()

        if not password:
            text = "Введите пароль"
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
        pwd1 = self.password1.get()
        pwd2 = self.password2.get()

        if not pwd2:
            self.match_label.setText("")
        elif pwd1 == pwd2:
            self.match_label.setText("Пароли совпадают")
            self.match_label.setStyleSheet("color: green; font-size: 10px; font-weight: bold;")
        else:
            self.match_label.setText("Пароли не совпадают")
            self.match_label.setStyleSheet("color: red; font-size: 10px; font-weight: bold;")

    def choose_db_path(self):
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Выберите место для базы данных",
            os.path.abspath("cryptosafe.db"),
            "SQLite Database (*.db);;All Files (*.*)"
        )
        if path:
            self.db_path.setText(path)

    def try_save(self):

        password1 = self.password1.get()
        password2 = self.password2.get()

        if not password1:
            QMessageBox.critical(self, "Ошибка", "Пароль не может быть пустым")
            self.password1.entry.setFocus()
            return

        if password1 != password2:
            QMessageBox.critical(self, "Ошибка", "Пароли не совпадают")
            self.password2.entry.setFocus()
            return

        is_strong, errors = self.auth._check_password_strength(password1)
        if not is_strong:
            error_message = "Пароль не соответствует требованиям безопасности:\n\n"
            for error in errors:
                error_message += f"• {error}\n"

            QMessageBox.critical(self, "Ошибка", error_message)
            self.password1.entry.setFocus()
            return

        db_path = self.db_path.text()
        if not db_path:
            QMessageBox.critical(self, "Ошибка", "Укажите путь к базе данных")
            return

        try:
            success, reg_errors = self.auth.register(password1)
            if success:
                self.completed = True
                QMessageBox.information(
                    self,
                    "Успех",
                    "Мастер-пароль успешно создан!\n\nТеперь вы можете войти в систему."
                )
                self.accept()
            else:
                error_message = "Ошибка при регистрации:\n\n"
                for error in reg_errors or ["Неизвестная ошибка"]:
                    error_message += f"• {error}\n"
                QMessageBox.critical(self, "Ошибка", error_message)

        except Exception as e:
            QMessageBox.critical(self, "Ошибка", f"Ошибка при регистрации:\n\n{str(e)}")

    def cancel(self):
        self.completed = False
        self.reject()