from PyQt6.QtWidgets import (QTreeWidget, QTreeWidgetItem, QHeaderView,
                             QMenu, QAbstractItemView, QWidget, QHBoxLayout,
                             QPushButton, QLineEdit, QApplication)
from PyQt6.QtCore import Qt, pyqtSignal


class PasswordWidget(QWidget):

    def __init__(self, password: str, parent=None):
        super().__init__(parent)
        self.password = password
        self.is_visible = False

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)

        self.password_field = QLineEdit()
        self.password_field.setReadOnly(True)
        self.password_field.setText("••••••••")
        self.password_field.setAlignment(Qt.AlignmentFlag.AlignLeft)
        self.password_field.setStyleSheet("border: none; background: transparent;")
        layout.addWidget(self.password_field)

        # Кнопка-глаз
        self.eye_button = QPushButton()
        self.eye_button.setText("👁")
        self.eye_button.setFixedSize(24, 24)
        self.eye_button.setFlat(True)
        self.eye_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.eye_button.clicked.connect(self.toggle_password)
        layout.addWidget(self.eye_button)

        layout.addStretch()

    def toggle_password(self):
        if self.is_visible:
            self.password_field.setText("••••••••")
            self.eye_button.setText("👁")
            self.is_visible = False
        else:
            self.password_field.setText(self.password)
            self.eye_button.setText("🗨")
            self.is_visible = True

    def get_password(self) -> str:
        return self.password


class SecureTable(QTreeWidget):
    item_selected = pyqtSignal(dict)
    item_double_clicked = pyqtSignal(dict)
    toggle_password_visibility = pyqtSignal(bool)

    def __init__(self, parent=None):
        super().__init__(parent)

        self.setHeaderLabels(["Название", "Имя пользователя", "Пароль", "URL/Домен", "Изменено"])

        self.header().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.header().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.header().setSectionResizeMode(2, QHeaderView.ResizeMode.Fixed)
        self.header().resizeSection(2, 120)
        self.header().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        self.header().setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)

        self.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.header().setSectionsMovable(True)

        self.setAlternatingRowColors(True)
        self.setRootIsDecorated(False)
        self.setSortingEnabled(True)

        self.itemSelectionChanged.connect(self._on_selection_changed)
        self.itemDoubleClicked.connect(self._on_double_click)

        self._item_ids = {}
        self._password_widgets = {}
        self._show_all_passwords = False

    def set_show_all_passwords(self, show: bool):

        self._show_all_passwords = show
        for widget in self._password_widgets.values():
            if show:
                widget.password_field.setText(widget.password)
                widget.eye_button.setText("🗨")
                widget.is_visible = True
            else:
                widget.password_field.setText("••••••••")
                widget.eye_button.setText("👁")
                widget.is_visible = False
        self.toggle_password_visibility.emit(show)

    def _extract_domain(self, url: str) -> str:
        if not url:
            return ""
        url = url.replace("https://", "").replace("http://", "")
        url = url.replace("www.", "")
        domain = url.split("/")[0]
        return domain

    def add_entry(self, entry_id: str, title: str, username: str,
                  password: str, url: str, updated_at: str = ""):

        if len(username) > 4:
            masked_username = username[:4] + "••••"
        else:
            masked_username = username + "••••"

        domain = self._extract_domain(url)

        item = QTreeWidgetItem([title, masked_username, "", domain, updated_at])

        self._item_ids[item] = entry_id

        password_widget = PasswordWidget(password)
        self._password_widgets[item] = password_widget

        self.setItemWidget(item, 2, password_widget)

        self.addTopLevelItem(item)

    def update_entry(self, entry_id: str, title: str, username: str,
                     password: str, url: str, updated_at: str = ""):
        for item, eid in self._item_ids.items():
            if eid == entry_id:
                if len(username) > 4:
                    masked_username = username[:4] + "••••"
                else:
                    masked_username = username + "••••"

                domain = self._extract_domain(url)

                item.setText(0, title)
                item.setText(1, masked_username)
                item.setText(3, domain)
                item.setText(4, updated_at)

                widget = self._password_widgets.get(item)
                if widget:
                    widget.password = password
                    if self._show_all_passwords:
                        widget.password_field.setText(password)
                        widget.eye_button.setText("‍🗨")
                        widget.is_visible = True
                    else:
                        widget.password_field.setText("••••••••")
                        widget.eye_button.setText("👁")
                        widget.is_visible = False
                break

    def remove_entry(self, entry_id: str):
        for item, eid in list(self._item_ids.items()):
            if eid == entry_id:
                del self._item_ids[item]
                if item in self._password_widgets:
                    del self._password_widgets[item]
                self.takeTopLevelItem(self.indexOfTopLevelItem(item))
                break

    def get_selected_entries(self) -> list:
        selected_items = self.selectedItems()
        return [self._item_ids[item] for item in selected_items if item in self._item_ids]

    def get_entry_password(self, entry_id: str) -> str:
        for item, eid in self._item_ids.items():
            if eid == entry_id:
                widget = self._password_widgets.get(item)
                if widget:
                    return widget.get_password()
        return ""

    def clear_all(self):
        self._item_ids.clear()
        self._password_widgets.clear()
        self.clear()

    def _on_selection_changed(self):
        selected = self.selectedItems()
        if selected:
            entry_id = self._item_ids.get(selected[0])
            if entry_id:
                self.item_selected.emit({'id': entry_id})

    def _on_double_click(self, item, column):
        entry_id = self._item_ids.get(item)
        if entry_id:
            self.item_double_clicked.emit({'id': entry_id})

    def contextMenuEvent(self, event):
        menu = QMenu(self)

        copy_title = menu.addAction("Копировать название")
        copy_username = menu.addAction("Копировать логин")
        copy_password = menu.addAction("Копировать пароль")
        copy_url = menu.addAction("Копировать URL")
        menu.addSeparator()
        edit_action = menu.addAction("Редактировать")
        delete_action = menu.addAction("Удалить")

        action = menu.exec(event.globalPos())

        selected = self.selectedItems()
        if not selected:
            return

        item = selected[0]
        entry_id = self._item_ids.get(item)

        if action == copy_title:
            QApplication.clipboard().setText(item.text(0))
        elif action == copy_username:
            QApplication.clipboard().setText(item.text(1))
        elif action == copy_password:
            widget = self._password_widgets.get(item)
            if widget:
                QApplication.clipboard().setText(widget.get_password())
        elif action == copy_url:
            QApplication.clipboard().setText(item.text(3))
        elif action == edit_action:
            self.item_double_clicked.emit({'id': entry_id})
        elif action == delete_action:
            if self.parent():
                self.parent().delete_selected()