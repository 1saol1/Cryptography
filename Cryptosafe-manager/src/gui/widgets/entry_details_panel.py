from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel,
                             QTextEdit, QFrame, QScrollArea, QPushButton,
                             QMessageBox)
from PyQt6.QtCore import pyqtSignal
from PyQt6.QtGui import QFont
import json
from typing import Dict, Any


class EntryDetailsPanel(QWidget):
    entry_selected = pyqtSignal(dict)

    def __init__(self, parent=None, db_connection=None, verifier=None):
        super().__init__(parent)
        self.db = db_connection
        self.verifier = verifier
        self.current_entry = None
        self.current_sequence = None

        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)

        title_label = QLabel("📋 Детали записи")
        title_label.setStyleSheet("font-size: 14px; font-weight: bold; margin-bottom: 10px;")
        layout.addWidget(title_label)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)

        scroll_content = QWidget()
        scroll_layout = QVBoxLayout(scroll_content)

        self.status_frame = QFrame()
        self.status_frame.setFrameShape(QFrame.Shape.StyledPanel)
        self.status_layout = QVBoxLayout(self.status_frame)

        self.status_label = QLabel("Статус верификации: Не выбран")
        self.status_label.setStyleSheet("font-weight: bold;")
        self.status_layout.addWidget(self.status_label)

        scroll_layout.addWidget(self.status_frame)

        self.chain_frame = QFrame()
        self.chain_frame.setFrameShape(QFrame.Shape.StyledPanel)
        self.chain_layout = QVBoxLayout(self.chain_frame)

        self.chain_label = QLabel("Hash Chain")
        self.chain_label.setStyleSheet("font-weight: bold;")
        self.chain_layout.addWidget(self.chain_label)

        self.prev_hash_label = QLabel("Previous hash: -")
        self.prev_hash_label.setWordWrap(True)
        self.chain_layout.addWidget(self.prev_hash_label)

        self.curr_hash_label = QLabel("Current hash: -")
        self.curr_hash_label.setWordWrap(True)
        self.chain_layout.addWidget(self.curr_hash_label)

        scroll_layout.addWidget(self.chain_frame)

        # Entry data
        self.data_frame = QFrame()
        self.data_frame.setFrameShape(QFrame.Shape.StyledPanel)
        self.data_layout = QVBoxLayout(self.data_frame)

        self.data_label = QLabel("Данные записи")
        self.data_label.setStyleSheet("font-weight: bold;")
        self.data_layout.addWidget(self.data_label)

        self.data_text = QTextEdit()
        self.data_text.setReadOnly(True)
        self.data_text.setFont(QFont("Courier New", 10))
        self.data_layout.addWidget(self.data_text)

        scroll_layout.addWidget(self.data_frame)

        # Verify button
        self.verify_btn = QPushButton("Проверить подпись")
        self.verify_btn.clicked.connect(self.verify_signature)
        scroll_layout.addWidget(self.verify_btn)

        scroll.setWidget(scroll_content)
        layout.addWidget(scroll)

        self.setMinimumWidth(400)

    def load_entry(self, row_data: Dict[str, Any]):
        self.current_entry = row_data

        try:
            entry_data = row_data.get('entry_data', {})
            if isinstance(entry_data, bytes):
                entry_data = entry_data.decode('utf-8')
            if isinstance(entry_data, str):
                entry_data = json.loads(entry_data)

            self.current_sequence = row_data.get('sequence_number') or entry_data.get('sequence_number')

            formatted_json = json.dumps(entry_data, indent=2, ensure_ascii=False)
            self.data_text.setPlainText(formatted_json)

            self.prev_hash_label.setText(f"Previous hash: {entry_data.get('previous_hash', '-')[:32]}...")
            self.curr_hash_label.setText(f"Current hash: {row_data.get('entry_hash', '-')[:32]}...")

            self.update_verification_status()

        except Exception as e:
            self.data_text.setPlainText(f"Error parsing entry: {e}")

    def update_verification_status(self):
        if not self.current_entry or not self.verifier:
            self.status_label.setText("Статус верификации: Не выбран")
            self.status_label.setStyleSheet("font-weight: bold;")
            return

        try:
            entry_data = self.current_entry.get('entry_data', b'')
            if isinstance(entry_data, bytes):
                entry_data = entry_data.decode('utf-8')

            signature_hex = self.current_entry.get('signature', '')
            signature = bytes.fromhex(signature_hex)

            is_valid = self.verifier.signer.verify(entry_data.encode(), signature)

            if is_valid:
                self.status_label.setText("✅ Статус верификации: ПОДПИСЬ ВАЛИДНА")
                self.status_label.setStyleSheet("font-weight: bold; color: green;")
                self.status_frame.setStyleSheet("background-color: #e8f5e9;")
            else:
                self.status_label.setText("❌ Статус верификации: ПОДПИСЬ НЕВАЛИДНА!")
                self.status_label.setStyleSheet("font-weight: bold; color: red;")
                self.status_frame.setStyleSheet("background-color: #ffebee;")

        except Exception as e:
            self.status_label.setText(f"⚠️ Статус верификации: Ошибка проверки")
            self.status_label.setStyleSheet("font-weight: bold; color: orange;")

    def verify_signature(self):
        if not self.current_entry or not self.verifier:
            QMessageBox.warning(self, "Ошибка", "Нет выбранной записи или верификатора")
            return

        try:
            entry_data = self.current_entry.get('entry_data', b'')
            if isinstance(entry_data, bytes):
                entry_data = entry_data.decode('utf-8')

            signature_hex = self.current_entry.get('signature', '')
            signature = bytes.fromhex(signature_hex)

            is_valid = self.verifier.signer.verify(entry_data.encode(), signature)

            chain_ok = True
            chain_msg = ""

            if self.current_sequence and self.current_sequence > 0:
                cursor = self.db.execute(
                    "SELECT entry_hash FROM audit_log WHERE sequence_number = ?",
                    (self.current_sequence - 1,)
                )
                prev_row = cursor.fetchone()
                if prev_row:
                    expected_hash = prev_row[0]
                    actual_hash = self.current_entry.get('previous_hash', '')
                    if expected_hash != actual_hash:
                        chain_ok = False
                        chain_msg = "\n\n⚠️ Hash chain break detected!"

            if is_valid and chain_ok:
                QMessageBox.information(
                    self,
                    "Результат верификации",
                    "Подпись валидна!\n"
                    "Hash chain целостен!"
                )
            elif is_valid and not chain_ok:
                QMessageBox.warning(
                    self,
                    "Результат верификации",
                    f"Подпись валидна!{chain_msg}"
                )
            else:
                QMessageBox.critical(
                    self,
                    "Результат верификации",
                    f"❌ Подпись НЕВАЛИДНА!{chain_msg}"
                )

        except Exception as e:
            QMessageBox.critical(self, "Ошибка", f"Ошибка верификации: {e}")

    def clear(self):
        self.current_entry = None
        self.current_sequence = None
        self.data_text.clear()
        self.prev_hash_label.setText("Previous hash: -")
        self.curr_hash_label.setText("Current hash: -")
        self.status_label.setText("Статус верификации: Не выбран")
        self.status_label.setStyleSheet("font-weight: bold;")
        self.status_frame.setStyleSheet("")