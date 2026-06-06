import sys
import json
import math
from pathlib import Path

from PyQt5.QtWidgets import QWidget, QApplication
from PyQt5.QtCore import Qt, QPoint, QTimer
from PyQt5.QtGui import QPainter, QColor, QPen, QBrush, QMouseEvent


class CrosshairOverlay(QWidget):
    """
    Overlay de mira fixa.

    - Janela transparente, sempre no topo, sem foco.
    - Crosshair desenhado no paintEvent.
    - Clique direito move o crosshair rapidamente para a posição do mouse.
    - Clique esquerdo inicia arraste da mira.
    - Posição salva em config_path.
    """

    def __init__(self, config_path=None, parent=None):
        super().__init__(parent)
        self.setWindowFlags(
            Qt.FramelessWindowHint
            | Qt.WindowStaysOnTopHint
            | Qt.Tool
        )
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_ShowWithoutActivating)

        self.cross_size = 14
        self.cross_thickness = 2
        self.cross_color = QColor(255, 30, 30)
        self.dot_size = 2

        self._drag_pos = QPoint()
        self._dragging = False

        self.config_path = config_path or self._default_config_path()
        self._position = self._load_position()

        self.setGeometry(
            self._position.get("x", 960),
            self._position.get("y", 540),
            64,
            64,
        )

    def _default_config_path(self):
        base = Path(sys._MEIPASS) if getattr(sys, "frozen", False) else Path(__file__).parent
        return base / "crosshair_pos.json"

    def _load_position(self):
        if not self.config_path.exists():
            return {"x": 960, "y": 540}
        try:
            with open(self.config_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if not isinstance(data, dict) or "x" not in data or "y" not in data:
                return {"x": 960, "y": 540}
            return {"x": int(data.get("x", 960)), "y": int(data.get("y", 540))}
        except Exception:
            return {"x": 960, "y": 540}

    def _save_position(self):
        try:
            data = {
                "x": self.x() + self.width() // 2,
                "y": self.y() + self.height() // 2,
            }
            with open(self.config_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            print(f"[CROSSHAIR] Failed to save position: {e}")

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)

        cx = self.width() // 2
        cy = self.height() // 2

        # Linhas horizontais
        pen = QPen(self.cross_color, self.cross_thickness)
        pen.setCapStyle(Qt.FlatCap)
        p.setPen(pen)
        p.drawLine(int(cx - self.cross_size), int(cy), int(cx - self.dot_size), int(cy))
        p.drawLine(int(cx + self.dot_size), int(cy), int(cx + self.cross_size), int(cy))

        # Linhas verticais
        p.drawLine(int(cx), int(cy - self.cross_size), int(cx), int(cy - self.dot_size))
        p.drawLine(int(cx), int(cy + self.dot_size), int(cx), int(cy + self.cross_size))

        # Ponto central
        p.setPen(Qt.NoPen)
        p.setBrush(QBrush(self.cross_color))
        p.drawEllipse(QPoint(int(cx), int(cy)), int(self.dot_size), int(self.dot_size))

    def mousePressEvent(self, event: QMouseEvent):
        if event.button() == Qt.LeftButton:
            self._dragging = True
            self._drag_pos = event.globalPos() - self.frameGeometry().topLeft()
            event.accept()
        elif event.button() == Qt.RightButton:
            # Teleport para posição atual do mouse (ajuste rápido)
            g = event.globalPos()
            self.move(int(g.x() - self.width() / 2), int(g.y() - self.height() / 2))
            self._save_position()
            event.accept()
        else:
            super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent):
        if self._dragging and event.buttons() & Qt.LeftButton:
            self.move(event.globalPos() - self._drag_pos)
            event.accept()
        else:
            super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent):
        if event.button() == Qt.LeftButton and self._dragging:
            self._dragging = False
            self._save_position()
            event.accept()
        else:
            super().mouseReleaseEvent(event)
