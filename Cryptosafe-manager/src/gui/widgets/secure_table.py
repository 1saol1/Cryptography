from PyQt6.QtWidgets import (
    QTreeWidget, QTreeWidgetItem, QHeaderView,
    QAbstractItemView, QApplication, QMenu
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QColor, QBrush


class SecureTable(QTreeWidget):
    item_selected = pyqtSignal(dict)
    item_double_clicked = pyqtSignal(dict)
    item_delete_requested = pyqtSignal(dict)
    toggle_password_visibility = pyqtSignal(bool)

    ICON_VISIBLE = "👁 "
    ICON_HIDDEN = "🔒 "
    ICON_WIDTH_PX = 32

    def __init__(self, parent=None):
        super().__init__(parent)

        self.setHeaderLabels(["Название", "Имя пользователя", "Пароль", "URL/Домен", "Изменено"])

        self.header().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.header().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.header().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.header().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        self.header().setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)

        self.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.header().setSectionsMovable(True)

        self.setAlternatingRowColors(True)
        self.setRootIsDecorated(False)
        self.setSortingEnabled(True)

        self.itemSelectionChanged.connect(self._on_selection_changed)
        self.itemDoubleClicked.connect(self._on_double_click)

        self._items = []
        self._item_ids = []
        self._passwords = []
        self._password_visible = {}
        self._show_all_passwords = False

        self._search_text = ""

    def _get_password_display(self, password: str, visible: bool) -> str:
        if visible:
            return self.ICON_VISIBLE + password
        return self.ICON_HIDDEN + "••••••••"

    def set_show_all_passwords(self, show: bool):
        self._show_all_passwords = show

        for entry_id in self._item_ids:
            self._password_visible[entry_id] = show

        for i, item in enumerate(self._items):
            item.setText(2, self._get_password_display(self._passwords[i], show))

        self.toggle_password_visibility.emit(show)

    def set_search_highlight(self, search_text: str):
        self._search_text = search_text.lower() if search_text else ""

        for i, item in enumerate(self._items):
            title = item.text(0)
            username = item.text(1)
            url = item.text(3)

            if self._search_text and (
                    self._search_text in title.lower() or
                    self._search_text in username.lower() or
                    self._search_text in url.lower()
            ):
                brush = QBrush(QColor(255, 255, 200))
                item.setBackground(0, brush)
                item.setBackground(1, brush)
                item.setBackground(3, brush)
            else:
                item.setBackground(0, QBrush())
                item.setBackground(1, QBrush())
                item.setBackground(3, QBrush())

    def add_entry(self, entry_id: str, title: str, username: str,
                  password: str, url: str, updated_at: str = ""):
        if len(username) > 4:
            masked_username = username[:4] + "••••"
        else:
            masked_username = username + "••••"

        domain = self._extract_domain(url)

        visible = self._show_all_passwords
        self._password_visible[entry_id] = visible
        display_pwd = self._get_password_display(password, visible)

        item = QTreeWidgetItem([title, masked_username, display_pwd, domain, updated_at])

        self._items.append(item)
        self._item_ids.append(entry_id)
        self._passwords.append(password)

        self.addTopLevelItem(item)

        if self._search_text:
            self.set_search_highlight(self._search_text)

    def update_entry(self, entry_id: str, title: str, username: str,
                     password: str, url: str, updated_at: str = ""):
        for i, eid in enumerate(self._item_ids):
            if eid == entry_id:
                item = self._items[i]

                if len(username) > 4:
                    masked_username = username[:4] + "••••"
                else:
                    masked_username = username + "••••"

                domain = self._extract_domain(url)

                self._passwords[i] = password
                visible = self._password_visible.get(entry_id, False)
                display_pwd = self._get_password_display(password, visible)

                item.setText(0, title)
                item.setText(1, masked_username)
                item.setText(2, display_pwd)
                item.setText(3, domain)
                item.setText(4, updated_at)
                break

        if self._search_text:
            self.set_search_highlight(self._search_text)

    def remove_entry(self, entry_id: str):
        for i in range(len(self._item_ids) - 1, -1, -1):
            if self._item_ids[i] == entry_id:
                item = self._items[i]
                self.takeTopLevelItem(self.indexOfTopLevelItem(item))

                del self._items[i]
                del self._item_ids[i]
                del self._passwords[i]
                self._password_visible.pop(entry_id, None)
                return

        print(f"Warning: Entry {entry_id} not found for removal")

    def remove_entries(self, entry_ids: list[str]):
        if not entry_ids:
            return

        indices = []
        for eid in entry_ids:
            for i, existing_id in enumerate(self._item_ids):
                if existing_id == eid:
                    indices.append(i)
                    break

        indices.sort(reverse=True)

        for idx in indices:
            item = self._items[idx]
            self.takeTopLevelItem(self.indexOfTopLevelItem(item))

            eid = self._item_ids[idx]
            del self._items[idx]
            del self._item_ids[idx]
            del self._passwords[idx]
            self._password_visible.pop(eid, None)

    def get_selected_entries(self) -> list:
        selected_items = self.selectedItems()
        result = []
        for sel in selected_items:
            for i, item in enumerate(self._items):
                if item is sel:
                    result.append(self._item_ids[i])
                    break
        return result

    def get_entry_password(self, entry_id: str) -> str:
        for i, eid in enumerate(self._item_ids):
            if eid == entry_id:
                return self._passwords[i]
        return ""

    def clear_all(self):
        self._items.clear()
        self._item_ids.clear()
        self._passwords.clear()
        self._password_visible.clear()
        self.clear()
        self._search_text = ""

    def _on_selection_changed(self):
        selected = self.selectedItems()
        if selected:
            for i, item in enumerate(self._items):
                if item is selected[0]:
                    self.item_selected.emit({'id': self._item_ids[i]})
                    break

    def _on_double_click(self, item, column):
        for i, it in enumerate(self._items):
            if it is item:
                self.item_double_clicked.emit({'id': self._item_ids[i]})
                break

    def _extract_domain(self, url: str) -> str:
        if not url:
            return ""
        url = url.replace("https://", "").replace("http://", "")
        url = url.replace("www.", "")
        domain = url.split("/")[0]
        return domain

    def mousePressEvent(self, event):
        if event.button() != Qt.MouseButton.LeftButton:
            return super().mousePressEvent(event)

        pos = event.pos()
        item = self.itemAt(pos)
        if not item:
            return super().mousePressEvent(event)

        column = self.columnAt(pos.x())
        if column != 2:
            return super().mousePressEvent(event)

        header = self.header()
        section_left = header.sectionViewportPosition(column)

        rel_x = pos.x() - section_left

        if 0 <= rel_x <= 40:
            idx = self._items.index(item)
            entry_id = self._item_ids[idx]

            was_visible = self._password_visible.get(entry_id, False)
            now_visible = not was_visible

            if self._show_all_passwords:
                self._show_all_passwords = False
                self.toggle_password_visibility.emit(False)

            self._password_visible[entry_id] = now_visible
            display = self._get_password_display(self._passwords[idx], now_visible)
            item.setText(2, display)

            event.accept()
            return

        return super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        pos = event.pos()
        item = self.itemAt(pos)
        if item:
            col = self.columnAt(pos.x())
            if col == 2:
                rect = self.visualItemRect(item)
                rel_x = pos.x() - rect.x()
                if rel_x <= self.ICON_WIDTH_PX:
                    QApplication.setOverrideCursor(Qt.CursorShape.PointingHandCursor)
                    return
        QApplication.restoreOverrideCursor()
        super().mouseMoveEvent(event)

    def leaveEvent(self, event):
        QApplication.restoreOverrideCursor()
        super().leaveEvent(event)

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

        idx = -1
        for i, it in enumerate(self._items):
            if it is item:
                idx = i
                break

        if idx == -1:
            return

        entry_id = self._item_ids[idx]

        if action == copy_title:
            if hasattr(self.parent(), 'copy_to_clipboard'):
                self.parent().copy_to_clipboard(item.text(0), data_type="title", entry_id=entry_id)
        elif action == copy_username:
            if hasattr(self.parent(), 'copy_to_clipboard'):
                full_username = self.parent().entry_manager.get_entry(entry_id).get('username', '')
                self.parent().copy_to_clipboard(full_username, data_type="username", entry_id=entry_id)
        elif action == copy_password:
            password = self._passwords[idx]
            if hasattr(self.parent(), 'copy_to_clipboard'):
                self.parent().copy_to_clipboard(password, data_type="password", entry_id=entry_id)
        elif action == copy_url:
            if hasattr(self.parent(), 'copy_to_clipboard'):
                full_url = self.parent().entry_manager.get_entry(entry_id).get('url', '')
                self.parent().copy_to_clipboard(full_url, data_type="url", entry_id=entry_id)
        elif action == edit_action:
            self.item_double_clicked.emit({'id': entry_id})
        elif action == delete_action:
            self.item_delete_requested.emit({'id': entry_id})