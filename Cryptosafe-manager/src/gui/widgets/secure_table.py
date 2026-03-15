from PyQt6.QtWidgets import QTreeWidget, QTreeWidgetItem, QHeaderView
from PyQt6.QtCore import Qt


class SecureTable(QTreeWidget):
    def __init__(self, parent=None):
        super().__init__(parent)

        self.setHeaderLabels(["Title", "Username", "URL"])
        self.header().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.setAlternatingRowColors(True)
        self.setRootIsDecorated(False)

    def add_entry(self, title, username, url):
        item = QTreeWidgetItem([title, username, url])
        self.addTopLevelItem(item)

    def get_selected_values(self):
        selected = self.selectedItems()
        if selected:
            item = selected[0]
            return {
                'title': item.text(0),
                'username': item.text(1),
                'url': item.text(2)
            }
        return None

    def delete_selected(self):
        for item in self.selectedItems():
            self.takeTopLevelItem(self.indexOfTopLevelItem(item))