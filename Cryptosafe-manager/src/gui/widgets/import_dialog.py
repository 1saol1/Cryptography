from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout,
    QLabel, QPushButton, QLineEdit, QGroupBox,
    QRadioButton, QButtonGroup, QTextEdit, QTableWidget,
    QTableWidgetItem, QMessageBox, QFileDialog,
    QComboBox, QProgressBar, QWidget, QSplitter
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont, QColor
from typing import Optional, Dict, Any, List


# UI-2: Диалог импорта записей
class ImportDialog(QDialog):
    """
    UI-2: Диалог импорта записей в хранилище.
    Включает:
    - Автоопределение формата
    - Настройки разрешения конфликтов
    - Предпросмотр записей
    - Сводка изменений
    """

    CONFLICT_MODES = {
        "merge": "Объединить (добавить новые, обновить существующие)",
        "replace": "Заменить (очистить хранилище и импортировать)",
        "dry_run": "Предпросмотр (без сохранения)",
    }

    FORMAT_LABELS = {
        "encrypted_json": "Зашифрованный JSON (CryptoSafe)",
        "csv": "CSV",
        "bitwarden_json": "Bitwarden JSON",
        "lastpass_csv": "LastPass CSV",
        "unknown": "Неизвестный",
    }

    def __init__(self, parent, entry_manager, vault_importer):
        super().__init__(parent)
        self.entry_manager = entry_manager
        self.vault_importer = vault_importer
        self._detected_format: Optional[str] = None
        self._preview_entries: List[Dict[str, Any]] = []
        self._import_summary: Optional[Dict[str, Any]] = None

        self.setWindowTitle("Импорт записей")
        self.setModal(True)
        self.setMinimumSize(680, 520)

        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(10)

        title = QLabel("Импорт записей")
        title.setFont(QFont("", 13, QFont.Weight.Bold))
        layout.addWidget(title)

        # ── Выбор файла ──
        file_group = QGroupBox("Файл импорта")
        file_layout = QHBoxLayout(file_group)

        self.file_input = QLineEdit()
        self.file_input.setPlaceholderText("Выберите файл для импорта...")
        self.file_input.setReadOnly(True)
        file_layout.addWidget(self.file_input)

        browse_btn = QPushButton("Обзор...")
        browse_btn.clicked.connect(self._browse_file)
        file_layout.addWidget(browse_btn)

        layout.addWidget(file_group)

        # ── UI-2: Автоопределение формата ──
        detect_group = QGroupBox("Формат")
        detect_layout = QFormLayout(detect_group)

        self.detected_format_label = QLabel("—")
        self.detected_format_label.setStyleSheet("font-weight: bold;")
        detect_layout.addRow("Определён автоматически:", self.detected_format_label)

        # Пароль для зашифрованных форматов
        self.password_label = QLabel("Пароль:")
        self.password_input = QLineEdit()
        self.password_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.password_input.setPlaceholderText("Для зашифрованных файлов")
        self.password_input.setVisible(False)
        self.password_label.setVisible(False)
        detect_layout.addRow(self.password_label, self.password_input)

        layout.addWidget(detect_group)

        # ── UI-2: Разрешение конфликтов ──
        conflict_group = QGroupBox("Разрешение конфликтов")
        conflict_layout = QVBoxLayout(conflict_group)

        self.conflict_btn_group = QButtonGroup(self)
        for key, label in self.CONFLICT_MODES.items():
            rb = QRadioButton(label)
            rb.setProperty("mode_key", key)
            if key == "merge":
                rb.setChecked(True)
            self.conflict_btn_group.addButton(rb)
            conflict_layout.addWidget(rb)

        layout.addWidget(conflict_group)

        # ── Кнопка загрузки предпросмотра ──
        load_btn = QPushButton("Загрузить и проверить файл")
        load_btn.clicked.connect(self._load_preview)
        layout.addWidget(load_btn)

        # ── UI-2: Предпросмотр записей ──
        preview_group = QGroupBox("Предпросмотр записей для импорта")
        preview_layout = QVBoxLayout(preview_group)

        self.preview_table = QTableWidget(0, 4)
        self.preview_table.setHorizontalHeaderLabels(["Название", "Логин", "URL", "Статус"])
        self.preview_table.horizontalHeader().setStretchLastSection(True)
        self.preview_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.preview_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.preview_table.setMaximumHeight(180)
        preview_layout.addWidget(self.preview_table)

        layout.addWidget(preview_group)

        # ── UI-2: Сводка изменений ──
        summary_group = QGroupBox("Сводка изменений")
        summary_layout = QVBoxLayout(summary_group)

        self.summary_text = QTextEdit()
        self.summary_text.setReadOnly(True)
        self.summary_text.setMaximumHeight(90)
        self.summary_text.setPlaceholderText("Загрузите файл для отображения сводки...")
        summary_layout.addWidget(self.summary_text)

        layout.addWidget(summary_group)

        # ── Кнопки ──
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        self.import_btn = QPushButton("Импортировать")
        self.import_btn.setDefault(True)
        self.import_btn.setEnabled(False)
        self.import_btn.clicked.connect(self._do_import)
        btn_layout.addWidget(self.import_btn)

        cancel_btn = QPushButton("Отмена")
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(cancel_btn)

        layout.addLayout(btn_layout)

    # ── Обзор файла ──

    def _browse_file(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Выбрать файл импорта", "",
            "Все поддерживаемые (*.cryptosafe *.json *.csv);;"
            "CryptoSafe (*.cryptosafe);;JSON (*.json);;CSV (*.csv);;Все файлы (*)"
        )
        if path:
            self.file_input.setText(path)
            self._auto_detect_format(path)

    def _auto_detect_format(self, path: str):
        """UI-2: Автоматическое определение формата по расширению и содержимому."""
        fmt = "unknown"
        try:
            if path.endswith(".cryptosafe"):
                fmt = "encrypted_json"
            elif path.endswith(".csv"):
                with open(path, "r", encoding="utf-8", errors="ignore") as f:
                    header = f.readline().lower()
                fmt = "lastpass_csv" if "grouping" in header else "csv"
            elif path.endswith(".json"):
                import json
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                if data.get("encrypted") or data.get("encryption"):
                    fmt = "encrypted_json"
                elif "items" in data or "folders" in data:
                    fmt = "bitwarden_json"
                else:
                    fmt = "encrypted_json"
        except Exception:
            pass

        self._detected_format = fmt
        label = self.FORMAT_LABELS.get(fmt, fmt)
        self.detected_format_label.setText(label)

        needs_password = fmt in ("encrypted_json",)
        self.password_input.setVisible(needs_password)
        self.password_label.setVisible(needs_password)

    # ── Загрузка предпросмотра ──

    def _load_preview(self):
        path = self.file_input.text().strip()
        if not path:
            QMessageBox.warning(self, "Ошибка", "Выберите файл для импорта.")
            return

        conflict_mode = self._get_conflict_mode()
        password = self.password_input.text() if self.password_input.isVisible() else None

        try:
            result = self.vault_importer.preview_import(
                file_path=path,
                format=self._detected_format,
                password=password,
                mode=conflict_mode
            )
            self._preview_entries = result.get("entries", [])
            self._import_summary = result.get("summary", {})
            self._populate_preview_table()
            self._update_summary()
            self.import_btn.setEnabled(conflict_mode != "dry_run")

        except Exception as e:
            QMessageBox.critical(self, "Ошибка загрузки", str(e))

    def _populate_preview_table(self):
        self.preview_table.setRowCount(0)
        for entry in self._preview_entries[:100]:  # Максимум 100 строк
            row = self.preview_table.rowCount()
            self.preview_table.insertRow(row)

            status = entry.get("import_status", "new")
            status_labels = {
                "new": "Новая",
                "duplicate": "Дубликат",
                "update": "Обновление",
                "conflict": "Конфликт",
            }

            items = [
                QTableWidgetItem(entry.get("title", "—")),
                QTableWidgetItem(entry.get("username", "")),
                QTableWidgetItem(entry.get("url", "")),
                QTableWidgetItem(status_labels.get(status, status)),
            ]

            # Цветовая маркировка статуса
            color_map = {
                "new": QColor("#e8f5e9"),
                "duplicate": QColor("#fff3e0"),
                "conflict": QColor("#ffebee"),
                "update": QColor("#e3f2fd"),
            }
            bg = color_map.get(status, QColor("white"))
            for item in items:
                item.setBackground(bg)
            for col, item in enumerate(items):
                self.preview_table.setItem(row, col, item)

    def _update_summary(self):
        """UI-2: Отображение сводки изменений."""
        if not self._import_summary:
            return
        s = self._import_summary
        lines = [
            f"Всего записей в файле: {s.get('total', 0)}",
            f"  ✅ Новых: {s.get('new', 0)}",
            f"  🔄 Обновлений: {s.get('updates', 0)}",
            f"  ⚠️  Дубликатов: {s.get('duplicates', 0)}",
            f"  ❌ Конфликтов: {s.get('conflicts', 0)}",
        ]
        if s.get("errors"):
            lines.append(f"  🛑 Ошибок валидации: {s.get('errors', 0)}")
        self.summary_text.setPlainText("\n".join(lines))

    # ── Утилиты ──

    def _get_conflict_mode(self) -> str:
        for btn in self.conflict_btn_group.buttons():
            if btn.isChecked():
                return btn.property("mode_key")
        return "merge"

    # ── Импорт ──

    def _do_import(self):
        path = self.file_input.text().strip()
        if not path:
            QMessageBox.warning(self, "Ошибка", "Выберите файл для импорта.")
            return

        mode = self._get_conflict_mode()
        if mode == "replace":
            reply = QMessageBox.warning(
                self, "Подтверждение",
                "Режим «Заменить» удалит все существующие записи!\n\nПродолжить?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            if reply != QMessageBox.StandardButton.Yes:
                return

        password = self.password_input.text() if self.password_input.isVisible() else None

        try:
            self.import_btn.setEnabled(False)
            self.import_btn.setText("Импортируется...")

            result = self.vault_importer.import_vault(
                file_path=path,
                format=self._detected_format,
                password=password,
                mode=mode
            )

            imported = result.get("imported_count", 0)
            QMessageBox.information(
                self, "Импорт завершён",
                f"Импорт выполнен успешно.\n"
                f"Добавлено/обновлено записей: {imported}"
            )
            self.accept()

        except Exception as e:
            QMessageBox.critical(self, "Ошибка импорта", str(e))
        finally:
            self.import_btn.setEnabled(True)
            self.import_btn.setText("Импортировать")