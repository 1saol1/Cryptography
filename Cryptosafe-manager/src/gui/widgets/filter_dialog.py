from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QFormLayout,
                             QComboBox, QDateEdit, QPushButton, QLabel,
                             QGroupBox, QCheckBox, QMessageBox)
from PyQt6.QtCore import Qt, QDate


class FilterDialog(QDialog):

    def __init__(self, parent=None, entry_manager=None):
        super().__init__(parent)
        self.entry_manager = entry_manager
        self.filters = {}  

        self.setWindowTitle("Фильтры")
        self.setModal(True)
        self.setMinimumWidth(400)

        layout = QVBoxLayout(self)

        # ========== Фильтр по категории ==========
        category_group = QGroupBox("Категория")
        category_layout = QFormLayout(category_group)

        self.category_combo = QComboBox()
        self.category_combo.addItem("Все категории", "")
        self.category_combo.addItems(["Общее", "Работа", "Личное", "Почта", "Соцсети", "Банки"])
        self.category_combo.setEditable(True)
        category_layout.addRow("Категория:", self.category_combo)

        layout.addWidget(category_group)

        # ========== Фильтр по тегам ==========
        tags_group = QGroupBox("Теги")
        tags_layout = QFormLayout(tags_group)

        self.tag_input = QComboBox()
        self.tag_input.setEditable(True)
        self.tag_input.setPlaceholderText("Введите тег...")
        tags_layout.addRow("Тег:", self.tag_input)

        layout.addWidget(tags_group)

        # ========== Фильтр по дате ==========
        date_group = QGroupBox("Дата изменения")
        date_layout = QFormLayout(date_group)

        # Чекбоксы для включения фильтров
        self.enable_date_from = QCheckBox("От:")
        self.enable_date_to = QCheckBox("До:")

        self.date_from = QDateEdit()
        self.date_from.setDate(QDate.currentDate().addDays(-30))
        self.date_from.setCalendarPopup(True)

        self.date_to = QDateEdit()
        self.date_to.setDate(QDate.currentDate())
        self.date_to.setCalendarPopup(True)

        # Layout для дат
        from_layout = QHBoxLayout()
        from_layout.addWidget(self.enable_date_from)
        from_layout.addWidget(self.date_from)
        date_layout.addRow(from_layout)

        to_layout = QHBoxLayout()
        to_layout.addWidget(self.enable_date_to)
        to_layout.addWidget(self.date_to)
        date_layout.addRow(to_layout)

        layout.addWidget(date_group)

        # ========== Фильтр по надежности пароля ==========
        strength_group = QGroupBox("Надежность пароля")
        strength_layout = QFormLayout(strength_group)

        self.strength_combo = QComboBox()
        self.strength_combo.addItem("Все пароли", "")
        self.strength_combo.addItem("Только слабые (score 0-1)", "weak")
        self.strength_combo.addItem("Только средние (score 2)", "medium")
        self.strength_combo.addItem("Только надежные (score 3-4)", "strong")
        strength_layout.addRow("Надежность:", self.strength_combo)

        layout.addWidget(strength_group)

        # ========== Кнопки ==========
        buttons_layout = QHBoxLayout()
        buttons_layout.addStretch()

        apply_btn = QPushButton("Применить")
        apply_btn.clicked.connect(self.accept)
        buttons_layout.addWidget(apply_btn)

        reset_btn = QPushButton("Сбросить")
        reset_btn.clicked.connect(self.reset_filters)
        buttons_layout.addWidget(reset_btn)

        cancel_btn = QPushButton("Отмена")
        cancel_btn.clicked.connect(self.reject)
        buttons_layout.addWidget(cancel_btn)

        layout.addLayout(buttons_layout)

    def reset_filters(self):
        """Сбрасывает все фильтры"""
        self.category_combo.setCurrentIndex(0)
        self.tag_input.clear()
        self.tag_input.setEditText("")
        self.enable_date_from.setChecked(False)
        self.enable_date_to.setChecked(False)
        self.strength_combo.setCurrentIndex(0)

    def get_filters(self) -> dict:
        """Возвращает словарь с выбранными фильтрами"""
        filters = {}

        # Фильтр по категории
        category = self.category_combo.currentText()
        if category and category != "Все категории":
            filters['category'] = category

        # Фильтр по тегу
        tag = self.tag_input.currentText().strip()
        if tag:
            filters['tag'] = tag

        # Фильтр по дате
        date_filters = {}
        if self.enable_date_from.isChecked():
            date_filters['from'] = self.date_from.date().toPyDate()
        if self.enable_date_to.isChecked():
            date_filters['to'] = self.date_to.date().toPyDate()
        if date_filters:
            filters['date'] = date_filters

        # Фильтр по надежности
        strength = self.strength_combo.currentData()
        if strength:
            filters['strength'] = strength

        return filters