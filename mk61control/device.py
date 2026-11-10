"""Low-level protocol for the GamaKay MK61.

All configuration goes through HID feature report 0x07 (264 bytes) on the
vendor interface (usage page 0xFF01, usage 0x0001):

    [0x07, command, arg1, arg2, 0, 0, 0, 0, payload (256 bytes)]

See PROTOCOL.md in the repository for the full command list.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field

from . import effects as fx
from .layout import MATRIX_LENGTH

try:
    import hid  # provided by the "hidapi" package
except ImportError:  # pragma: no cover - reported nicely by callers
    hid = None

REPORT_ID = 0x07
REPORT_LEN = 264
PAYLOAD = 8  # payload offset inside a report
CONFIG_USAGE_PAGE = 0xFF01

# Known USB IDs. 2442:0030 is the MK61 after the 2023 firmware (V3017);
# 1EA7:9018 is the original 2021 firmware.
KNOWN_DEVICES = {
    (0x2442, 0x0030): "MK61 (2023 firmware)",
    (0x1EA7, 0x9018): "MK61 / SK61L (2021 firmware)",
}

# Commands
CMD_SET_PROFILE = 0x01      # arg1 = profile 1..4, 0xFF = factory reset
CMD_WRITE_BLOCK = 0x02      # arg1 = profile, payload = 256-byte settings block
CMD_WRITE_KEYMAP = 0x03     # arg1 = profile, payload = normal / Fn / custom-LED layers (3 x 70)
CMD_WRITE_GAME_LEDS = 0x04  # arg1 = profile, payload = planar RGB x 70
CMD_WRITE_MACRO = 0x05      # arg1 = profile, arg2 = key slot (0..69 normal, 70..139 Fn)
CMD_ENABLE_EVENTS = 0x06
CMD_CUSTOM_COLOR = 0x08     # arg1 = profile, arg2 = custom slot, payload = planar RGB x 70
CMD_CUSTOM_FRAME = 0x09
CMD_CUSTOM_EFFECT = 0x0A
CMD_OPTIONS = 0x0B          # arg1 = profile, payload[3] = arrow swap, payload[5] = Win lock
CMD_READ_PROFILE = 0x81
CMD_READ_BLOCK = 0x82

# Settings block offsets
B_REPORT_RATE = 0
B_EFFECT = 3
B_BRIGHTNESS = 4
B_DIRECTION = 5
B_SPEED = 11          # inverted: 0 = fastest
B_SPECTRUM = range(24, 33)
B_CUSTOM_COUNT = 126  # changing this byte commits the block to flash
B_CUSTOM_CURRENT = 127
B_LED_STATUS = 128    # 1 = on, 2 = backlight off, 3 = all off

BRIGHTNESS_MAX = 5
DIRECTION_MAX = 3
SPEED_FW_MAX = 255


class MK61Error(RuntimeError):
    pass


def speed_to_fw(speed: int) -> int:
    """App speed 0..100 (100 = fastest) -> firmware byte (0 = fastest)."""
    s = max(0, min(100, int(speed)))
    return round(SPEED_FW_MAX * (100 - s) / 100)


def speed_from_fw(value: int) -> int:
    v = max(0, min(SPEED_FW_MAX, int(value)))
    return max(0, min(100, round(100 - 100 * v / SPEED_FW_MAX)))


@dataclass
class DeviceInfo:
    vid: int
    pid: int
    path: bytes
    product: str
    firmware: int  # USB bcdDevice, e.g. 0x3017

    @property
    def model(self) -> str:
        return KNOWN_DEVICES.get((self.vid, self.pid), "Unknown")

    @property
    def firmware_str(self) -> str:
        return f"V{self.firmware:04X}"


@dataclass
class Lighting:
    effect: int = 12
    brightness: int = BRIGHTNESS_MAX
    speed: int = 50           # 0..100, 100 = fastest
    direction: int = 0        # 0..3
    colors: list[tuple[int, int, int]] = field(default_factory=lambda: [(255, 255, 255)])
    led_on: bool = True

    @classmethod
    def from_block(cls, block: list[int]) -> "Lighting":
        eff = fx.BY_ID.get(block[B_EFFECT])
        colors = []
        if eff and eff.offset is not None:
            n, o = eff.colors, eff.offset
            colors = [(block[o + i], block[o + n + i], block[o + 2 * n + i]) for i in range(n)]
        return cls(
            effect=block[B_EFFECT],
            brightness=block[B_BRIGHTNESS],
            speed=speed_from_fw(block[B_SPEED]),
            direction=block[B_DIRECTION],
            colors=colors or [(255, 255, 255)],
            led_on=block[B_LED_STATUS] in (0, 1),
        )


def find_devices() -> list[DeviceInfo]:
    if hid is None:
        raise MK61Error("The 'hidapi' package is missing. Install it with: pip install hidapi")
    found = []
    for info in hid.enumerate():
        key = (info["vendor_id"], info["product_id"])
        if key in KNOWN_DEVICES and info.get("usage_page") == CONFIG_USAGE_PAGE:
            found.append(DeviceInfo(
                vid=key[0], pid=key[1], path=info["path"],
                product=info.get("product_string") or "",
                firmware=info.get("release_number") or 0,
            ))
    return found


class MK61:
    """An open connection to one keyboard."""

    def __init__(self, info: DeviceInfo | None = None):
        if info is None:
            devices = find_devices()
            if not devices:
                raise MK61Error("No MK61 keyboard found. Is it plugged in with the USB cable?")
            info = devices[0]
        self.info = info
        self._dev = hid.device()
        try:
            self._dev.open_path(info.path)
        except OSError as e:
            raise MK61Error(
                "Could not open the keyboard. Close the official GamaKay app if it is running."
            ) from e

    # -- context manager -------------------------------------------------
    def close(self):
        try:
            self._dev.close()
        except Exception:
            pass

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()

    # -- transport -------------------------------------------------------
    def _send(self, cmd: int, arg1: int = 0, arg2: int = 0, payload=None, wait: float = 0.06):
        buf = [0] * REPORT_LEN
        buf[0], buf[1], buf[2], buf[3] = REPORT_ID, cmd, arg1 & 0xFF, arg2 & 0xFF
        if payload is not None:
            for i, b in enumerate(list(payload)[:REPORT_LEN - PAYLOAD]):
                buf[PAYLOAD + i] = int(b) & 0xFF
        n = self._dev.send_feature_report(buf)
        if n is None or n < 0:
            raise MK61Error(f"Keyboard rejected command 0x{cmd:02X}")
        time.sleep(wait)
        return buf

    def _query(self, cmd: int, arg1: int = 0) -> list[int]:
        """Send a read command and return the 264-byte response (report ID at [0])."""
        last = None
        for attempt in range(1, 4):
            self._send(cmd, arg1, wait=0.03 * attempt)
            raw = list(self._dev.get_feature_report(REPORT_ID, REPORT_LEN))
            if raw and raw[0] != REPORT_ID:
                raw = [REPORT_ID] + raw
            raw += [0] * (REPORT_LEN - len(raw))
            # A valid answer echoes the report ID and the command.
            if raw[0] == REPORT_ID and raw[1] == cmd:
                return raw
            last = raw[:4]
            time.sleep(0.08 * attempt)
        raise MK61Error(f"Invalid response to 0x{cmd:02X}: {last}")

    # -- profiles --------------------------------------------------------
    def active_profile(self) -> int:
        """Active hardware profile, 1..4."""
        p = self._query(CMD_READ_PROFILE)[2]
        return p if 1 <= p <= 4 else 1

    def set_profile(self, profile: int):
        if not 1 <= profile <= 4:
            raise ValueError("profile must be 1..4")
        self._send(CMD_SET_PROFILE, profile, wait=0.15)

    def reload_lights(self, profile: int):
        """Switch away and back so the LED engine re-reads the block."""
        other = 2 if profile == 1 else 1
        self.set_profile(other)
        time.sleep(0.1)
        self.set_profile(profile)
        time.sleep(0.2)

    def factory_reset(self):
        """Restore all four profiles to factory settings."""
        self._send(CMD_SET_PROFILE, 0xFF, wait=2.0)

    # -- settings block --------------------------------------------------
    def read_block(self, profile: int) -> list[int]:
        return self._query(CMD_READ_BLOCK, profile)[PAYLOAD:PAYLOAD + 256]

    def write_block(self, profile: int, block: list[int]):
        if len(block) != 256:
            raise ValueError("block must be 256 bytes")
        self._send(CMD_WRITE_BLOCK, profile, payload=block, wait=0.08)

    def commit_block(self, profile: int, block: list[int], final_count: int = 255):
        """Write a block and make the keyboard save it to flash.

        The firmware commits the block to flash when the custom-count byte
        changes, so write it once with a different value, then with the
        value we want to keep.
        """
        block = list(block)
        block[B_CUSTOM_COUNT] = 1 if final_count != 1 else 255
        self.write_block(profile, block)
        block[B_CUSTOM_COUNT] = final_count
        self.write_block(profile, block)
        return block

    # -- lighting --------------------------------------------------------
    def read_lighting(self, profile: int) -> Lighting:
        return Lighting.from_block(self.read_block(profile))

    def write_lighting(self, profile: int, light: Lighting, verify: bool = True) -> list[int]:
        block = self.read_block(profile)
        block[B_EFFECT] = light.effect & 0xFF
        block[B_BRIGHTNESS] = max(0, min(BRIGHTNESS_MAX, int(light.brightness)))
        block[B_DIRECTION] = max(0, min(DIRECTION_MAX, int(light.direction)))
        if speed_from_fw(block[B_SPEED]) != int(light.speed):  # keep the exact byte if unchanged
            block[B_SPEED] = speed_to_fw(light.speed)
        block[B_LED_STATUS] = 1 if light.led_on else 2
        for i in B_SPECTRUM:  # non-zero flags can force the factory rainbow
            block[i] = 0
        eff = fx.BY_ID.get(light.effect)
        if eff and eff.offset is not None:
            n, o = eff.colors, eff.offset
            cols = list(light.colors) or [(255, 255, 255)]
            for j in range(n):
                r, g, b = cols[j % len(cols)]
                block[o + j], block[o + n + j], block[o + 2 * n + j] = r, g, b
        if light.effect == fx.CUSTOM:
            block[B_CUSTOM_CURRENT] = 0
            final = 1
        else:
            final = 255
        block = self.commit_block(profile, block, final_count=final)
        if verify:
            check = self.read_block(profile)
            for idx in (B_EFFECT, B_BRIGHTNESS, B_DIRECTION, B_SPEED, B_CUSTOM_COUNT):
                if check[idx] != block[idx]:
                    raise MK61Error(
                        f"Verification failed at byte {idx}: wrote {block[idx]}, read {check[idx]}")
        return block

    def write_per_key(self, profile: int, colors: dict[int, tuple[int, int, int]],
                      default=(0, 0, 0), brightness: int | None = None):
        """Static per-key colors (custom mode). `colors` maps matrix slot -> RGB."""
        n = MATRIX_LENGTH
        rgb = [0] * (n * 3)
        for slot in range(n):
            r, g, b = colors.get(slot, default)
            rgb[slot], rgb[n + slot], rgb[2 * n + slot] = r, g, b
        self._send(CMD_CUSTOM_COLOR, profile, 0, rgb, wait=0.2)

        frame = [0] * 256
        frame[0] = 1                      # one frame
        for slot in range(n):             # every key belongs to the frame
            frame[1 + slot // 8] |= 1 << (slot % 8)
        frame[182], frame[183] = 0, 0     # frame time
        self._send(CMD_CUSTOM_FRAME, profile, 0, frame, wait=0.2)

        effect = [0] * (n * 3)
        for slot in range(n):
            effect[slot] = 2              # 2 = static
        self._send(CMD_CUSTOM_EFFECT, profile, 0, effect, wait=0.25)

        cur = self.read_lighting(profile)
        cur.effect = fx.CUSTOM
        if brightness is not None:
            cur.brightness = brightness
        self.write_lighting(profile, cur)
        self.reload_lights(profile)

    # -- keys ------------------------------------------------------------
    def write_keymap(self, profile: int, normal: list[int], fn_layer: list[int]):
        """Write both key layers. There is no read-back command for the keymap."""
        if len(normal) != MATRIX_LENGTH or len(fn_layer) != MATRIX_LENGTH:
            raise ValueError("each layer must have 70 entries")
        payload = list(normal) + list(fn_layer) + [0] * MATRIX_LENGTH
        self._send(CMD_WRITE_KEYMAP, profile, 0, payload, wait=0.12)

    def write_macro(self, profile: int, slot: int, steps: list[tuple[int, bool, int]],
                    repeat: int = 1):
        """Store a macro for a matrix slot (add 70 for the Fn layer).

        `steps` is a list of (hid_code, key_down, delay_ms). The key itself must be
        set to keycodes.MACRO in the keymap.
        """
        if len(steps) > 84:
            raise ValueError("a macro can hold at most 84 steps")
        data = [0] * 256
        data[0], data[1] = (repeat >> 8) & 0xFF, repeat & 0xFF
        for i, (code, down, delay) in enumerate(steps):
            delay = max(20, min(0x7FFF, int(delay)))
            data[2 + i * 3] = ((delay >> 8) & 0x7F) | (0x80 if down else 0)
            data[3 + i * 3] = delay & 0xFF
            data[4 + i * 3] = code & 0xFF
        self._send(CMD_WRITE_MACRO, profile, slot, data, wait=0.2)

    def write_options(self, profile: int, arrow_swap: bool = False, win_lock: bool = False):
        payload = [0] * 8
        payload[3] = 1 if arrow_swap else 0
        payload[5] = 1 if win_lock else 0
        self._send(CMD_OPTIONS, profile, payload=payload, wait=0.1)

    # -- backup ----------------------------------------------------------
    def backup(self) -> dict:
        return {
            "device": f"{self.info.vid:04X}:{self.info.pid:04X}",
            "firmware": self.info.firmware_str,
            "active_profile": self.active_profile(),
            "blocks": {str(p): self.read_block(p) for p in (1, 2, 3, 4)},
        }

    def restore(self, data: dict):
        active = self.active_profile()
        for p in (1, 2, 3, 4):
            block = data["blocks"].get(str(p))
            if block and len(block) == 256:
                self.commit_block(p, block, final_count=block[B_CUSTOM_COUNT])
        self.reload_lights(int(data.get("active_profile", active)))
