"""MK61 Control - main window."""

from __future__ import annotations

import json
import sys
import time
from contextlib import contextmanager

from PySide6.QtCore import QElapsedTimer, Qt
from PySide6.QtGui import QAction, QColor, QIcon, QKeySequence, QPixmap, QPainter
from PySide6.QtWidgets import (
    QAbstractItemView, QApplication, QButtonGroup, QCheckBox, QColorDialog, QComboBox,
    QDialog, QDialogButtonBox, QFileDialog, QFormLayout, QFrame, QGridLayout, QGroupBox,
    QHBoxLayout, QHeaderView, QLabel, QListWidget, QListWidgetItem, QMainWindow, QMessageBox,
    QPushButton, QRadioButton, QSlider, QSpinBox, QStatusBar, QTableWidget, QTableWidgetItem,
    QTabWidget, QToolButton, QVBoxLayout, QWidget,
)

from .. import __version__, effects as fx, keycodes, store
from ..device import BRIGHTNESS_MAX, DIRECTION_MAX, MK61, Lighting, MK61Error, find_devices
from ..layout import DEFAULT_FN, DEFAULT_NORMAL, KEY_INDEX, LABELS, MATRIX_LENGTH
from .keyboard import KeyboardWidget
from .qtkeys import HID_TO_KEYNAME, event_to_hid

REPO_URL = "https://github.com/omerfarukmmt/mk61-control"


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def qcolor(rgb) -> QColor:
    return QColor(*rgb)


def rgb_of(c: QColor):
    return (c.red(), c.green(), c.blue())


def hex_of(rgb) -> str:
    return "#%02x%02x%02x" % tuple(rgb)


class ColorButton(QToolButton):
    """A swatch that opens a color picker."""

    def __init__(self, rgb=(255, 255, 255), parent=None):
        super().__init__(parent)
        self.setFixedSize(34, 26)
        self.set_rgb(rgb)
        self.clicked.connect(self._pick)

    def set_rgb(self, rgb):
        self.rgb = tuple(rgb)
        self.setStyleSheet(
            f"QToolButton{{background:{hex_of(self.rgb)};border:1px solid #888;border-radius:4px}}")
        self.setToolTip(hex_of(self.rgb))

    def _pick(self):
        c = QColorDialog.getColor(qcolor(self.rgb), self, "Pick a color")
        if c.isValid():
            self.set_rgb(rgb_of(c))


def labeled_slider(lo, hi, value):
    s = QSlider(Qt.Horizontal)
    s.setRange(lo, hi)
    s.setValue(value)
    lab = QLabel(str(value))
    lab.setMinimumWidth(28)
    s.valueChanged.connect(lambda v: lab.setText(str(v)))
    row = QHBoxLayout()
    row.addWidget(s, 1)
    row.addWidget(lab)
    return s, row


# ---------------------------------------------------------------------------
# Lighting tab
# ---------------------------------------------------------------------------

class LightingTab(QWidget):
    def __init__(self, win: "MainWindow"):
        super().__init__()
        self.win = win
        lay = QVBoxLayout(self)

        form = QFormLayout()
        self.effect = QComboBox()
        for e in fx.EFFECTS:
            if e.id != fx.CUSTOM:
                self.effect.addItem(e.name, e.id)
        self.effect.currentIndexChanged.connect(self._effect_changed)
        form.addRow("Effect", self.effect)

        self.colors_box = QHBoxLayout()
        self.colors_box.setSpacing(4)
        cw = QWidget()
        cw.setLayout(self.colors_box)
        self.colors_row_label = QLabel("Colors")
        form.addRow(self.colors_row_label, cw)
        self.swatches: list[ColorButton] = []

        self.brightness, row = labeled_slider(0, BRIGHTNESS_MAX, BRIGHTNESS_MAX)
        form.addRow("Brightness", row)
        self.speed, row = labeled_slider(0, 100, 50)
        form.addRow("Speed", row)
        self.direction = QComboBox()
        for i, n in enumerate(["Direction 1", "Direction 2", "Direction 3", "Direction 4"]):
            self.direction.addItem(n, i)
        form.addRow("Direction", self.direction)
        self.led_on = QCheckBox("Backlight on")
        self.led_on.setChecked(True)
        form.addRow("", self.led_on)
        lay.addLayout(form)

        hint = QLabel("Settings are saved on the keyboard itself, so they stay after "
                      "you close this app or unplug the keyboard.")
        hint.setWordWrap(True)
        hint.setStyleSheet("color: gray")
        lay.addWidget(hint)
        lay.addStretch(1)

        btns = QHBoxLayout()
        btns.addStretch(1)
        reload_btn = QPushButton("Reload from keyboard")
        reload_btn.clicked.connect(self.load)
        self.apply_btn = QPushButton("Apply")
        self.apply_btn.setDefault(True)
        self.apply_btn.clicked.connect(self.apply)
        btns.addWidget(reload_btn)
        btns.addWidget(self.apply_btn)
        lay.addLayout(btns)
        self._effect_changed()

    def _set_swatches(self, n, colors):
        while self.colors_box.count():
            item = self.colors_box.takeAt(0)
            if item.widget() is not None:
                item.widget().setParent(None)
        self.swatches = []
        for i in range(n):
            b = ColorButton(colors[i] if i < len(colors) else (255, 255, 255))
            self.swatches.append(b)
            self.colors_box.addWidget(b)
        self.colors_box.addStretch(1)
        self.colors_row_label.setVisible(n > 0)

    def _effect_changed(self):
        e = fx.BY_ID[self.effect.currentData()]
        old = [s.rgb for s in self.swatches]
        self._set_swatches(e.colors, old or [(255, 255, 255)])
        animated = e.id not in (12,)
        self.speed.setEnabled(animated)
        self.direction.setEnabled(animated)

    def load(self):
        with self.win.device() as kb:
            if kb is None:
                return
            L = kb.read_lighting(self.win.profile)
        idx = self.effect.findData(L.effect)
        if idx < 0:  # custom per-key mode
            idx = self.effect.findData(12)
        self.effect.blockSignals(True)
        self.effect.setCurrentIndex(idx)
        self.effect.blockSignals(False)
        e = fx.BY_ID[self.effect.currentData()]
        self._set_swatches(e.colors, L.colors)
        self.speed.setEnabled(e.id != 12)
        self.direction.setEnabled(e.id != 12)
        self.brightness.setValue(min(L.brightness, BRIGHTNESS_MAX))
        self.speed.setValue(L.speed)
        self.direction.setCurrentIndex(min(L.direction, DIRECTION_MAX))
        self.led_on.setChecked(L.led_on)
        if L.effect == fx.CUSTOM:
            self.win.status("This profile uses per-key colors (see the Per-key tab).")

    def apply(self):
        L = Lighting(effect=self.effect.currentData(), brightness=self.brightness.value(),
                     speed=self.speed.value(), direction=self.direction.currentData(),
                     colors=[s.rgb for s in self.swatches] or [(255, 255, 255)],
                     led_on=self.led_on.isChecked())
        with self.win.device() as kb:
            if kb is None:
                return
            kb.write_lighting(self.win.profile, L)
            kb.reload_lights(self.win.profile)
        self.win.status(f"Lighting saved to profile {self.win.profile}.")


# ---------------------------------------------------------------------------
# Per-key tab
# ---------------------------------------------------------------------------

class PerKeyTab(QWidget):
    PALETTE = [(255, 0, 0), (255, 128, 0), (255, 255, 0), (0, 255, 0), (0, 255, 255),
               (0, 0, 255), (160, 0, 255), (255, 0, 255), (255, 255, 255), (0, 0, 0)]

    def __init__(self, win: "MainWindow"):
        super().__init__()
        self.win = win
        lay = QVBoxLayout(self)
        tip = QLabel("Pick a color, then click keys to paint them. "
                     "Shift-click paints a whole row.")
        tip.setStyleSheet("color: gray")
        lay.addWidget(tip)

        tools = QHBoxLayout()
        tools.addWidget(QLabel("Brush"))
        self.brush = ColorButton((255, 0, 0))
        tools.addWidget(self.brush)
        for rgb in self.PALETTE:
            b = QToolButton()
            b.setFixedSize(22, 22)
            b.setStyleSheet(f"background:{hex_of(rgb)};border:1px solid #888;border-radius:3px")
            b.clicked.connect(lambda _=False, c=rgb: self.brush.set_rgb(c))
            tools.addWidget(b)
        tools.addStretch(1)
        fill = QPushButton("Fill all")
        fill.clicked.connect(self.fill_all)
        tools.addWidget(fill)
        lay.addLayout(tools)

        self.kbd = KeyboardWidget()
        self.kbd.keyClicked.connect(self.paint)
        lay.addWidget(self.kbd, 1)

        row = QHBoxLayout()
        bri_label = QLabel("Brightness")
        self.brightness, brow = labeled_slider(0, BRIGHTNESS_MAX, BRIGHTNESS_MAX)
        row.addWidget(bri_label)
        row.addLayout(brow, 1)
        load = QPushButton("Open design…")
        load.clicked.connect(self.open_file)
        save = QPushButton("Save design…")
        save.clicked.connect(self.save_file)
        apply_btn = QPushButton("Apply")
        apply_btn.setDefault(True)
        apply_btn.clicked.connect(self.apply)
        row.addWidget(load)
        row.addWidget(save)
        row.addWidget(apply_btn)
        lay.addLayout(row)

    def load(self):
        prof = self.win.data[str(self.win.profile)]
        design = prof.get("perkey") or {}
        self.kbd.fills = {k: QColor(v) for k, v in design.items() if k in KEY_INDEX}
        self.kbd.update()

    def _store(self):
        self.win.data[str(self.win.profile)]["perkey"] = {
            k: c.name() for k, c in self.kbd.fills.items()}
        store.save(self.win.data)

    def paint(self, name, mods):
        from ..layout import ROWS
        targets = [name]
        if mods & Qt.ShiftModifier:
            for row in ROWS:
                if any(k == name for k, _ in row):
                    targets = [k for k, _ in row]
        for k in targets:
            self.kbd.fills[k] = qcolor(self.brush.rgb)
        self.kbd.update()
        self._store()

    def fill_all(self):
        for k in KEY_INDEX:
            self.kbd.fills[k] = qcolor(self.brush.rgb)
        self.kbd.update()
        self._store()

    def open_file(self):
        fn, _ = QFileDialog.getOpenFileName(self, "Open design", "", "Design (*.json)")
        if not fn:
            return
        try:
            with open(fn, encoding="utf-8") as f:
                design = json.load(f)
            self.kbd.fills = {k: QColor(v) for k, v in design.items() if k in KEY_INDEX}
        except (OSError, ValueError) as e:
            QMessageBox.warning(self, "Open design", f"Could not read the file:\n{e}")
            return
        self.kbd.update()
        self._store()

    def save_file(self):
        fn, _ = QFileDialog.getSaveFileName(self, "Save design", "mk61-design.json",
                                            "Design (*.json)")
        if fn:
            with open(fn, "w", encoding="utf-8") as f:
                json.dump({k: c.name() for k, c in self.kbd.fills.items()}, f, indent=1)

    def apply(self):
        colors = {KEY_INDEX[k]: rgb_of(c) for k, c in self.kbd.fills.items()}
        with self.win.device() as kb:
            if kb is None:
                return
            kb.write_per_key(self.win.profile, colors, default=(0, 0, 0),
                             brightness=self.brightness.value())
        self.win.status(f"Per-key colors saved to profile {self.win.profile}.")


# ---------------------------------------------------------------------------
# Key assignment
# ---------------------------------------------------------------------------

class MacroEditor(QDialog):
    """Edit or record a list of (key, down/up, delay) steps."""

    def __init__(self, macro: dict | None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Macro")
        self.resize(460, 420)
        macro = macro or {"repeat": 1, "steps": []}
        lay = QVBoxLayout(self)

        top = QHBoxLayout()
        self.record_btn = QPushButton("● Record")
        self.record_btn.setCheckable(True)
        self.record_btn.toggled.connect(self._toggle_record)
        top.addWidget(self.record_btn)
        clear = QPushButton("Clear")
        clear.clicked.connect(lambda: self.table.setRowCount(0))
        top.addWidget(clear)
        top.addStretch(1)
        top.addWidget(QLabel("Repeat"))
        self.repeat = QSpinBox()
        self.repeat.setRange(1, 999)
        self.repeat.setValue(int(macro.get("repeat", 1)))
        top.addWidget(self.repeat)
        lay.addLayout(top)

        self.info = QLabel("Press Record, type the keys, then press Record again.")
        self.info.setStyleSheet("color: gray")
        lay.addWidget(self.info)

        self.table = QTableWidget(0, 3)
        self.table.setHorizontalHeaderLabels(["Key", "Action", "Delay (ms)"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.DoubleClicked)
        lay.addWidget(self.table, 1)
        for code, down, delay in macro.get("steps", []):
            self._add(code, down, delay)

        row = QHBoxLayout()
        rm = QPushButton("Remove step")
        rm.clicked.connect(lambda: self.table.removeRow(self.table.currentRow()))
        row.addWidget(rm)
        row.addStretch(1)
        bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        row.addWidget(bb)
        lay.addLayout(row)
        self._timer = QElapsedTimer()

    def _add(self, code, down, delay):
        r = self.table.rowCount()
        self.table.insertRow(r)
        item = QTableWidgetItem(keycodes.name(code))
        item.setData(Qt.UserRole, code)
        item.setFlags(item.flags() & ~Qt.ItemIsEditable)
        self.table.setItem(r, 0, item)
        act = QTableWidgetItem("Press" if down else "Release")
        act.setData(Qt.UserRole, bool(down))
        act.setFlags(act.flags() & ~Qt.ItemIsEditable)
        self.table.setItem(r, 1, act)
        self.table.setItem(r, 2, QTableWidgetItem(str(int(delay))))

    def _toggle_record(self, on):
        self.record_btn.setText("■ Stop" if on else "● Record")
        self.info.setText("Recording… type now." if on else
                          "Press Record, type the keys, then press Record again.")
        if on:
            self.table.setRowCount(0)
            self._timer.start()
            self.grabKeyboard()
        else:
            self.releaseKeyboard()

    def _rec(self, ev, down):
        if not self.record_btn.isChecked() or ev.isAutoRepeat():
            return False
        code = event_to_hid(ev)
        if not code:
            return True
        delay = max(20, self._timer.restart()) if self.table.rowCount() else 20
        if self.table.rowCount():
            # the delay belongs to the previous step (wait after it)
            self.table.item(self.table.rowCount() - 1, 2).setText(str(delay))
        self._add(code, down, 20)
        if self.table.rowCount() >= 84:
            self.record_btn.setChecked(False)
        return True

    def keyPressEvent(self, ev):
        if not self._rec(ev, True):
            super().keyPressEvent(ev)

    def keyReleaseEvent(self, ev):
        if not self._rec(ev, False):
            super().keyReleaseEvent(ev)

    def result_macro(self) -> dict:
        steps = []
        for r in range(self.table.rowCount()):
            code = self.table.item(r, 0).data(Qt.UserRole)
            down = self.table.item(r, 1).data(Qt.UserRole)
            try:
                delay = int(self.table.item(r, 2).text())
            except ValueError:
                delay = 20
            steps.append([code, bool(down), max(20, delay)])
        return {"repeat": self.repeat.value(), "steps": steps}


class KeyPicker(QDialog):
    """Choose what a key should do."""

    def __init__(self, key: str, current: int, default: int, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"Assign key: {LABELS.get(key, key)}")
        self.resize(380, 460)
        self.choice = current
        self.want_macro = False
        lay = QVBoxLayout(self)
        lay.addWidget(QLabel(f"Currently: <b>{keycodes.name(current)}</b> "
                             f"(factory: {keycodes.name(default)})"))
        self.group = QComboBox()
        for name, _ in keycodes.GROUPS:
            self.group.addItem(name)
        lay.addWidget(self.group)
        self.list = QListWidget()
        lay.addWidget(self.list, 1)
        self.group.currentIndexChanged.connect(self._fill)
        self._fill(0)
        self.list.itemDoubleClicked.connect(lambda _: self.accept())

        row = QHBoxLayout()
        macro = QPushButton("Macro…")
        macro.clicked.connect(self._macro)
        reset = QPushButton("Factory default")
        reset.clicked.connect(lambda: self._done(default))
        row.addWidget(macro)
        row.addWidget(reset)
        row.addStretch(1)
        bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        row.addWidget(bb)
        lay.addLayout(row)

    def _fill(self, idx):
        self.list.clear()
        for code in keycodes.GROUPS[idx][1]:
            it = QListWidgetItem(keycodes.name(code))
            it.setData(Qt.UserRole, code)
            self.list.addItem(it)

    def _done(self, code):
        self.choice = code
        super().accept()

    def _macro(self):
        self.want_macro = True
        self.choice = keycodes.MACRO
        super().accept()

    def accept(self):
        it = self.list.currentItem()
        if it is not None:
            self.choice = it.data(Qt.UserRole)
        super().accept()


class KeysTab(QWidget):
    def __init__(self, win: "MainWindow"):
        super().__init__()
        self.win = win
        lay = QVBoxLayout(self)
        top = QHBoxLayout()
        self.normal_btn = QRadioButton("Normal layer")
        self.fn_btn = QRadioButton("Fn layer (while holding Fn)")
        self.normal_btn.setChecked(True)
        grp = QButtonGroup(self)
        grp.addButton(self.normal_btn)
        grp.addButton(self.fn_btn)
        self.normal_btn.toggled.connect(self.refresh)
        top.addWidget(self.normal_btn)
        top.addWidget(self.fn_btn)
        top.addStretch(1)
        lay.addLayout(top)

        tip = QLabel("Click a key to change what it does. Changed keys are highlighted. "
                     "The keyboard cannot report its keymap, so this app remembers it.")
        tip.setWordWrap(True)
        tip.setStyleSheet("color: gray")
        lay.addWidget(tip)

        self.kbd = KeyboardWidget()
        self.kbd.keyClicked.connect(self.edit_key)
        lay.addWidget(self.kbd, 1)

        btns = QHBoxLayout()
        reset = QPushButton("Reset layer to factory")
        reset.clicked.connect(self.reset_layer)
        btns.addWidget(reset)
        btns.addStretch(1)
        self.dirty_label = QLabel("")
        self.dirty_label.setStyleSheet("color: #c77700")
        btns.addWidget(self.dirty_label)
        apply_btn = QPushButton("Apply")
        apply_btn.setDefault(True)
        apply_btn.clicked.connect(self.apply)
        btns.addWidget(apply_btn)
        lay.addLayout(btns)

    @property
    def layer(self):
        return "fn" if self.fn_btn.isChecked() else "normal"

    @property
    def prof(self):
        return self.win.data[str(self.win.profile)]

    def load(self):
        self.dirty_label.setText("")
        self.refresh()

    def refresh(self):
        values = self.prof[self.layer]
        defaults = DEFAULT_FN if self.layer == "fn" else DEFAULT_NORMAL
        self.kbd.sublabels.clear()
        self.kbd.highlight.clear()
        for name, slot in KEY_INDEX.items():
            v = values[slot]
            if self.layer == "fn" or v != defaults[slot]:
                if v != 0 or self.layer == "normal":
                    self.kbd.sublabels[name] = _short(v)
            if v != defaults[slot]:
                self.kbd.highlight.add(name)
        self.kbd.update()

    def edit_key(self, name, _mods):
        slot = KEY_INDEX[name]
        values = self.prof[self.layer]
        defaults = DEFAULT_FN if self.layer == "fn" else DEFAULT_NORMAL
        dlg = KeyPicker(name, values[slot], defaults[slot], self)
        if not dlg.exec():
            return
        macro_slot = str(slot + (MATRIX_LENGTH if self.layer == "fn" else 0))
        if dlg.want_macro:
            ed = MacroEditor(self.prof["macros"].get(macro_slot), self)
            if not ed.exec():
                return
            m = ed.result_macro()
            if not m["steps"]:
                return
            self.prof["macros"][macro_slot] = m
        else:
            self.prof["macros"].pop(macro_slot, None)
        if name == "fn" and self.layer == "normal" and dlg.choice != keycodes.FN:
            if QMessageBox.question(
                    self, "Fn key",
                    "Without an Fn key you cannot reach the Fn layer (arrows, media, "
                    "lighting keys). Continue?") != QMessageBox.Yes:
                return
        values[slot] = dlg.choice
        store.save(self.win.data)
        self.dirty_label.setText("Not applied yet")
        self.refresh()

    def reset_layer(self):
        defaults = DEFAULT_FN if self.layer == "fn" else DEFAULT_NORMAL
        self.prof[self.layer] = list(defaults)
        offset = MATRIX_LENGTH if self.layer == "fn" else 0
        for slot in list(self.prof["macros"]):
            if offset <= int(slot) < offset + MATRIX_LENGTH:
                del self.prof["macros"][slot]
        store.save(self.win.data)
        self.dirty_label.setText("Not applied yet")
        self.refresh()

    def apply(self):
        p = self.win.profile
        with self.win.device() as kb:
            if kb is None:
                return
            kb.write_keymap(p, self.prof["normal"], self.prof["fn"])
            for slot, m in self.prof["macros"].items():
                layer = "fn" if int(slot) >= MATRIX_LENGTH else "normal"
                if self.prof[layer][int(slot) % MATRIX_LENGTH] == keycodes.MACRO:
                    kb.write_macro(p, int(slot), [tuple(s) for s in m["steps"]],
                                   int(m.get("repeat", 1)))
        self.dirty_label.setText("")
        self.win.status(f"Keymap saved to profile {p}.")


def _short(code: int) -> str:
    n = keycodes.name(code)
    short = {"Disabled": "—", "Backspace": "Bksp", "Caps Lock": "Caps", "Print Screen": "PrtSc",
             "Scroll Lock": "ScrLk", "Page Up": "PgUp", "Page Down": "PgDn", "Delete": "Del",
             "Insert": "Ins", "Play/Pause": "▶︎❚❚", "Volume Up": "Vol+", "Volume Down": "Vol−",
             "Media Next": "⏭", "Media Prev": "⏮", "Media Stop": "⏹", "Right": "→", "Left": "←",
             "Up": "↑", "Down": "↓", "Brightness +": "☀+", "Brightness -": "☀−",
             "Next Effect": "FX", "LED On/Off": "LED", "Custom Lighting": "Cust",
             "Endurance Mode": "Endur", "Speed +": "Spd+", "Speed -": "Spd−",
             "Win Lock": "WinLk", "NKRO/6KRO": "NKRO", "Next Color": "Color"}
    n = short.get(n, n)
    for a, b in (("Left ", "L"), ("Right ", "R"), ("Profile ", "P"), ("Mouse ", "M-")):
        n = n.replace(a, b)
    return n


# ---------------------------------------------------------------------------
# Key tester
# ---------------------------------------------------------------------------

class TesterTab(QWidget):
    def __init__(self, win):
        super().__init__()
        lay = QVBoxLayout(self)
        tip = QLabel("Click here and press keys. Each key lights up when the computer "
                     "receives it. Use it to check switches or a new keymap.")
        tip.setWordWrap(True)
        tip.setStyleSheet("color: gray")
        lay.addWidget(tip)
        self.kbd = KeyboardWidget()
        self.kbd.setFocusPolicy(Qt.StrongFocus)
        self.kbd.keyPressEvent = self._press
        self.kbd.keyReleaseEvent = self._release
        lay.addWidget(self.kbd, 1)
        self.last = QLabel("Last key: —")
        lay.addWidget(self.last)
        clear = QPushButton("Clear")
        clear.clicked.connect(self._clear)
        lay.addWidget(clear, 0, Qt.AlignRight)
        self.kbd.keyClicked.connect(lambda *_: self.kbd.setFocus())

    def _clear(self):
        self.kbd.fills.clear()
        self.kbd.update()
        self.kbd.setFocus()

    def _press(self, ev):
        code = event_to_hid(ev)
        self.last.setText(f"Last key: {keycodes.name(code)} (HID 0x{code:02X})")
        name = HID_TO_KEYNAME.get(code)
        if ev.key() == Qt.Key_QuoteLeft:
            name = "esc"
        if name:
            self.kbd.fills[name] = QColor("#2ea043")
            self.kbd.selected.add(name)
            self.kbd.update()

    def _release(self, ev):
        name = HID_TO_KEYNAME.get(event_to_hid(ev))
        if name:
            self.kbd.selected.discard(name)
            self.kbd.update()

    def load(self):
        pass


# ---------------------------------------------------------------------------
# Settings tab
# ---------------------------------------------------------------------------

class SettingsTab(QWidget):
    def __init__(self, win: "MainWindow"):
        super().__init__()
        self.win = win
        lay = QVBoxLayout(self)

        box = QGroupBox("Profile options")
        f = QVBoxLayout(box)
        self.win_lock = QCheckBox("Lock the Windows key (useful in games)")
        self.arrow_swap = QCheckBox("Swap arrow-key layout")
        f.addWidget(self.win_lock)
        f.addWidget(self.arrow_swap)
        ap = QPushButton("Apply options")
        ap.clicked.connect(self.apply_options)
        f.addWidget(ap, 0, Qt.AlignRight)
        lay.addWidget(box)

        box = QGroupBox("Backup")
        g = QHBoxLayout(box)
        b1 = QPushButton("Save backup…")
        b1.clicked.connect(self.backup)
        b2 = QPushButton("Restore backup…")
        b2.clicked.connect(self.restore)
        g.addWidget(b1)
        g.addWidget(b2)
        g.addStretch(1)
        lay.addWidget(box)

        box = QGroupBox("Factory reset")
        g = QHBoxLayout(box)
        lab = QLabel("Restores factory lighting and keys on all four profiles.")
        lab.setWordWrap(True)
        g.addWidget(lab, 1)
        b = QPushButton("Factory reset…")
        b.clicked.connect(self.factory_reset)
        g.addWidget(b)
        lay.addWidget(box)

        self.about = QLabel()
        self.about.setOpenExternalLinks(True)
        self.about.setWordWrap(True)
        self.about.setStyleSheet("color: gray")
        lay.addStretch(1)
        lay.addWidget(self.about)

    def load(self):
        prof = self.win.data[str(self.win.profile)]
        self.win_lock.setChecked(bool(prof.get("win_lock")))
        self.arrow_swap.setChecked(bool(prof.get("arrow_swap")))
        dev = self.win.info
        devtxt = (f"{dev.model}, firmware {dev.firmware_str} "
                  f"({dev.vid:04X}:{dev.pid:04X})") if dev else "no keyboard"
        self.about.setText(
            f"MK61 Control {__version__} · {devtxt}<br>"
            f"Unofficial, not affiliated with GamaKay. "
            f"<a href='{REPO_URL}'>Source code and help</a>")

    def apply_options(self):
        prof = self.win.data[str(self.win.profile)]
        prof["win_lock"] = self.win_lock.isChecked()
        prof["arrow_swap"] = self.arrow_swap.isChecked()
        store.save(self.win.data)
        with self.win.device() as kb:
            if kb is None:
                return
            kb.write_options(self.win.profile, prof["arrow_swap"], prof["win_lock"])
        self.win.status("Options saved.")

    def backup(self):
        fn, _ = QFileDialog.getSaveFileName(self, "Save backup", "mk61-backup.json",
                                            "Backup (*.json)")
        if not fn:
            return
        with self.win.device() as kb:
            if kb is None:
                return
            data = kb.backup()
        data["app"] = {k: v for k, v in self.win.data.items()}
        with open(fn, "w", encoding="utf-8") as f:
            json.dump(data, f)
        self.win.status(f"Backup saved to {fn}")

    def restore(self):
        fn, _ = QFileDialog.getOpenFileName(self, "Restore backup", "", "Backup (*.json)")
        if not fn:
            return
        try:
            with open(fn, encoding="utf-8") as f:
                data = json.load(f)
            assert "blocks" in data
        except (OSError, ValueError, AssertionError):
            QMessageBox.warning(self, "Restore", "This is not an MK61 Control backup file.")
            return
        with self.win.device() as kb:
            if kb is None:
                return
            kb.restore(data)
            if "app" in data:
                self.win.data.update(data["app"])
                store.save(self.win.data)
                for p in (1, 2, 3, 4):
                    prof = self.win.data[str(p)]
                    kb.write_keymap(p, prof["normal"], prof["fn"])
        self.win.reload_all()
        self.win.status("Backup restored.")

    def factory_reset(self):
        if QMessageBox.question(self, "Factory reset",
                                "Reset lighting and keys on all four profiles?") != QMessageBox.Yes:
            return
        with self.win.device() as kb:
            if kb is None:
                return
            kb.factory_reset()
            kb.reload_lights(1)
        for p in ("1", "2", "3", "4"):
            self.win.data[p] = store.default_profile()
        store.save(self.win.data)
        self.win.profile = 1
        self.win.reload_all()
        self.win.status("Factory settings restored.")


# ---------------------------------------------------------------------------
# Main window
# ---------------------------------------------------------------------------

def app_icon(size: int = 64) -> QIcon:
    pm = QPixmap(size, size)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing)
    p.scale(size / 64, size / 64)
    p.setBrush(QColor("#1f2328"))
    p.setPen(Qt.NoPen)
    p.drawRoundedRect(4, 14, 56, 36, 7, 7)
    colors = ["#ff4d4d", "#ffb84d", "#ffe14d", "#4dff88", "#4dd2ff", "#8c4dff"]
    for r in range(3):
        for c in range(6):
            p.setBrush(QColor(colors[(c + r) % 6]))
            p.drawRoundedRect(9 + c * 8, 19 + r * 9, 6, 6, 1.5, 1.5)
    p.end()
    return QIcon(pm)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("MK61 Control")
        self.setWindowIcon(app_icon())
        self.resize(900, 560)
        self.data = store.load()
        self.profile = 1
        self.info = None

        central = QWidget()
        lay = QVBoxLayout(central)

        head = QHBoxLayout()
        self.dev_label = QLabel("Looking for the keyboard…")
        f = self.dev_label.font()
        f.setBold(True)
        self.dev_label.setFont(f)
        head.addWidget(self.dev_label)
        head.addStretch(1)
        head.addWidget(QLabel("Profile"))
        self.profile_group = QButtonGroup(self)
        for p in (1, 2, 3, 4):
            b = QPushButton(str(p))
            b.setCheckable(True)
            b.setFixedWidth(40)
            self.profile_group.addButton(b, p)
            head.addWidget(b)
        self.profile_group.idClicked.connect(self.select_profile)
        refresh = QPushButton("Reconnect")
        refresh.clicked.connect(self.connect)
        head.addWidget(refresh)
        lay.addLayout(head)

        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        line.setFrameShadow(QFrame.Sunken)
        lay.addWidget(line)

        self.tabs = QTabWidget()
        self.lighting = LightingTab(self)
        self.perkey = PerKeyTab(self)
        self.keys = KeysTab(self)
        self.tester = TesterTab(self)
        self.settings = SettingsTab(self)
        self.tabs.addTab(self.lighting, "Lighting")
        self.tabs.addTab(self.perkey, "Per-key colors")
        self.tabs.addTab(self.keys, "Keys && macros")
        self.tabs.addTab(self.tester, "Key tester")
        self.tabs.addTab(self.settings, "Settings")
        lay.addWidget(self.tabs, 1)
        self.setCentralWidget(central)
        self.setStatusBar(QStatusBar())

        quit_act = QAction(self)
        quit_act.setShortcut(QKeySequence.Quit)
        quit_act.triggered.connect(self.close)
        self.addAction(quit_act)
        self.connect()

    # -- device access ---------------------------------------------------
    @contextmanager
    def device(self):
        """Open the keyboard for one operation; show errors instead of crashing."""
        QApplication.setOverrideCursor(Qt.WaitCursor)
        kb = None
        try:
            try:
                kb = MK61(self.info) if self.info else MK61()
                self.info = kb.info
            except MK61Error as e:
                self._offline(str(e))
                yield None
                return
            try:
                yield kb
            except MK61Error as e:
                QMessageBox.warning(self, "MK61 Control", str(e))
            except OSError as e:
                self.info = None
                QMessageBox.warning(self, "MK61 Control",
                                    f"Lost connection to the keyboard ({e}). Click Reconnect.")
        finally:
            if kb is not None:
                kb.close()
            QApplication.restoreOverrideCursor()

    def _offline(self, msg):
        self.info = None
        self.dev_label.setText("Keyboard not found")
        self.status(msg)

    def status(self, msg):
        self.statusBar().showMessage(msg, 8000)

    def connect(self):
        self.info = None
        try:
            devs = find_devices()
        except MK61Error as e:
            self._offline(str(e))
            return
        if not devs:
            self._offline("Plug in the MK61 with its USB cable, then click Reconnect.")
            self.settings.load()
            return
        self.info = devs[0]
        self.dev_label.setText(f"GamaKay {self.info.model} · firmware {self.info.firmware_str}")
        with self.device() as kb:
            if kb is not None:
                self.profile = kb.active_profile()
        self.reload_all()
        self.status("Connected.")

    def reload_all(self):
        self.profile_group.button(self.profile).setChecked(True)
        for tab in (self.lighting, self.perkey, self.keys, self.tester, self.settings):
            tab.load()

    def select_profile(self, p):
        with self.device() as kb:
            if kb is None:
                self.profile_group.button(self.profile).setChecked(True)
                return
            kb.set_profile(p)
            self.profile = p
        self.reload_all()
        self.status(f"Profile {p} is now active on the keyboard.")


def run():
    if sys.platform == "win32":
        try:  # own taskbar icon instead of python.exe's
            import ctypes
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("mk61control.app")
        except Exception:
            pass
    app = QApplication.instance() or QApplication(sys.argv)
    app.setApplicationName("MK61 Control")
    app.setStyle("Fusion")
    w = MainWindow()
    w.show()
    return app.exec()
