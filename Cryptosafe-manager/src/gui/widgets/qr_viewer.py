from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QGroupBox, QTextEdit, QMessageBox,
    QSizePolicy
)
from PyQt6.QtCore import Qt, QTimer, QByteArray
from PyQt6.QtGui import QFont, QPixmap, QPainter
from typing import Optional, List, Dict, Any


# UI-4: Просмотрщик QR кодов
class QRViewerDialog(QDialog):
    """
    UI-4: Диалог для отображения QR кода.
    Включает:
    - Большое чёткое отображение QR кода
    - Информацию о полезной нагрузке
    - Кнопки копирования и сохранения
    - Авто-обновление для временных кодов
    """

    def __init__(self, parent,
                 qr_codes: List[str],
                 payload_info: Optional[Dict] = None,
                 validity_seconds: Optional[int] = None,
                 title: str = "QR-код"):
        super().__init__(parent)
        self.qr_codes = qr_codes
        self.payload_info = payload_info or {}
        self.validity_seconds = validity_seconds
        self._current_chunk = 0
        self._refresh_callback = None
        self._timer: Optional[QTimer] = None
        self._remaining_seconds = validity_seconds or 0

        self.setWindowTitle(title)
        self.setModal(True)
        self.setMinimumSize(480, 560)

        self._setup_ui()

        if validity_seconds:
            self._start_validity_timer()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(8)

        title_label = QLabel(self.windowTitle())
        title_label.setFont(QFont("", 13, QFont.Weight.Bold))
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title_label)

        # UI-4: Большое чёткое отображение QR кода
        qr_group = QGroupBox()
        qr_layout = QVBoxLayout(qr_group)

        # Навигация по чанкам
        if len(self.qr_codes) > 1:
            nav_layout = QHBoxLayout()
            self.prev_btn = QPushButton("◀")
            self.prev_btn.setFixedWidth(40)
            self.prev_btn.clicked.connect(self._prev_chunk)
            self.chunk_label = QLabel()
            self.chunk_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.next_btn = QPushButton("▶")
            self.next_btn.setFixedWidth(40)
            self.next_btn.clicked.connect(self._next_chunk)
            nav_layout.addWidget(self.prev_btn)
            nav_layout.addWidget(self.chunk_label)
            nav_layout.addWidget(self.next_btn)
            qr_layout.addLayout(nav_layout)

        # QLabel для рендеринга QR как растрового изображения
        self.qr_label = QLabel()
        self.qr_label.setFixedSize(320, 320)
        self.qr_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.qr_label.setStyleSheet("background: white; border: 1px solid #ccc;")
        qr_layout.addWidget(self.qr_label, alignment=Qt.AlignmentFlag.AlignCenter)

        layout.addWidget(qr_group)

        # UI-4: Таймер срока действия
        if self.validity_seconds:
            self.timer_label = QLabel()
            self.timer_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.timer_label.setStyleSheet("font-size: 12px; color: #e65100;")
            layout.addWidget(self.timer_label)

        # UI-4: Информация о payload
        info_group = QGroupBox("Информация о коде")
        info_layout = QVBoxLayout(info_group)
        self.info_text = QTextEdit()
        self.info_text.setReadOnly(True)
        self.info_text.setMaximumHeight(100)
        self.info_text.setFont(QFont("Courier", 9))
        info_layout.addWidget(self.info_text)
        layout.addWidget(info_group)

        # UI-4: Кнопки
        btn_layout = QHBoxLayout()
        copy_svg_btn = QPushButton("📋 Копировать SVG")
        copy_svg_btn.clicked.connect(self._copy_svg)
        btn_layout.addWidget(copy_svg_btn)
        save_btn = QPushButton("💾 Сохранить PNG")
        save_btn.clicked.connect(self._save_png)
        btn_layout.addWidget(save_btn)
        close_btn = QPushButton("Закрыть")
        close_btn.clicked.connect(self.accept)
        btn_layout.addWidget(close_btn)
        layout.addLayout(btn_layout)

        self._render_current_qr()
        self._update_payload_info()

    # ── Рендеринг ──

    def _render_current_qr(self):
        if not self.qr_codes:
            return
        qr_data = self.qr_codes[self._current_chunk]
        try:
            if qr_data.startswith("data:image/png;base64,"):
                # PNG base64 — декодируем и загружаем в QPixmap
                import base64
                png_bytes = base64.b64decode(qr_data.split(",", 1)[1])
                pixmap = QPixmap()
                pixmap.loadFromData(png_bytes)
                pixmap = pixmap.scaled(
                    320, 320,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.FastTransformation
                )
            else:
                # SVG fallback через QSvgRenderer
                from PyQt6.QtSvg import QSvgRenderer
                renderer = QSvgRenderer(QByteArray(qr_data.encode("utf-8")))
                pixmap = QPixmap(320, 320)
                pixmap.fill(Qt.GlobalColor.white)
                painter = QPainter(pixmap)
                renderer.render(painter)
                painter.end()
            self.qr_label.setPixmap(pixmap)
        except Exception as e:
            self.qr_label.setText("Ошибка рендеринга: " + str(e))

        if len(self.qr_codes) > 1:
            self.chunk_label.setText(
                f"Часть {self._current_chunk + 1} из {len(self.qr_codes)}"
            )
            self.prev_btn.setEnabled(self._current_chunk > 0)
            self.next_btn.setEnabled(self._current_chunk < len(self.qr_codes) - 1)

    def _prev_chunk(self):
        if self._current_chunk > 0:
            self._current_chunk -= 1
            self._render_current_qr()

    def _next_chunk(self):
        if self._current_chunk < len(self.qr_codes) - 1:
            self._current_chunk += 1
            self._render_current_qr()

    # ── Payload info ──

    def _update_payload_info(self):
        if not self.payload_info:
            self.info_text.setPlainText("Нет данных о содержимом.")
            return
        type_labels = {
            "public_key": "Публичный ключ",
            "encrypted_entry": "Зашифрованная запись",
            "share_link": "Ссылка шеринга",
            "contact_info": "Контактная информация",
        }
        lines = []
        ptype = self.payload_info.get("type", "")
        if ptype:
            lines.append(f"Тип: {type_labels.get(ptype, ptype)}")
        if self.payload_info.get("fingerprint"):
            lines.append(f"Fingerprint: {self.payload_info['fingerprint'][:23]}...")
        if self.payload_info.get("key_id"):
            lines.append(f"Key ID: {self.payload_info['key_id'][:16]}...")
        if self.payload_info.get("algorithm"):
            lines.append(f"Алгоритм: {self.payload_info['algorithm']}")
        if self.payload_info.get("expires_at"):
            lines.append(f"Истекает: {self.payload_info['expires_at'][:19]}")
        if self.payload_info.get("chunks_total", 1) > 1:
            lines.append(f"Частей: {self.payload_info['chunks_total']}")
        self.info_text.setPlainText("\n".join(lines) if lines else "Нет данных.")

    # ── Таймер ──

    def _start_validity_timer(self):
        self._remaining_seconds = self.validity_seconds
        self._update_timer_label()
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(1000)

    def _tick(self):
        self._remaining_seconds -= 1
        self._update_timer_label()
        if self._remaining_seconds <= 0:
            self._timer.stop()
            self._on_expired()

    def _update_timer_label(self):
        if not hasattr(self, "timer_label"):
            return
        mins = self._remaining_seconds // 60
        secs = self._remaining_seconds % 60
        self.timer_label.setText(f"⏱ Действителен ещё: {mins:02d}:{secs:02d}")
        if self._remaining_seconds <= 60:
            self.timer_label.setStyleSheet("font-size: 12px; color: red; font-weight: bold;")
        else:
            self.timer_label.setStyleSheet("font-size: 12px; color: #e65100;")

    def _on_expired(self):
        if hasattr(self, "timer_label"):
            self.timer_label.setText("❌ QR-код истёк")
            self.timer_label.setStyleSheet("font-size: 12px; color: red; font-weight: bold;")
        if self._refresh_callback:
            reply = QMessageBox.question(
                self, "QR-код истёк",
                "Срок действия QR-кода истёк.\nСгенерировать новый?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            if reply == QMessageBox.StandardButton.Yes:
                self._manual_refresh()
        else:
            QMessageBox.information(self, "QR-код истёк",
                                    "Срок действия истёк. Закройте и сгенерируйте новый.")

    def set_refresh_callback(self, callback):
        self._refresh_callback = callback

    def _manual_refresh(self):
        if self._refresh_callback:
            try:
                new_qr_codes = self._refresh_callback()
                if new_qr_codes:
                    self.qr_codes = new_qr_codes
                    self._current_chunk = 0
                    self._render_current_qr()
                    if self.validity_seconds:
                        if self._timer:
                            self._timer.stop()
                        self._start_validity_timer()
            except Exception as e:
                QMessageBox.warning(self, "Ошибка", f"Не удалось обновить QR-код: {e}")

    # ── Копирование и сохранение ──

    def _copy_svg(self):
        from PyQt6.QtWidgets import QApplication
        svg_str = self.qr_codes[self._current_chunk]
        QApplication.clipboard().setText(svg_str)
        QMessageBox.information(self, "Скопировано", "SVG QR-кода скопирован в буфер обмена.")

    def _save_png(self):
        from PyQt6.QtWidgets import QFileDialog
        path, _ = QFileDialog.getSaveFileName(
            self, "Сохранить QR-код", "qr_code.png",
            "PNG изображения (*.png);;Все файлы (*)"
        )
        if not path:
            return
        try:
            pixmap = self.qr_label.pixmap()
            if pixmap and not pixmap.isNull():
                pixmap.save(path, "PNG")
                QMessageBox.information(self, "Сохранено", f"QR-код сохранён: {path}")
            else:
                QMessageBox.warning(self, "Ошибка", "QR-код ещё не сгенерирован.")
        except Exception as e:
            QMessageBox.warning(self, "Ошибка", f"Не удалось сохранить: {e}")

    def closeEvent(self, event):
        if self._timer:
            self._timer.stop()
        super().closeEvent(event)