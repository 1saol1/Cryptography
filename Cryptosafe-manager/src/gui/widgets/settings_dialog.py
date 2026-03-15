from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QTabWidget,
                             QWidget, QLabel, QSpinBox, QPushButton,
                             QRadioButton, QButtonGroup, QComboBox, QFrame)
from PyQt6.QtCore import Qt


class SettingsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Настройки CryptoSafe Manager")
        self.setGeometry(100, 100, 620, 520)
        self.setModal(True)

        main_layout = QVBoxLayout(self)

        tabs = QTabWidget()

        tabs.addTab(self.create_security_tab(), "Безопасность")
        tabs.addTab(self.create_appearance_tab(), "Внешний вид")
        tabs.addTab(self.create_advanced_tab(), "Дополнительно")

        main_layout.addWidget(tabs)

        button_layout = QHBoxLayout()
        button_layout.addStretch()

        cancel_btn = QPushButton("Отмена")
        cancel_btn.clicked.connect(self.reject)
        save_btn = QPushButton("Сохранить")
        save_btn.clicked.connect(self.on_save)

        button_layout.addWidget(cancel_btn)
        button_layout.addWidget(save_btn)

        main_layout.addLayout(button_layout)

    def create_security_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)

        clip_layout = QHBoxLayout()
        clip_layout.addWidget(QLabel("Очистка буфера обмена через (секунды):"))
        self.clip_timeout = QSpinBox()
        self.clip_timeout.setRange(10, 600)
        self.clip_timeout.setSingleStep(10)
        self.clip_timeout.setValue(90)
        clip_layout.addWidget(self.clip_timeout)
        clip_layout.addStretch()
        layout.addLayout(clip_layout)

        auto_layout = QHBoxLayout()
        auto_layout.addWidget(QLabel("Автоматическая блокировка после (минут):"))
        self.autolock = QSpinBox()
        self.autolock.setRange(1, 120)
        self.autolock.setSingleStep(5)
        self.autolock.setValue(10)
        auto_layout.addWidget(self.autolock)
        auto_layout.addStretch()
        layout.addLayout(auto_layout)

        layout.addWidget(QLabel("(Значения будут сохраняться в следующих спринтах)"))
        layout.addStretch()

        return tab

    def create_appearance_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)

        layout.addWidget(QLabel("Тема оформления:"))

        self.theme_group = QButtonGroup()

        theme_system = QRadioButton("Системная")
        theme_system.setChecked(True)
        theme_light = QRadioButton("Светлая")
        theme_dark = QRadioButton("Тёмная")

        self.theme_group.addButton(theme_system)
        self.theme_group.addButton(theme_light)
        self.theme_group.addButton(theme_dark)

        layout.addWidget(theme_system)
        layout.addWidget(theme_light)
        layout.addWidget(theme_dark)

        layout.addSpacing(20)
        layout.addWidget(QLabel("Язык интерфейса:"))

        self.lang = QComboBox()
        self.lang.addItems(["Русский", "English"])
        layout.addWidget(self.lang)

        layout.addSpacing(20)
        layout.addWidget(QLabel("(Применение темы и языка — в следующих спринтах)"))
        layout.addStretch()

        return tab

    def create_advanced_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)

        backup_btn = QPushButton("Создать резервную копию хранилища…")
        backup_btn.setEnabled(False)
        layout.addWidget(backup_btn)

        restore_btn = QPushButton("Восстановить из резервной копии…")
        restore_btn.setEnabled(False)
        layout.addWidget(restore_btn)

        export_btn = QPushButton("Экспортировать записи…")
        export_btn.setEnabled(False)
        layout.addWidget(export_btn)

        import_btn = QPushButton("Импортировать записи…")
        import_btn.setEnabled(False)
        layout.addWidget(import_btn)

        layout.addSpacing(20)

        label = QLabel("Функции резервного копирования и импорта/экспорта\n"
                       "будут реализованы в спринтах 6–8")
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(label)

        layout.addStretch()

        return tab

    def on_save(self):
        from PyQt6.QtWidgets import QMessageBox
        QMessageBox.information(self, "Настройки",
                                "Настройки сохранены (заглушка).\n"
                                "Значения вступят в силу после реализации в следующих спринтах.")
        self.accept()