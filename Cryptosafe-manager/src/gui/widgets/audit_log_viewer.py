import json

from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QTableWidget,
                             QTableWidgetItem, QPushButton, QLineEdit, QComboBox,
                             QLabel, QHeaderView, QMessageBox, QDateEdit,
                             QGroupBox)
from PyQt6.QtCore import Qt, QDateTime, QTimer
from PyQt6.QtGui import QColor


class AuditLogViewer(QDialog):

    def __init__(self, parent, db_connection, audit_logger=None):
        super().__init__(parent)
        self.db = db_connection
        self.audit_logger = audit_logger
        self.current_page = 0
        self.page_size = 50
        self.total_entries = 0
        self.total_pages = 0
        self.current_filters = {}

        self.setWindowTitle("Audit Log Viewer")
        self.setGeometry(200, 200, 1200, 700)
        self.setModal(False)

        self.init_ui()
        self.load_entries()

        if self.audit_logger:
            self.audit_logger.log_event(
                event_type="AUDIT_LOGS_VIEWED",
                severity="INFO",
                source="gui.audit_viewer",
                details={},
                user_id=None
            )

    def init_ui(self):
        layout = QVBoxLayout(self)

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

        self.apply_btn = QPushButton("Применить фильтры")
        self.apply_btn.clicked.connect(self.apply_filters)
        row3.addWidget(self.apply_btn)

        self.reset_btn = QPushButton("Сбросить")
        self.reset_btn.clicked.connect(self.reset_filters)
        row3.addWidget(self.reset_btn)

        filter_layout.addLayout(row3)
        layout.addWidget(filter_group)

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
        layout.addWidget(self.table)

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

        layout.addLayout(pagination_layout)

        close_btn = QPushButton("Закрыть")
        close_btn.clicked.connect(self.accept)
        layout.addWidget(close_btn)

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
                json_extract(entry_data, '$.severity') as severity,
                json_extract(entry_data, '$.user_id') as user_id,
                json_extract(entry_data, '$.source') as source,
                entry_data
            FROM audit_log
            WHERE 1=1
        """
        params = []

        if self.current_filters.get('event_type'):
            query += " AND event_type = ?"
            params.append(self.current_filters['event_type'])

        if self.current_filters.get('severity'):
            query += " AND json_extract(entry_data, '$.severity') = ?"
            params.append(self.current_filters['severity'])

        if self.current_filters.get('user_id'):
            query += " AND json_extract(entry_data, '$.user_id') LIKE ?"
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