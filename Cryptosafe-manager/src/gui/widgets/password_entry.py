from PyQt6.QtWidgets import QWidget, QHBoxLayout, QLineEdit, QCheckBox
from PyQt6.QtCore import Qt


class PasswordEntry(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self.entry = QLineEdit()
        self.entry.setEchoMode(QLineEdit.EchoMode.Password)
        layout.addWidget(self.entry)

        self.show_checkbox = QCheckBox("Show")
        self.show_checkbox.stateChanged.connect(self.toggle_password)
        layout.addWidget(self.show_checkbox)

    def toggle_password(self, state):
        if state == 2:
            self.entry.setEchoMode(QLineEdit.EchoMode.Normal)
        else:
            self.entry.setEchoMode(QLineEdit.EchoMode.Password)

    def get(self):
        return self.entry.text()

    def clear(self):
        self.entry.clear()