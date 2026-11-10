"""A clickable drawing of the MK61 keyboard."""

from __future__ import annotations

from PySide6.QtCore import QRectF, Qt, Signal
from PySide6.QtGui import QColor, QFont, QPainter, QPen
from PySide6.QtWidgets import QSizePolicy, QWidget

from ..layout import LABELS, ROWS

UNIT = 15.0  # total key units per row


class KeyboardWidget(QWidget):
    """Draws the 61 keys. Each key can have a fill color, a sub-label and a selection mark."""

    keyClicked = Signal(str, object)  # key name, Qt.KeyboardModifiers

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(560, 200)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        self.setMouseTracking(True)
        self.fills: dict[str, QColor] = {}
        self.sublabels: dict[str, str] = {}
        self.highlight: set[str] = set()
        self.selected: set[str] = set()
        self._hover: str | None = None
        self._rects: dict[str, QRectF] = {}

    def heightForWidth(self, w: int) -> int:
        return int(w * 5 / UNIT) + 10

    def hasHeightForWidth(self) -> bool:
        return True

    # -- geometry --------------------------------------------------------
    def _layout(self):
        pad = 6
        u = min((self.width() - 2 * pad) / UNIT, (self.height() - 2 * pad) / 5)
        x0 = (self.width() - u * UNIT) / 2
        y0 = (self.height() - u * 5) / 2
        self._rects.clear()
        for r, row in enumerate(ROWS):
            x = x0
            for name, w in row:
                self._rects[name] = QRectF(x + 2, y0 + r * u + 2, w * u - 4, u - 4)
                x += w * u
        return u

    def key_at(self, pos) -> str | None:
        for name, rect in self._rects.items():
            if rect.contains(pos):
                return name
        return None

    # -- events ----------------------------------------------------------
    def mousePressEvent(self, ev):
        name = self.key_at(ev.position())
        if name and ev.button() == Qt.LeftButton:
            self.keyClicked.emit(name, ev.modifiers())

    def mouseMoveEvent(self, ev):
        name = self.key_at(ev.position())
        if name != self._hover:
            self._hover = name
            self.setCursor(Qt.PointingHandCursor if name else Qt.ArrowCursor)
            self.update()

    def leaveEvent(self, ev):
        self._hover = None
        self.update()

    # -- painting --------------------------------------------------------
    def paintEvent(self, ev):
        u = self._layout()
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        pal = self.palette()
        base = pal.window().color()
        dark = base.lightness() < 128
        key_bg = QColor("#2b2f36") if dark else QColor("#e9ecf1")
        key_fg = QColor("#e8eaed") if dark else QColor("#1f2328")
        accent = pal.highlight().color()

        font = QFont(self.font())
        font.setPixelSize(max(9, int(u * 0.22)))
        small = QFont(font)
        small.setPixelSize(max(8, int(u * 0.17)))

        for name, rect in self._rects.items():
            fill = self.fills.get(name)
            bg = QColor(key_bg)
            p.setPen(Qt.NoPen)
            p.setBrush(bg)
            p.drawRoundedRect(rect, 5, 5)
            if fill is not None:
                inner = rect.adjusted(3, 3, -3, -3)
                p.setBrush(fill)
                p.drawRoundedRect(inner, 4, 4)
            if name in self.highlight:
                p.setBrush(QColor(accent.red(), accent.green(), accent.blue(), 70))
                p.drawRoundedRect(rect, 5, 5)

            # outline
            if name in self.selected:
                p.setPen(QPen(accent, 2.5))
            elif name == self._hover:
                p.setPen(QPen(key_fg, 1.2))
            else:
                p.setPen(QPen(key_bg.darker(130) if not dark else key_bg.lighter(140), 1))
            p.setBrush(Qt.NoBrush)
            p.drawRoundedRect(rect, 5, 5)

            # text: on top of a colored key, pick black or white for contrast
            fg = key_fg
            if fill is not None:
                lum = 0.299 * fill.red() + 0.587 * fill.green() + 0.114 * fill.blue()
                fg = QColor("#111") if lum > 140 else QColor("#fff")
            p.setPen(fg)
            sub = self.sublabels.get(name)
            label = LABELS.get(name, name)
            if sub:
                p.setFont(small)
                top = QRectF(rect.x() + 4, rect.y() + 2, rect.width() - 8, rect.height() / 2)
                p.drawText(top, Qt.AlignLeft | Qt.AlignVCenter, label)
                p.setFont(font)
                bold = QFont(font)
                bold.setBold(True)
                p.setFont(bold)
                bot = QRectF(rect.x() + 3, rect.y() + rect.height() / 2 - 2,
                             rect.width() - 6, rect.height() / 2)
                p.drawText(bot, Qt.AlignCenter, sub)
            else:
                p.setFont(font)
                p.drawText(rect, Qt.AlignCenter, label)
        p.end()
