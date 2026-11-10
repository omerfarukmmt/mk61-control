"""Translate Qt key events to HID usage codes and MK61 key names."""

from PySide6.QtCore import Qt

K = Qt.Key

QT_TO_HID: dict[int, int] = {
    K.Key_Return: 0x28, K.Key_Enter: 0x28, K.Key_Escape: 0x29, K.Key_Backspace: 0x2A,
    K.Key_Tab: 0x2B, K.Key_Backtab: 0x2B, K.Key_Space: 0x2C, K.Key_Minus: 0x2D,
    K.Key_Underscore: 0x2D, K.Key_Equal: 0x2E, K.Key_Plus: 0x2E, K.Key_BracketLeft: 0x2F,
    K.Key_BraceLeft: 0x2F, K.Key_BracketRight: 0x30, K.Key_BraceRight: 0x30,
    K.Key_Backslash: 0x31, K.Key_Bar: 0x31, K.Key_Semicolon: 0x33, K.Key_Colon: 0x33,
    K.Key_Apostrophe: 0x34, K.Key_QuoteDbl: 0x34, K.Key_QuoteLeft: 0x35,
    K.Key_AsciiTilde: 0x35, K.Key_Comma: 0x36, K.Key_Less: 0x36, K.Key_Period: 0x37,
    K.Key_Greater: 0x37, K.Key_Slash: 0x38, K.Key_Question: 0x38, K.Key_CapsLock: 0x39,
    K.Key_Print: 0x46, K.Key_ScrollLock: 0x47, K.Key_Pause: 0x48, K.Key_Insert: 0x49,
    K.Key_Home: 0x4A, K.Key_PageUp: 0x4B, K.Key_Delete: 0x4C, K.Key_End: 0x4D,
    K.Key_PageDown: 0x4E, K.Key_Right: 0x4F, K.Key_Left: 0x50, K.Key_Down: 0x51,
    K.Key_Up: 0x52, K.Key_Menu: 0x65,
    K.Key_Control: 0xE0, K.Key_Shift: 0xE1, K.Key_Alt: 0xE2, K.Key_Meta: 0xE3,
    K.Key_AltGr: 0xE6,
}
for _i in range(26):
    QT_TO_HID[K.Key_A + _i] = 0x04 + _i
for _i in range(1, 10):
    QT_TO_HID[K.Key_0 + _i] = 0x1D + _i
QT_TO_HID[K.Key_0] = 0x27
# shifted number row symbols
for _sym, _code in ((K.Key_Exclam, 0x1E), (K.Key_At, 0x1F), (K.Key_NumberSign, 0x20),
                    (K.Key_Dollar, 0x21), (K.Key_Percent, 0x22), (K.Key_AsciiCircum, 0x23),
                    (K.Key_Ampersand, 0x24), (K.Key_Asterisk, 0x25), (K.Key_ParenLeft, 0x26),
                    (K.Key_ParenRight, 0x27)):
    QT_TO_HID[_sym] = _code
for _i in range(12):
    QT_TO_HID[K.Key_F1 + _i] = 0x3A + _i

# On Windows the native virtual-key code tells left and right modifiers apart.
_VK_SIDE = {0xA0: 0xE1, 0xA1: 0xE5, 0xA2: 0xE0, 0xA3: 0xE4, 0xA4: 0xE2, 0xA5: 0xE6,
            0x5B: 0xE3, 0x5C: 0xE7}

HID_TO_KEYNAME = {
    0x29: "esc", 0x2A: "bksp", 0x2B: "tab", 0x2C: "space", 0x28: "enter", 0x39: "caps",
    0x2D: "minus", 0x2E: "plus", 0x2F: "lqu", 0x30: "rqu", 0x31: "bslash", 0x33: "sem",
    0x34: "quo", 0x35: "esc", 0x36: "comma", 0x37: "dot", 0x38: "qmark",
    0xE0: "lctrl", 0xE1: "lshift", 0xE2: "lalt", 0xE3: "win", 0xE4: "rctrl",
    0xE5: "rshift", 0xE6: "ralt", 0x65: "menu",
}
for _i in range(26):
    HID_TO_KEYNAME[0x04 + _i] = chr(97 + _i)
for _i in range(1, 10):
    HID_TO_KEYNAME[0x1D + _i] = f"n{_i}"
HID_TO_KEYNAME[0x27] = "n0"


def event_to_hid(ev) -> int:
    vk = ev.nativeVirtualKey()
    if vk in _VK_SIDE:
        return _VK_SIDE[vk]
    return QT_TO_HID.get(ev.key(), 0)
