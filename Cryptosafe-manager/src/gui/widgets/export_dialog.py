from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout,
    QLabel, QPushButton, QComboBox, QLineEdit,
    QCheckBox, QTreeWidget, QTreeWidgetItem, QGroupBox,
    QRadioButton, QButtonGroup, QTextEdit, QSplitter,
    QMessageBox, QFileDialog, QProgressBar, QSpinBox,
    QStackedWidget, QWidget
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QFont
from typing import Optional, List, Dict, Any

class ExportDialog(QDialog):

    FORMATS = {
        "encrypted_json": {
            "name": "Зашифрованный JSON (рекомендуется)",
            "description": "Нативный формат CryptoSafe. AES-256-GCM шифрование, полные метаданные.",
            "requires_password": True,
            "supports_public_key": True,
        },
        "csv": {
            "name": "CSV (миграция)",
            "description": "Текстовый формат. Подходит для переноса в другие менеджеры паролей.",
            "requires_password": False,
            "supports_public_key": False,
        },
        "bitwarden_json": {
            "name": "Bitwarden JSON",
            "description": "Совместимый формат для импорта в Bitwarden.",
            "requires_password": False,
            "supports_public_key": False,
        },
        "lastpass_csv": {
            "name": "LastPass CSV",
            "description": "CSV формат для импорта в LastPass.",
            "requires_password": False,
            "supports_public_key": False,
        },
    }

    def __init__(self, parent, entry_manager, vault_exporter):
        super().__init__(parent)
        self.entry_manager = entry_manager
        self.vault_exporter = vault_exporter
        self._entries: List[Dict[str, Any]] = []
        self._preview_data: Optional[Dict[str, Any]] = None

        self.setWindowTitle("Экспорт хранилища")
        self.setModal(True)
        self.setMinimumSize(700, 550)

        self._load_entries()
        self._setup_ui()

    def _load_entries(self):
        try:
            self._entries = self.entry_manager.get_all_entries()
        except Exception:
            self._entries = []

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(10)

        # Заголовок
        title = QLabel("Экспорт записей")
        title.setFont(QFont("", 13, QFont.Weight.Bold))
        layout.addWidget(title)

        splitter = QSplitter(Qt.Orientation.Horizontal)

        # ── Левая панель: формат + шифрование ──
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(0, 0, 8, 0)

        # UI-1: Выбор формата с описаниями
        fmt_group = QGroupBox("Формат экспорта")
        fmt_layout = QVBoxLayout(fmt_group)

        self.format_combo = QComboBox()
        for key, info in self.FORMATS.items():
            self.format_combo.addItem(info["name"], userData=key)
        self.format_combo.currentIndexChanged.connect(self._on_format_changed)
        fmt_layout.addWidget(self.format_combo)

        self.format_description = QLabel()
        self.format_description.setWordWrap(True)
        self.format_description.setStyleSheet("color: gray; font-size: 11px;")
        fmt_layout.addWidget(self.format_description)

        left_layout.addWidget(fmt_group)

        # UI-1: Панель настроек шифрования
        self.enc_group = QGroupBox("Шифрование")
        enc_layout = QFormLayout(self.enc_group)

        # Метод защиты
        self.enc_method_group = QButtonGroup(self)
        self.radio_password = QRadioButton("Пароль")
        self.radio_pubkey = QRadioButton("Публичный ключ")
        self.radio_password.setChecked(True)
        self.enc_method_group.addButton(self.radio_password)
        self.enc_method_group.addButton(self.radio_pubkey)
        self.radio_password.toggled.connect(self._on_enc_method_changed)

        method_layout = QHBoxLayout()
        method_layout.addWidget(self.radio_password)
        method_layout.addWidget(self.radio_pubkey)
        method_layout.addStretch()
        enc_layout.addRow("Метод:", method_layout)

        self.password_input = QLineEdit()
        self.password_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.password_input.setPlaceholderText("Введите пароль для экспорта")
        enc_layout.addRow("Пароль:", self.password_input)

        self.password_confirm = QLineEdit()
        self.password_confirm.setEchoMode(QLineEdit.EchoMode.Password)
        self.password_confirm.setPlaceholderText("Подтвердите пароль")
        enc_layout.addRow("Подтверждение:", self.password_confirm)

        self.pubkey_input = QLineEdit()
        self.pubkey_input.setPlaceholderText("Путь к файлу публичного ключа (.pem)")
        self.pubkey_browse_btn = QPushButton("Обзор...")
        self.pubkey_browse_btn.clicked.connect(self._browse_pubkey)
        pubkey_layout = QHBoxLayout()
        pubkey_layout.addWidget(self.pubkey_input)
        pubkey_layout.addWidget(self.pubkey_browse_btn)
        enc_layout.addRow("Ключ:", pubkey_layout)

        # Сила шифрования
        self.enc_strength = QComboBox()
        self.enc_strength.addItem("256-бит (рекомендуется)", userData=256)
        self.enc_strength.addItem("128-бит", userData=128)
        enc_layout.addRow("Стойкость:", self.enc_strength)

        # Сжатие
        self.compress_check = QCheckBox("GZIP сжатие")
        enc_layout.addRow("", self.compress_check)

        left_layout.addWidget(self.enc_group)
        left_layout.addStretch()

        splitter.addWidget(left_widget)

        # ── Правая панель: выбор записей ──
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        right_layout.setContentsMargins(8, 0, 0, 0)

        entries_group = QGroupBox("Записи для экспорта")
        entries_layout = QVBoxLayout(entries_group)

        # Кнопки выбора всех/снятия
        sel_layout = QHBoxLayout()
        select_all_btn = QPushButton("Выбрать все")
        select_all_btn.clicked.connect(self._select_all)
        deselect_all_btn = QPushButton("Снять все")
        deselect_all_btn.clicked.connect(self._deselect_all)
        sel_layout.addWidget(select_all_btn)
        sel_layout.addWidget(deselect_all_btn)
        sel_layout.addStretch()
        entries_layout.addLayout(sel_layout)

        # UI-1: Дерево записей с чекбоксами
        self.entries_tree = QTreeWidget()
        self.entries_tree.setHeaderLabels(["Название", "Категория"])
        self.entries_tree.setColumnWidth(0, 200)
        self.entries_tree.itemChanged.connect(self._on_entry_check_changed)
        entries_layout.addWidget(self.entries_tree)

        self.selected_count_label = QLabel("Выбрано: 0 из 0")
        self.selected_count_label.setStyleSheet("font-size: 11px; color: gray;")
        entries_layout.addWidget(self.selected_count_label)

        right_layout.addWidget(entries_group)

        # UI-1: Предпросмотр
        preview_group = QGroupBox("Предпросмотр")
        preview_layout = QVBoxLayout(preview_group)

        preview_btn = QPushButton("Обновить предпросмотр")
        preview_btn.clicked.connect(self._update_preview)
        preview_layout.addWidget(preview_btn)

        self.preview_text = QTextEdit()
        self.preview_text.setReadOnly(True)
        self.preview_text.setMaximumHeight(120)
        self.preview_text.setPlaceholderText("Нажмите «Обновить предпросмотр»...")
        preview_layout.addWidget(self.preview_text)

        right_layout.addWidget(preview_group)

        splitter.addWidget(right_widget)
        splitter.setSizes([300, 380])
        layout.addWidget(splitter)

        # Кнопки
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        self.export_btn = QPushButton("Экспортировать")
        self.export_btn.setDefault(True)
        self.export_btn.clicked.connect(self._do_export)
        btn_layout.addWidget(self.export_btn)

        cancel_btn = QPushButton("Отмена")
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(cancel_btn)

        layout.addLayout(btn_layout)

        # Инициализация
        self._populate_entries_tree()
        self._on_format_changed(0)
        self._on_enc_method_changed()

    # ── Заполнение дерева ──

    def _populate_entries_tree(self):
        self.entries_tree.blockSignals(True)
        self.entries_tree.clear()

        # Группируем по категории
        categories: Dict[str, List] = {}
        for entry in self._entries:
            cat = entry.get("category", "Общее")
            categories.setdefault(cat, []).append(entry)

        for cat, entries in sorted(categories.items()):
            cat_item = QTreeWidgetItem(self.entries_tree, [cat, ""])
            cat_item.setFlags(cat_item.flags() | Qt.ItemFlag.ItemIsUserCheckable
                              | Qt.ItemFlag.ItemIsAutoTristate)
            cat_item.setCheckState(0, Qt.CheckState.Checked)
            for entry in entries:
                entry_item = QTreeWidgetItem(cat_item, [
                    entry.get("title", "—"),
                    entry.get("category", "")
                ])
                entry_item.setFlags(entry_item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
                entry_item.setCheckState(0, Qt.CheckState.Checked)
                entry_item.setData(0, Qt.ItemDataRole.UserRole, entry.get("id"))

        self.entries_tree.expandAll()
        self.entries_tree.blockSignals(False)
        self._update_selected_count()

    def _select_all(self):
        self.entries_tree.blockSignals(True)
        root = self.entries_tree.invisibleRootItem()
        for i in range(root.childCount()):
            cat = root.child(i)
            cat.setCheckState(0, Qt.CheckState.Checked)
            for j in range(cat.childCount()):
                cat.child(j).setCheckState(0, Qt.CheckState.Checked)
        self.entries_tree.blockSignals(False)
        self._update_selected_count()

    def _deselect_all(self):
        self.entries_tree.blockSignals(True)
        root = self.entries_tree.invisibleRootItem()
        for i in range(root.childCount()):
            cat = root.child(i)
            cat.setCheckState(0, Qt.CheckState.Unchecked)
            for j in range(cat.childCount()):
                cat.child(j).setCheckState(0, Qt.CheckState.Unchecked)
        self.entries_tree.blockSignals(False)
        self._update_selected_count()

    def _on_entry_check_changed(self, item, column):
        if column == 0:
            self._update_selected_count()

    def _update_selected_count(self):
        selected = len(self._get_selected_entry_ids())
        total = len(self._entries)
        self.selected_count_label.setText(f"Выбрано: {selected} из {total}")

    def _get_selected_entry_ids(self) -> List[str]:
        ids = []
        root = self.entries_tree.invisibleRootItem()
        for i in range(root.childCount()):
            cat = root.child(i)
            for j in range(cat.childCount()):
                child = cat.child(j)
                if child.checkState(0) == Qt.CheckState.Checked:
                    entry_id = child.data(0, Qt.ItemDataRole.UserRole)
                    if entry_id:
                        ids.append(entry_id)
        return ids

    def _on_format_changed(self, index):
        key = self.format_combo.currentData()
        info = self.FORMATS.get(key, {})
        self.format_description.setText(info.get("description", ""))

        requires_password = info.get("requires_password", False)
        self.enc_group.setVisible(requires_password)

    def _on_enc_method_changed(self):
        use_password = self.radio_password.isChecked()
        self.password_input.setVisible(use_password)
        self.password_confirm.setVisible(use_password)
        self.pubkey_input.setVisible(not use_password)
        self.pubkey_browse_btn.setVisible(not use_password)

    def _browse_pubkey(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Выбрать публичный ключ", "", "PEM файлы (*.pem);;Все файлы (*)"
        )
        if path:
            self.pubkey_input.setText(path)

    # ── Предпросмотр ──

    def _update_preview(self):
        selected_ids = self._get_selected_entry_ids()
        if not selected_ids:
            self.preview_text.setPlainText("Не выбрано ни одной записи.")
            return

        fmt_key = self.format_combo.currentData()
        lines = [
            f"Формат: {self.FORMATS[fmt_key]['name']}",
            f"Записей к экспорту: {len(selected_ids)} из {len(self._entries)}",
            f"Шифрование: {'Пароль' if self.radio_password.isChecked() else 'Публичный ключ'}",
            f"Стойкость: {self.enc_strength.currentData()}-бит",
            f"Сжатие: {'да' if self.compress_check.isChecked() else 'нет'}",
            "",
            "Первые записи:",
        ]
        # Показываем первые 5 выбранных записей
        entry_map = {e.get("id"): e for e in self._entries}
        for eid in selected_ids[:5]:
            entry = entry_map.get(eid)
            if entry:
                lines.append(f"  • {entry.get('title', '—')} ({entry.get('category', '')})")
        if len(selected_ids) > 5:
            lines.append(f"  ... и ещё {len(selected_ids) - 5}")

        self.preview_text.setPlainText("\n".join(lines))

    # ── Валидация ──

    def _validate(self) -> bool:
        fmt_key = self.format_combo.currentData()
        info = self.FORMATS.get(fmt_key, {})

        if not self._get_selected_entry_ids():
            QMessageBox.warning(self, "Ошибка", "Выберите хотя бы одну запись для экспорта.")
            return False

        if info.get("requires_password"):
            if self.radio_password.isChecked():
                pwd = self.password_input.text()
                if not pwd:
                    QMessageBox.warning(self, "Ошибка", "Введите пароль для экспорта.")
                    self.password_input.setFocus()
                    return False
                if pwd != self.password_confirm.text():
                    QMessageBox.warning(self, "Ошибка", "Пароли не совпадают.")
                    self.password_confirm.setFocus()
                    return False
            else:
                if not self.pubkey_input.text().strip():
                    QMessageBox.warning(self, "Ошибка", "Укажите файл публичного ключа.")
                    return False

        return True

    def _do_export(self):
        if not self._validate():
            return

        save_path, _ = QFileDialog.getSaveFileName(
            self, "Сохранить файл экспорта", "",
            "CryptoSafe Export (*.cryptosafe);;JSON файлы (*.json);;CSV файлы (*.csv);;Все файлы (*)"
        )
        if not save_path:
            return

        fmt_key = self.format_combo.currentData()
        selected_ids = self._get_selected_entry_ids()

        options = {
            "encryption_strength": self.enc_strength.currentData(),
            "compression": "gzip" if self.compress_check.isChecked() else None,
        }

        password = None
        public_key = None

        if self.FORMATS[fmt_key]["requires_password"]:
            if self.radio_password.isChecked():
                password = self.password_input.text()
            else:
                try:
                    with open(self.pubkey_input.text(), "rb") as f:
                        public_key = f.read()
                except Exception as e:
                    QMessageBox.critical(self, "Ошибка", f"Не удалось прочитать ключ:\n{e}")
                    return

        try:
            self.export_btn.setEnabled(False)
            self.export_btn.setText("Экспортируется...")

            result = self.vault_exporter.export_vault(
                entry_ids=selected_ids,
                password=password,
                public_key=public_key,
                format=fmt_key,
                options=options
            )

            import json
            if fmt_key in ("csv", "lastpass_csv") and isinstance(result.get("data"), str):
                with open(save_path, "w", encoding="utf-8", newline="") as f:
                    f.write(result["data"])
            else:
                with open(save_path, "w", encoding="utf-8") as f:
                    json.dump(result, f, ensure_ascii=False, indent=2, default=str)

            QMessageBox.information(
                self, "Готово",
                f"Экспорт завершён успешно.\n"
                f"Записей: {len(selected_ids)}\n"
                f"Файл: {save_path}"
            )
            self.accept()

        except Exception as e:
            QMessageBox.critical(self, "Ошибка экспорта", str(e))
        finally:
            self.export_btn.setEnabled(True)
            self.export_btn.setText("Экспортировать")

    def get_export_options(self) -> Dict[str, Any]:
        return {
            "format": self.format_combo.currentData(),
            "entry_ids": self._get_selected_entry_ids(),
            "encryption_strength": self.enc_strength.currentData(),
            "compression": "gzip" if self.compress_check.isChecked() else None,
            "use_password": self.radio_password.isChecked(),
        }