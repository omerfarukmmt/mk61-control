"""Command-line interface: python -m mk61control <command>."""

from __future__ import annotations

import argparse
import json
import sys

from . import __version__, effects as fx, keycodes, store
from .device import MK61, MK61Error, find_devices, BRIGHTNESS_MAX
from .layout import KEY_INDEX, MATRIX_LENGTH


def parse_color(s: str) -> tuple[int, int, int]:
    s = s.strip().lstrip("#")
    if len(s) != 6:
        raise argparse.ArgumentTypeError(f"color must look like ff8800, got {s!r}")
    return tuple(int(s[i:i + 2], 16) for i in (0, 2, 4))


def parse_code(s: str) -> int:
    s = s.strip()
    if s.lower().startswith("0x"):
        return int(s, 16)
    for code, name in keycodes.NAMES.items():
        if name.lower() == s.lower():
            return code
    raise argparse.ArgumentTypeError(f"unknown key {s!r} (use a name like 'Esc' or a hex code)")


def _profile(kb: MK61, p: int | None) -> int:
    return p or kb.active_profile()


def cmd_list(a):
    devs = find_devices()
    if not devs:
        print("No MK61 found.")
    for d in devs:
        print(f"{d.vid:04X}:{d.pid:04X}  {d.model}  firmware {d.firmware_str}  {d.product}")


def cmd_info(a):
    with MK61() as kb:
        p = kb.active_profile()
        print(f"Model:    {kb.info.model} ({kb.info.vid:04X}:{kb.info.pid:04X})")
        print(f"Firmware: {kb.info.firmware_str}")
        print(f"Profile:  {p}")
        for q in (1, 2, 3, 4):
            L = kb.read_lighting(q)
            name = fx.BY_ID[L.effect].name if L.effect in fx.BY_ID else f"#{L.effect}"
            cols = " ".join(f"#{r:02x}{g:02x}{b:02x}" for r, g, b in L.colors[:4])
            mark = "*" if q == p else " "
            print(f" {mark}P{q}: {name:<18} brightness {L.brightness}  speed {L.speed}  "
                  f"direction {L.direction}  {cols}")


def cmd_dump(a):
    with MK61() as kb:
        print(json.dumps(kb.backup()))


def cmd_backup(a):
    with MK61() as kb:
        data = kb.backup()
    with open(a.file, "w", encoding="utf-8") as f:
        json.dump(data, f)
    print(f"Saved to {a.file}")


def cmd_restore(a):
    with open(a.file, encoding="utf-8") as f:
        data = json.load(f)
    with MK61() as kb:
        kb.restore(data)
    print("Restored.")


def cmd_profile(a):
    with MK61() as kb:
        kb.set_profile(a.number)
        print(f"Active profile: {kb.active_profile()}")


def cmd_light(a):
    with MK61() as kb:
        p = _profile(kb, a.profile)
        L = kb.read_lighting(p)
        if a.effect is not None:
            L.effect = fx.SLUGS[a.effect]
        if a.color:
            L.colors = a.color
        if a.brightness is not None:
            L.brightness = a.brightness
        if a.speed is not None:
            L.speed = a.speed
        if a.direction is not None:
            L.direction = a.direction
        if a.off:
            L.led_on = False
        if a.on:
            L.led_on = True
        kb.write_lighting(p, L)
        kb.reload_lights(p)
        print(f"Profile {p}: {fx.BY_ID.get(L.effect).name}, brightness {L.brightness}")


def cmd_perkey(a):
    colors = {}
    if a.file:
        with open(a.file, encoding="utf-8") as f:
            for key, hexcol in json.load(f).items():
                if key not in KEY_INDEX:
                    sys.exit(f"Unknown key name {key!r}")
                colors[KEY_INDEX[key]] = parse_color(hexcol)
    for spec in a.key or []:
        key, _, hexcol = spec.partition("=")
        if key not in KEY_INDEX:
            sys.exit(f"Unknown key name {key!r}")
        colors[KEY_INDEX[key]] = parse_color(hexcol)
    with MK61() as kb:
        p = _profile(kb, a.profile)
        kb.write_per_key(p, colors, default=a.base)
    print(f"Per-key colors written to profile {p}.")


def cmd_remap(a):
    data = store.load()
    with MK61() as kb:
        p = _profile(kb, a.profile)
        prof = data[str(p)]
        if a.reset:
            fresh = store.default_profile()
            prof["normal"], prof["fn"] = fresh["normal"], fresh["fn"]
        for spec in a.set or []:
            key, _, target = spec.partition("=")
            if key not in KEY_INDEX:
                sys.exit(f"Unknown key name {key!r}")
            layer = "fn" if a.fn else "normal"
            prof[layer][KEY_INDEX[key]] = parse_code(target)
        kb.write_keymap(p, prof["normal"], prof["fn"])
        store.save(data)
    print(f"Keymap written to profile {p}.")


def cmd_options(a):
    data = store.load()
    with MK61() as kb:
        p = _profile(kb, a.profile)
        prof = data[str(p)]
        if a.win_lock is not None:
            prof["win_lock"] = a.win_lock == "on"
        if a.arrow_swap is not None:
            prof["arrow_swap"] = a.arrow_swap == "on"
        kb.write_options(p, prof["arrow_swap"], prof["win_lock"])
        store.save(data)
    print("Options written.")


def cmd_reset(a):
    if not a.yes:
        sys.exit("This restores factory settings on all 4 profiles. Add --yes to confirm.")
    with MK61() as kb:
        kb.factory_reset()
        kb.reload_lights(1)
    print("Factory settings restored.")


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(prog="mk61control",
                                 description="Unofficial control tool for the GamaKay MK61")
    ap.add_argument("--version", action="version", version=__version__)
    sub = ap.add_subparsers(dest="cmd")

    sub.add_parser("gui", help="open the graphical app (default)")
    sub.add_parser("list", help="list connected keyboards").set_defaults(fn=cmd_list)
    sub.add_parser("info", help="show lighting of all profiles").set_defaults(fn=cmd_info)
    sub.add_parser("dump", help="print raw settings as JSON").set_defaults(fn=cmd_dump)

    s = sub.add_parser("backup", help="save all profile settings to a file")
    s.add_argument("file")
    s.set_defaults(fn=cmd_backup)
    s = sub.add_parser("restore", help="restore settings from a backup file")
    s.add_argument("file")
    s.set_defaults(fn=cmd_restore)

    s = sub.add_parser("profile", help="switch the active profile")
    s.add_argument("number", type=int, choices=[1, 2, 3, 4])
    s.set_defaults(fn=cmd_profile)

    s = sub.add_parser("light", help="change the lighting effect")
    s.add_argument("--profile", type=int, choices=[1, 2, 3, 4])
    s.add_argument("--effect", choices=[k for k in fx.SLUGS if k != "custom"])
    s.add_argument("--color", type=parse_color, nargs="+", help="one or more hex colors")
    s.add_argument("--brightness", type=int, choices=range(0, BRIGHTNESS_MAX + 1))
    s.add_argument("--speed", type=int, help="0..100")
    s.add_argument("--direction", type=int, choices=[0, 1, 2, 3])
    s.add_argument("--off", action="store_true", help="turn the backlight off")
    s.add_argument("--on", action="store_true", help="turn the backlight on")
    s.set_defaults(fn=cmd_light)

    s = sub.add_parser("perkey", help="static color per key")
    s.add_argument("--profile", type=int, choices=[1, 2, 3, 4])
    s.add_argument("--base", type=parse_color, default=(0, 0, 0), help="color for other keys")
    s.add_argument("--key", nargs="+", help="e.g. w=ff0000 a=ff0000")
    s.add_argument("--file", help="JSON file {key: hex}")
    s.set_defaults(fn=cmd_perkey)

    s = sub.add_parser("remap", help="change what a key does")
    s.add_argument("--profile", type=int, choices=[1, 2, 3, 4])
    s.add_argument("--fn", action="store_true", help="edit the Fn layer")
    s.add_argument("--set", nargs="+", help="e.g. caps=Esc menu=0x4C")
    s.add_argument("--reset", action="store_true", help="restore the factory keymap first")
    s.set_defaults(fn=cmd_remap)

    s = sub.add_parser("options", help="Windows-key lock and arrow swap")
    s.add_argument("--profile", type=int, choices=[1, 2, 3, 4])
    s.add_argument("--win-lock", choices=["on", "off"])
    s.add_argument("--arrow-swap", choices=["on", "off"])
    s.set_defaults(fn=cmd_options)

    s = sub.add_parser("factory-reset", help="restore factory settings")
    s.add_argument("--yes", action="store_true")
    s.set_defaults(fn=cmd_reset)
    return ap


def main(argv=None):
    ap = build_parser()
    a = ap.parse_args(argv)
    if a.cmd in (None, "gui"):
        from .gui.app import run
        return run()
    try:
        a.fn(a)
    except MK61Error as e:
        sys.exit(f"Error: {e}")


assert MATRIX_LENGTH == 70
