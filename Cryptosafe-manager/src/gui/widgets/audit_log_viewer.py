import json

from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QTableWidget,
                             QTableWidgetItem, QPushButton, QLineEdit, QComboBox,
                             QLabel, QHeaderView, QMessageBox, QDateEdit,
                             QGroupBox, QSplitter, QWidget, QMenu)
from PyQt6.QtCore import Qt, QDateTime, QTimer
from PyQt6.QtGui import QColor
from src.gui.widgets.entry_details_panel import EntryDetailsPanel
from PyQt6.QtWidgets import QFileDialog, QInputDialog, QProgressDialog
from src.core.audit.log_formatters import LogFormatter
from typing import Any, Dict, List
from datetime import datetime

class AuditLogViewer(QDialog):

    def __init__(self, parent, db_connection, audit_logger=None, verifier=None):
        super().__init__(parent)
        self.db = db_connection
        self.audit_logger = audit_logger
        self.verifier = verifier
        self.current_page = 0
        self.page_size = 50
        self.total_entries = 0
        self.total_pages = 0
        self.current_filters = {}

        self.setWindowTitle("Audit Log Viewer")
        self.setGeometry(200, 200, 1400, 700)
        self.setModal(False)

        self.init_ui()
        self.load_entries()

        if self.audit_logger:
            self.audit_logger.log_event(
                event_type="AUDIT_LOGS_VIEWED",
                severity="INFO",
                source="gui.audit_viewer",
                details={'filters_applied': bool(self.current_filters)},
                user_id=None
            )

    def init_ui(self):
        main_layout = QHBoxLayout(self)

        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(0, 0, 0, 0)

        filter_group = QGroupBox("Фильтры")
        filter_layout = QVBoxLayout(filter_group)

        row1 = QHBoxLayout()
        row1.addWidget(QLabel("Тип события:"))
        self.event_type_combo = QComboBox()
        self.event_type_combo.addItem("Все")
        self.event_type_combo.addItems([
            "AUTH_LOGIN_SUCCESS", "AUTH_LOGIN_FAILURE", "AUTH_LOGOUT",
            "VAULT_ENTRY_CREATE", "VAULT_ENTRY_READ", "VAULT_ENTRY_UPDATE", "VAULT_ENTRY_DELETE",
            "CLIPBOARD_COPY", "CLIPBOARD_CLEAR",
            "SYSTEM_STARTUP", "SYSTEM_SHUTDOWN",
            "SECURITY_SUSPICIOUS_ACTIVITY", "SECURITY_TAMPER_DETECTED",
            "CONFIG_CHANGE"
        ])
        row1.addWidget(self.event_type_combo)

        row1.addWidget(QLabel("Severity:"))
        self.severity_combo = QComboBox()
        self.severity_combo.addItems(["Все", "INFO", "WARN", "ERROR", "CRITICAL"])
        row1.addWidget(self.severity_combo)

        row1.addStretch()
        filter_layout.addLayout(row1)

        row2 = QHBoxLayout()
        row2.addWidget(QLabel("Дата от:"))
        self.date_from = QDateEdit()
        self.date_from.setCalendarPopup(True)
        self.date_from.setDate(QDateTime.currentDateTime().addDays(-7).date())
        row2.addWidget(self.date_from)

        row2.addWidget(QLabel("до:"))
        self.date_to = QDateEdit()
        self.date_to.setCalendarPopup(True)
        self.date_to.setDate(QDateTime.currentDateTime().date())
        row2.addWidget(self.date_to)

        row2.addWidget(QLabel("Пользователь:"))
        self.user_filter = QLineEdit()
        self.user_filter.setPlaceholderText("username...")
        self.user_filter.setMaximumWidth(150)
        row2.addWidget(self.user_filter)

        row2.addStretch()
        filter_layout.addLayout(row2)

        row3 = QHBoxLayout()
        row3.addWidget(QLabel("Поиск:"))
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Поиск по содержимому...")
        self.search_input.textChanged.connect(self.on_search_changed)
        row3.addWidget(self.search_input)
        self.export_btn = QPushButton("Экспорт")
        self.export_btn.clicked.connect(self.export_logs)
        row3.addWidget(self.export_btn)

        self.apply_btn = QPushButton("Применить фильтры")
        self.apply_btn.clicked.connect(self.apply_filters)
        row3.addWidget(self.apply_btn)

        self.reset_btn = QPushButton("Сбросить")
        self.reset_btn.clicked.connect(self.reset_filters)
        row3.addWidget(self.reset_btn)

        filter_layout.addLayout(row3)
        left_layout.addWidget(filter_group)

        self.table = QTableWidget()
        self.table.setColumnCount(7)
        self.table.setHorizontalHeaderLabels([
            "Seq", "Время", "Тип события", "Severity",
            "Пользователь", "Источник", "Детали"
        ])
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        self.table.setSortingEnabled(True)
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.itemSelectionChanged.connect(self.on_selection_changed)
        left_layout.addWidget(self.table)

        pagination_layout = QHBoxLayout()
        self.prev_btn = QPushButton("◀ Назад")
        self.prev_btn.clicked.connect(self.prev_page)
        pagination_layout.addWidget(self.prev_btn)

        self.page_label = QLabel("Страница 0 из 0")
        pagination_layout.addWidget(self.page_label)

        self.next_btn = QPushButton("Вперед ▶")
        self.next_btn.clicked.connect(self.next_page)
        pagination_layout.addWidget(self.next_btn)

        pagination_layout.addStretch()

        self.status_label = QLabel("Всего записей: 0")
        pagination_layout.addWidget(self.status_label)

        left_layout.addLayout(pagination_layout)

        close_btn = QPushButton("Закрыть")
        close_btn.clicked.connect(self.accept)
        left_layout.addWidget(close_btn)

        self.details_panel = EntryDetailsPanel(
            parent=self,
            db_connection=self.db,
            verifier=self.verifier
        )

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.addWidget(left_widget)
        splitter.addWidget(self.details_panel)
        splitter.setSizes([900, 400])

        main_layout.addWidget(splitter)

        self.table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self.show_context_menu)

    def on_selection_changed(self):
        selected = self.table.selectedItems()
        if selected:
            row = selected[0].row()
            seq_num = self.table.item(row, 0).text()
            try:
                cursor = self.db.execute(
                    "SELECT * FROM audit_log WHERE sequence_number = ?",
                    (seq_num,)
                )
                row_data = cursor.fetchone()
                if row_data:
                    self.details_panel.load_entry(dict(row_data))
            except Exception as e:
                print(f"Error loading entry details: {e}")
        else:
            self.details_panel.clear()

    def on_search_changed(self, text: str):
        if hasattr(self, '_search_timer'):
            self._search_timer.stop()

        self._search_timer = QTimer()
        self._search_timer.setSingleShot(True)
        self._search_timer.timeout.connect(self.apply_filters)
        self._search_timer.start(500)

    def apply_filters(self):
        self.current_filters = {
            'event_type': self.event_type_combo.currentText() if self.event_type_combo.currentText() != "Все" else None,
            'severity': self.severity_combo.currentText() if self.severity_combo.currentText() != "Все" else None,
            'user_id': self.user_filter.text() if self.user_filter.text() else None,
            'date_from': self.date_from.date().toString("yyyy-MM-dd"),
            'date_to': self.date_to.date().toString("yyyy-MM-dd"),
            'search': self.search_input.text() if self.search_input.text() else None
        }
        self.current_page = 0
        self.load_entries()

    def reset_filters(self):
        self.event_type_combo.setCurrentIndex(0)
        self.severity_combo.setCurrentIndex(0)
        self.user_filter.clear()
        self.search_input.clear()
        self.date_from.setDate(QDateTime.currentDateTime().addDays(-7).date())
        self.date_to.setDate(QDateTime.currentDateTime().date())
        self.apply_filters()

    def load_entries(self):
        try:
            query, params = self._build_query()

            count_query = f"SELECT COUNT(*) FROM ({query})"
            cursor = self.db.execute(count_query, params)
            self.total_entries = cursor.fetchone()[0]
            self.total_pages = (self.total_entries + self.page_size - 1) // self.page_size

            query += " LIMIT ? OFFSET ?"
            params.extend([self.page_size, self.current_page * self.page_size])

            cursor = self.db.execute(query, params)
            rows = cursor.fetchall()

            self._display_entries(rows)
            self._update_pagination_ui()

        except Exception as e:
            QMessageBox.warning(self, "Ошибка", f"Не удалось загрузить логи: {e}")

    def _build_query(self) -> tuple:
        query = """
            SELECT 
                sequence_number, 
                timestamp, 
                event_type,
                severity,
                user_id,
                source,
                entry_data
            FROM audit_log
            WHERE 1=1
        """
        params = []

        if self.current_filters.get('event_type'):
            query += " AND event_type = ?"
            params.append(self.current_filters['event_type'])

        if self.current_filters.get('severity'):
            query += " AND severity = ?"
            params.append(self.current_filters['severity'])

        if self.current_filters.get('user_id'):
            query += " AND user_id LIKE ?"
            params.append(f"%{self.current_filters['user_id']}%")

        if self.current_filters.get('date_from'):
            query += " AND date(timestamp) >= ?"
            params.append(self.current_filters['date_from'])

        if self.current_filters.get('date_to'):
            query += " AND date(timestamp) <= ?"
            params.append(self.current_filters['date_to'])

        if self.current_filters.get('search'):
            query += " AND entry_data LIKE ?"
            params.append(f"%{self.current_filters['search']}%")

        query += " ORDER BY sequence_number DESC"

        return query, params

    def _display_entries(self, rows):
        self.table.setRowCount(len(rows))

        for row_idx, row in enumerate(rows):
            seq_num = row[0]
            timestamp = row[1]
            event_type = row[2]
            severity = row[3] or "INFO"
            user_id = row[4] or "anonymous"
            source = row[5] or "unknown"
            entry_data = row[6]

            try:
                if isinstance(entry_data, bytes):
                    entry_data = entry_data.decode('utf-8')
                details_dict = json.loads(entry_data)
                details = json.dumps(details_dict.get('details', {}), ensure_ascii=False)[:100]
            except:
                details = str(entry_data)[:100]

            self.table.setItem(row_idx, 0, QTableWidgetItem(str(seq_num)))
            self.table.setItem(row_idx, 1, QTableWidgetItem(str(timestamp)))
            self.table.setItem(row_idx, 2, QTableWidgetItem(event_type))

            severity_item = QTableWidgetItem(str(severity))
            if severity == "CRITICAL":
                severity_item.setBackground(QColor(255, 200, 200))
                severity_item.setForeground(QColor(255, 0, 0))
            elif severity == "ERROR":
                severity_item.setBackground(QColor(255, 220, 220))
                severity_item.setForeground(QColor(200, 0, 0))
            elif severity == "WARN":
                severity_item.setBackground(QColor(255, 255, 200))
            self.table.setItem(row_idx, 3, severity_item)

            self.table.setItem(row_idx, 4, QTableWidgetItem(str(user_id)))
            self.table.setItem(row_idx, 5, QTableWidgetItem(str(source)))
            self.table.setItem(row_idx, 6, QTableWidgetItem(details))

    def _update_pagination_ui(self):
        self.page_label.setText(f"Страница {self.current_page + 1} из {max(1, self.total_pages)}")
        self.prev_btn.setEnabled(self.current_page > 0)
        self.next_btn.setEnabled(self.current_page < self.total_pages - 1)
        self.status_label.setText(f"Всего записей: {self.total_entries}")

    def prev_page(self):
        if self.current_page > 0:
            self.current_page -= 1
            self.load_entries()

    def next_page(self):
        if self.current_page < self.total_pages - 1:
            self.current_page += 1
            self.load_entries()

    def show_context_menu(self, position):
        menu = QMenu(self)

        investigate_action = menu.addAction("Расследовать событие")
        investigate_action.triggered.connect(self.investigate_event)

        menu.addSeparator()

        copy_details_action = menu.addAction("Копировать детали")
        copy_details_action.triggered.connect(self.copy_event_details)

        current_row = self.table.currentRow()
        if current_row >= 0:
            event_type = self.table.item(current_row, 2).text()
            if event_type.startswith("VAULT_ENTRY_"):
                menu.addSeparator()
                vault_action = menu.addAction("Найти запись в хранилище")
                vault_action.triggered.connect(self.find_vault_entry)

        menu.exec(self.table.viewport().mapToGlobal(position))

    def investigate_event(self):
        current_row = self.table.currentRow()
        if current_row < 0:
            return

        seq_num = self.table.item(current_row, 0).text()
        cursor = self.db.execute(
            "SELECT * FROM audit_log WHERE sequence_number = ?",
            (seq_num,)
        )
        row_data = cursor.fetchone()

        if not row_data:
            return

        entry_data = row_data['entry_data']
        if isinstance(entry_data, bytes):
            entry_data = entry_data.decode('utf-8')
        data = json.loads(entry_data)

        msg = f"Детали расследования\n\n"
        msg += f"Sequence: {row_data['sequence_number']}\n"
        msg += f"Время: {row_data['timestamp']}\n"
        msg += f"Тип: {row_data['event_type']}\n"
        msg += f"Severity: {row_data['severity']}\n"
        msg += f"Пользователь: {row_data['user_id']}\n"
        msg += f"Источник: {row_data['source']}\n"
        msg += f"\nДетали:\n"
        msg += json.dumps(data.get('details', {}), indent=2, ensure_ascii=False)

        if row_data['event_type'] == 'AUTH_LOGIN_FAILURE':
            msg += f"\n\n⚠️ Это неудачная попытка входа!"
            if 'ip' in data.get('details', {}):
                msg += f"\nIP адрес: {data['details']['ip']}"

        QMessageBox.information(self, "Расследование события", msg)

    def copy_event_details(self):
        current_row = self.table.currentRow()
        if current_row < 0:
            return

        seq_num = self.table.item(current_row, 0).text()
        cursor = self.db.execute(
            "SELECT * FROM audit_log WHERE sequence_number = ?",
            (seq_num,)
        )
        row_data = cursor.fetchone()

        if not row_data:
            return

        import json
        from PyQt6.QtWidgets import QApplication

        data = {
            'sequence_number': row_data['sequence_number'],
            'timestamp': row_data['timestamp'],
            'event_type': row_data['event_type'],
            'severity': row_data['severity'],
            'user_id': row_data['user_id'],
            'source': row_data['source'],
            'entry_data': json.loads(row_data['entry_data']) if row_data['entry_data'] else {}
        }

        clipboard = QApplication.clipboard()
        clipboard.setText(json.dumps(data, indent=2, ensure_ascii=False))

        QMessageBox.information(self, "Успех", "Детали события скопированы в буфер обмена")

    def find_vault_entry(self):
        current_row = self.table.currentRow()
        if current_row < 0:
            return

        seq_num = self.table.item(current_row, 0).text()
        cursor = self.db.execute(
            "SELECT entry_data FROM audit_log WHERE sequence_number = ?",
            (seq_num,)
        )
        row_data = cursor.fetchone()

        if not row_data:
            return

        entry_data = row_data['entry_data']
        if isinstance(entry_data, bytes):
            entry_data = entry_data.decode('utf-8')
        data = json.loads(entry_data)

        entry_id = data.get('entry_id') or data.get('details', {}).get('entry_id')

        if entry_id:
            if self.parent():
                main_window = self.get_main_window()
                if main_window and hasattr(main_window, 'highlight_vault_entry'):
                    main_window.highlight_vault_entry(entry_id)
                    QMessageBox.information(self, "Найдено", f"Запись {entry_id} найдена в хранилище")
                else:
                    QMessageBox.information(self, "Информация",
                                            f"ID записи: {entry_id}\n(Функция подсветки в разработке)")
        else:
            QMessageBox.warning(self, "Ошибка", "Не удалось найти ID записи в логе")

    def get_main_window(self):
        parent = self.parent()
        while parent:
            if parent.__class__.__name__ == 'CryptoSafeApp':
                return parent
            parent = parent.parent()
        return None

    def export_logs(self):

        if not self.verify_master_password():
            QMessageBox.warning(self, "Отмена", "Экспорт отменён")
            return

        progress = QProgressDialog("Подготовка данных для экспорта...", None, 0, 0, self)
        progress.setWindowTitle("Экспорт")
        progress.setModal(True)
        progress.show()

        try:

            query, params = self._build_query()
            cursor = self.db.execute(query, params)
            rows = cursor.fetchall()
            entries = [dict(row) for row in rows]
            progress.close()

            if not entries:
                QMessageBox.warning(self, "Предупреждение", "Нет данных для экспорта")
                return

            formats = ["Signed JSON (.json)", "CSV (.csv)", "PDF (.pdf)"]
            if self._encryption_available():
                formats.append("Encrypted JSON (.enc.json)")

            format_choice, ok = QInputDialog.getItem(
                self, "Выбор формата", "Выберите формат экспорта:", formats, 0, False
            )

            if not ok:
                return

            if format_choice == "Signed JSON (.json)":
                filter_str = "JSON files (*.json)"
                default_ext = ".json"
                file_type = "json"
            elif format_choice == "CSV (.csv)":
                filter_str = "CSV files (*.csv)"
                default_ext = ".csv"
                file_type = "csv"
            elif format_choice == "Encrypted JSON (.enc.json)":
                filter_str = "Encrypted JSON files (*.enc.json)"
                default_ext = ".enc.json"
                file_type = "encrypted"
            else:
                filter_str = "PDF files (*.pdf)"
                default_ext = ".pdf"
                file_type = "pdf"

            file_path, _ = QFileDialog.getSaveFileName(
                self, "Сохранить экспорт",
                f"audit_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}{default_ext}",
                filter_str
            )

            if not file_path:
                return

            encryption_password = None
            if file_type == "encrypted":
                enc_password, ok = QInputDialog.getText(
                    self, "Шифрование экспорта",
                    "Введите пароль для шифрования экспорта (оставьте пустым для отмены):",
                    QLineEdit.EchoMode.Password
                )
                if not ok:
                    return
                if enc_password:
                    encryption_password = enc_password
                else:
                    QMessageBox.warning(self, "Отмена", "Экспорт отменён (пароль не указан)")
                    return

            formatter = LogFormatter(self.db, None)

            if self.parent() and hasattr(self.parent(), 'audit_signer'):
                formatter.signer = self.parent().audit_signer

            success = False

            if file_type == "json":
                date_range = {
                    'start_date': self.current_filters.get('date_from', ''),
                    'end_date': self.current_filters.get('date_to', '')
                }
                success = formatter.export_to_signed_json(entries, file_path, date_range)

            elif file_type == "csv":
                success = formatter.export_to_csv(entries, file_path)

            elif file_type == "encrypted":
                success = self._export_encrypted(entries, file_path, encryption_password)

            else:
                summary = self._calculate_summary(entries)
                success = formatter.export_to_pdf(entries, file_path, summary)

            if success:
                self._log_export_operation(file_type, len(entries), encryption_password is not None)

                QMessageBox.information(self, "Успех", f"Экспорт сохранён в:\n{file_path}")
            else:
                QMessageBox.critical(self, "Ошибка", "Не удалось выполнить экспорт")

        except Exception as e:
            progress.close()
            QMessageBox.critical(self, "Ошибка", f"Ошибка экспорта: {e}")

    def _calculate_summary(self, entries: List[Dict[str, Any]]) -> Dict[str, Any]:
        summary = {
            'total_entries': len(entries),
            'start_date': entries[-1].get('timestamp', '')[:10] if entries else '',
            'end_date': entries[0].get('timestamp', '')[:10] if entries else '',
            'info_count': 0,
            'warn_count': 0,
            'error_count': 0,
            'critical_count': 0
        }

        for entry in entries:
            severity = entry.get('severity', '')
            if severity == 'INFO':
                summary['info_count'] += 1
            elif severity == 'WARN':
                summary['warn_count'] += 1
            elif severity == 'ERROR':
                summary['error_count'] += 1
            elif severity == 'CRITICAL':
                summary['critical_count'] += 1

        return summary

    def verify_master_password(self) -> bool:

        password, ok = QInputDialog.getText(
            self,
            "Подтверждение пароля",
            "Для экспорта логов введите мастер-пароль:",
            QLineEdit.EchoMode.Password
        )

        if not ok or not password:
            return False

        if self.parent() and hasattr(self.parent(), 'auth'):
            key = self.parent().auth.login(password)
            if key:
                return True

        QMessageBox.critical(self, "Ошибка", "Неверный мастер-пароль")
        return False

    def _encryption_available(self) -> bool:
        try:
            from cryptography.hazmat.primitives.ciphers.aead import AESGCM
            return True
        except ImportError:
            return False
