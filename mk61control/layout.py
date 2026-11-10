"""MK61 physical layout and key-matrix tables.

The keyboard addresses keys through a 70-slot matrix (14 columns x 5 rows,
column-major: ``index = column * 5 + row``). Not every slot has a key; empty
slots are ``""``.

The matrix order and the factory keymaps come from the official GamaKay
"MK Series" driver tables, as documented by the MK61-Studio project
(https://github.com/d4nielrx/MK61-Studio, MIT).
"""

MATRIX_LENGTH = 70

# Matrix slot -> key name (column-major).
MATRIX_KEYS = [
    "esc", "tab", "caps", "lshift", "lctrl",
    "n1", "q", "a", "", "win",
    "n2", "w", "s", "z", "lalt",
    "n3", "e", "d", "x", "",
    "n4", "r", "f", "c", "",
    "n5", "t", "g", "v", "space",
    "n6", "y", "h", "b", "",
    "n7", "u", "j", "n", "",
    "n8", "i", "k", "m", "",
    "n9", "o", "l", "comma", "",
    "n0", "p", "sem", "dot", "ralt",
    "minus", "lqu", "quo", "qmark", "menu",
    "plus", "rqu", "", "", "rctrl",
    "bksp", "bslash", "enter", "rshift", "fn",
]

KEY_INDEX = {name: i for i, name in enumerate(MATRIX_KEYS) if name}

# Visual rows: (key name, width in key units). Standard ANSI 60%.
ROWS = [
    [("esc", 1), ("n1", 1), ("n2", 1), ("n3", 1), ("n4", 1), ("n5", 1), ("n6", 1),
     ("n7", 1), ("n8", 1), ("n9", 1), ("n0", 1), ("minus", 1), ("plus", 1), ("bksp", 2)],
    [("tab", 1.5), ("q", 1), ("w", 1), ("e", 1), ("r", 1), ("t", 1), ("y", 1), ("u", 1),
     ("i", 1), ("o", 1), ("p", 1), ("lqu", 1), ("rqu", 1), ("bslash", 1.5)],
    [("caps", 1.75), ("a", 1), ("s", 1), ("d", 1), ("f", 1), ("g", 1), ("h", 1), ("j", 1),
     ("k", 1), ("l", 1), ("sem", 1), ("quo", 1), ("enter", 2.25)],
    [("lshift", 2.25), ("z", 1), ("x", 1), ("c", 1), ("v", 1), ("b", 1), ("n", 1), ("m", 1),
     ("comma", 1), ("dot", 1), ("qmark", 1), ("rshift", 2.75)],
    [("lctrl", 1.25), ("win", 1.25), ("lalt", 1.25), ("space", 6.25), ("ralt", 1.25),
     ("menu", 1.25), ("rctrl", 1.25), ("fn", 1.25)],
]

LABELS = {
    "esc": "Esc", "bksp": "Backspace", "tab": "Tab", "caps": "Caps", "enter": "Enter",
    "space": "", "lshift": "Shift", "rshift": "Shift", "lctrl": "Ctrl", "rctrl": "Ctrl",
    "lalt": "Alt", "ralt": "Alt", "win": "Win", "menu": "Menu", "fn": "Fn",
    "minus": "-", "plus": "=", "lqu": "[", "rqu": "]", "bslash": "\\", "sem": ";",
    "quo": "'", "comma": ",", "dot": ".", "qmark": "/",
}
for _i in range(10):
    LABELS[f"n{_i}"] = str(_i)
for _c in "abcdefghijklmnopqrstuvwxyz":
    LABELS[_c] = _c.upper()

# Factory keymaps, indexed by matrix slot. Values are USB HID usage IDs plus
# a few firmware-specific codes (see keycodes.py).
DEFAULT_NORMAL = [
    0x29, 0x2B, 0x39, 0xE1, 0xE0, 0x1E, 0x14, 0x04, 0x00, 0xE3,
    0x1F, 0x1A, 0x16, 0x1D, 0xE2, 0x20, 0x08, 0x07, 0x1B, 0x00,
    0x21, 0x15, 0x09, 0x06, 0x00, 0x22, 0x17, 0x0A, 0x19, 0x2C,
    0x23, 0x1C, 0x0B, 0x05, 0x00, 0x24, 0x18, 0x0D, 0x11, 0x00,
    0x25, 0x0C, 0x0E, 0x10, 0x00, 0x26, 0x12, 0x0F, 0x36, 0x00,
    0x27, 0x13, 0x33, 0x37, 0xE6, 0x2D, 0x2F, 0x34, 0x38, 0x65,
    0x2E, 0x30, 0x00, 0x00, 0xE4, 0x2A, 0x31, 0x28, 0xE5, 0xAC,
]

DEFAULT_FN = [
    0x35, 0x00, 0x39, 0xE1, 0xE0, 0x3A, 0xAD, 0xA7, 0x00, 0xB1,
    0x3B, 0xAE, 0xA6, 0x1D, 0xE2, 0x3C, 0xAF, 0xA8, 0x1B, 0x00,
    0x3D, 0xB0, 0xA9, 0x06, 0x00, 0x3E, 0x17, 0xAA, 0x19, 0xF3,
    0x3F, 0x1C, 0xAB, 0x05, 0x00, 0x40, 0x46, 0x49, 0xB5, 0x00,
    0x41, 0x47, 0x4A, 0x4C, 0x00, 0x42, 0x48, 0x4B, 0x4D, 0x00,
    0x43, 0xD7, 0xDE, 0x4E, 0x50, 0x44, 0xD6, 0xDF, 0x52, 0x51,
    0x45, 0xF8, 0x00, 0x00, 0x4F, 0xF9, 0xD9, 0xFC, 0xE5, 0xAC,
]

assert len(MATRIX_KEYS) == len(DEFAULT_NORMAL) == len(DEFAULT_FN) == MATRIX_LENGTH
