from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout,
    QLabel, QPushButton, QLineEdit, QGroupBox,
    QComboBox, QSpinBox, QCheckBox, QTextEdit,
    QTableWidget, QTableWidgetItem, QMessageBox,
    QTabWidget, QWidget, QRadioButton, QButtonGroup
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont
from typing import Optional, Dict, Any, List
from datetime import datetime


# UI-3: Диалог шеринга записи
class SharingDialog(QDialog):
    """
    UI-3: Диалог безопасного шеринга записи.
    Включает:
    - Выбор получателя (из контактов или новый)
    - Настройки прав (read, edit, срок действия)
    - Метод доставки (QR, файл, ссылка)
    - История и статус шерингов
    """

    def __init__(self, parent, entry: Dict[str, Any],
                 sharing_service, qr_service=None):
        super().__init__(parent)
        self.entry = entry
        self.sharing_service = sharing_service
        self.qr_service = qr_service
        self._contacts: List[Dict[str, Any]] = []
        self._share_result: Optional[Dict[str, Any]] = None

        self.setWindowTitle(f"Поделиться: {entry.get('title', '—')}")
        self.setModal(True)
        self.setMinimumSize(580, 520)

        self._load_contacts()
        self._setup_ui()

    def _load_contacts(self):
        try:
            self._contacts = self.sharing_service.get_available_recipients()
        except Exception:
            self._contacts = []

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        title = QLabel(f"Поделиться записью: {self.entry.get('title', '—')}")
        title.setFont(QFont("", 13, QFont.Weight.Bold))
        layout.addWidget(title)

        tabs = QTabWidget()
        tabs.addTab(self._build_share_tab(), "Отправить")
        tabs.addTab(self._build_history_tab(), "История")
        layout.addWidget(tabs)

        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        self.share_btn = QPushButton("Создать пакет шеринга")
        self.share_btn.setDefault(True)
        self.share_btn.clicked.connect(self._do_share)
        btn_layout.addWidget(self.share_btn)
        close_btn = QPushButton("Закрыть")
        close_btn.clicked.connect(self.reject)
        btn_layout.addWidget(close_btn)
        layout.addLayout(btn_layout)

    # ── Вкладка «Отправить» ──

    def _build_share_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # UI-3: Выбор получателя
        recipient_group = QGroupBox("Получатель")
        recipient_layout = QVBoxLayout(recipient_group)

        self.recipient_mode_group = QButtonGroup(self)
        rb_existing = QRadioButton("Из контактов")
        rb_new = QRadioButton("Новый получатель")
        rb_existing.setChecked(True)
        self.recipient_mode_group.addButton(rb_existing, 0)
        self.recipient_mode_group.addButton(rb_new, 1)
        rb_existing.toggled.connect(self._on_recipient_mode_changed)

        mode_layout = QHBoxLayout()
        mode_layout.addWidget(rb_existing)
        mode_layout.addWidget(rb_new)
        mode_layout.addStretch()
        recipient_layout.addLayout(mode_layout)

        # Существующий контакт
        self.contact_combo = QComboBox()
        self.contact_combo.addItem("— Без конкретного получателя —", userData=None)
        for c in self._contacts:
            label = c.get("name", "—")
            if c.get("public_key_fingerprint"):
                label += f" 🔑"
            self.contact_combo.addItem(label, userData=c.get("id"))
        recipient_layout.addWidget(self.contact_combo)

        # Новый получатель
        self.new_recipient_widget = QWidget()
        new_layout = QFormLayout(self.new_recipient_widget)
        self.new_name_input = QLineEdit()
        self.new_name_input.setPlaceholderText("Имя получателя")
        new_layout.addRow("Имя:", self.new_name_input)
        self.new_recipient_widget.setVisible(False)
        recipient_layout.addWidget(self.new_recipient_widget)

        layout.addWidget(recipient_group)

        # UI-3: Метод шифрования
        method_group = QGroupBox("Метод шифрования")
        method_layout = QVBoxLayout(method_group)

        self.method_combo = QComboBox()
        self.method_combo.addItem("🔐 Пароль", userData="password")
        self.method_combo.addItem("🔑 Публичный ключ", userData="public_key")
        self.method_combo.addItem("⏰ Временная ссылка", userData="time_limited")
        self.method_combo.currentIndexChanged.connect(self._on_method_changed)
        method_layout.addWidget(self.method_combo)

        self.method_desc = QLabel()
        self.method_desc.setStyleSheet("color: gray; font-size: 11px;")
        self.method_desc.setWordWrap(True)
        method_layout.addWidget(self.method_desc)

        layout.addWidget(method_group)

        # UI-3: Права доступа и срок действия
        perms_group = QGroupBox("Права доступа")
        perms_layout = QFormLayout(perms_group)

        self.perm_read = QCheckBox("Читать запись")
        self.perm_read.setChecked(True)
        self.perm_read.setEnabled(False)
        perms_layout.addRow("", self.perm_read)

        self.perm_edit = QCheckBox("Редактировать запись")
        perms_layout.addRow("", self.perm_edit)

        self.perm_password = QCheckBox("Видеть пароль")
        self.perm_password.setChecked(True)
        perms_layout.addRow("", self.perm_password)

        self.perm_notes = QCheckBox("Видеть заметки")
        self.perm_notes.setChecked(True)
        perms_layout.addRow("", self.perm_notes)

        self.expiry_spin = QSpinBox()
        self.expiry_spin.setRange(1, 30)
        self.expiry_spin.setValue(7)
        self.expiry_spin.setSuffix(" дн.")
        perms_layout.addRow("Срок действия:", self.expiry_spin)

        layout.addWidget(perms_group)

        # UI-3: Метод доставки
        delivery_group = QGroupBox("Способ доставки")
        delivery_layout = QHBoxLayout(delivery_group)

        self.delivery_btn_group = QButtonGroup(self)
        for key, label in [("file", "📁 Файл"), ("qr", "📷 QR-код"), ("link", "🔗 Ссылка")]:
            rb = QRadioButton(label)
            rb.setProperty("delivery_key", key)
            if key == "file":
                rb.setChecked(True)
            self.delivery_btn_group.addButton(rb)
            delivery_layout.addWidget(rb)
        delivery_layout.addStretch()

        layout.addWidget(delivery_group)
        layout.addStretch()

        self._on_method_changed(0)
        return widget

    # ── Вкладка «История» ──

    def _build_history_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # UI-3: История шерингов для этой записи
        self.history_table = QTableWidget(0, 4)
        self.history_table.setHorizontalHeaderLabels(["Получатель", "Метод", "Истекает", "Статус"])
        self.history_table.horizontalHeader().setStretchLastSection(True)
        self.history_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        layout.addWidget(self.history_table)

        refresh_btn = QPushButton("Обновить")
        refresh_btn.clicked.connect(self._load_history)
        layout.addWidget(refresh_btn)

        self._load_history()
        return widget

    def _load_history(self):
        self.history_table.setRowCount(0)
        try:
            shares = self.sharing_service._get_active_shares_for_entry(
                self.entry.get("id", "")
            )
            for share in shares:
                row = self.history_table.rowCount()
                self.history_table.insertRow(row)
                expires = share.get("expires_at", "—")
                now = datetime.utcnow().isoformat()
                is_expired = isinstance(expires, str) and expires < now
                status = "Истёк" if is_expired else "Активен"
                for col, val in enumerate([
                    share.get("recipient") or "Любой",
                    share.get("method", "—"),
                    str(expires)[:10] if expires else "—",
                    status
                ]):
                    item = QTableWidgetItem(val)
                    if is_expired:
                        item.setForeground(Qt.GlobalColor.gray)
                    self.history_table.setItem(row, col, item)
        except Exception:
            pass

    # ── Реакции на изменения ──

    def _on_recipient_mode_changed(self, checked: bool):
        use_existing = self.recipient_mode_group.checkedId() == 0
        self.contact_combo.setVisible(use_existing)
        self.new_recipient_widget.setVisible(not use_existing)

    def _on_method_changed(self, _index):
        method = self.method_combo.currentData()
        descs = {
            "password": "Зашифровать файл с паролем. Пароль нужно передать отдельным каналом.",
            "public_key": "Зашифровать публичным ключом получателя. Самый безопасный метод.",
            "time_limited": "Создать ссылку с ограниченным сроком действия.",
        }
        self.method_desc.setText(descs.get(method, ""))

    def _get_delivery_method(self) -> str:
        for btn in self.delivery_btn_group.buttons():
            if btn.isChecked():
                return btn.property("delivery_key")
        return "file"

    # ── Шеринг ──

    def _do_share(self):
        entry_id = self.entry.get("id")
        if not entry_id:
            QMessageBox.warning(self, "Ошибка", "Не удалось определить ID записи.")
            return

        # Получатель
        use_existing = self.recipient_mode_group.checkedId() == 0
        recipient_id = None
        if use_existing:
            recipient_id = self.contact_combo.currentData()
        else:
            name = self.new_name_input.text().strip()
            if name:
                try:
                    contact = self.sharing_service.add_recipient(name=name)
                    recipient_id = contact.get("id")
                except Exception as e:
                    QMessageBox.warning(self, "Ошибка", f"Не удалось добавить контакт:\n{e}")
                    return

        permissions = {
            "access_type": "read_write" if self.perm_edit.isChecked() else "read_only",
            "read": True,
            "edit": self.perm_edit.isChecked(),
            "read_password": self.perm_password.isChecked(),
            "read_notes": self.perm_notes.isChecked(),
            "read_totp": False,
            "share": False,
        }

        try:
            self.share_btn.setEnabled(False)
            self.share_btn.setText("Создаётся...")

            result = self.sharing_service.share_entry(
                entry_id=entry_id,
                sharer="current_user",
                recipient_id=recipient_id,
                method=self.method_combo.currentData(),
                expires_in_days=self.expiry_spin.value(),
                permissions=permissions,
                delivery_channel=self._get_delivery_method(),
            )
            self._share_result = result

            msg = f"Пакет шеринга создан!\nShare ID: {result.get('share_id', '—')}"
            if result.get("share_password"):
                msg += f"\n\nПароль для получателя:\n{result['share_password']}"
                msg += "\n\n⚠️ Передайте пароль отдельным каналом!"
            if result.get("share_link"):
                msg += f"\n\nСсылка:\n{result['share_link']}"

            QMessageBox.information(self, "Шеринг создан", msg)
            self._load_history()

        except Exception as e:
            QMessageBox.critical(self, "Ошибка шеринга", str(e))
        finally:
            self.share_btn.setEnabled(True)
            self.share_btn.setText("Создать пакет шеринга")

    def get_share_result(self) -> Optional[Dict[str, Any]]:
        return self._share_result