# GamaKay MK61 configuration protocol

Notes for anyone who wants to write their own tool. Offsets were taken from the
official "MK Series" driver (`MK61Series.js`, March 2022) and checked against a
keyboard running the 2023 firmware **V3017** (`2442:0030`). The MK61-Studio project
documented the same protocol for the 2021 firmware (`1EA7:9018`); the layout is identical.

## USB

| | 2021 firmware | 2023 firmware (V3017) |
|---|---|---|
| VID:PID | `1EA7:9018` | `2442:0030` |
| Product string | `SK61L` | `USB APP` |
| bcdDevice | `0x7037` | `0x3017` |

The firmware version is the USB `bcdDevice` (`release_number` in hidapi).

Configuration uses **interface 2** (usage page `0xFF01`, usage `0x0001`). Every
message is a **feature report, ID `0x07`, 264 bytes**:

```
[0x07, command, arg1, arg2, 0, 0, 0, 0, payload[256]]
```

Read commands are a SET followed by a GET of report `0x07`; the answer echoes the
report ID and command at bytes 0 and 1. Check that before trusting a read: a read sent
too soon after a burst of writes can return stale data.

## Commands

| Cmd | Meaning | arg1 | arg2 | Payload |
|---|---|---|---|---|
| `0x01` | Activate profile | 1-4, `0xFF` = factory reset | | |
| `0x02` | Write settings block | profile | | 256-byte block |
| `0x03` | Write keymap | profile | 0 | normal layer (70) + Fn layer (70) + custom-LED map (70) |
| `0x04` | Game-mode key colors | profile | | planar RGB, 70 keys |
| `0x05` | Write macro | profile | key slot (0-69 normal, 70-139 Fn) | see below |
| `0x06` | Enable event reports | 1 | | |
| `0x07` | Live LED stream (software effects) | page | | |
| `0x08` | Custom-mode colors | profile | custom slot | planar RGB, 70 keys |
| `0x09` | Custom-mode frames | profile | custom slot | `[0]` frame count, `[1 + f*9 ..]` key bitmask, `[182 + f*2]` frame time (LE) |
| `0x0A` | Custom-mode key effects | profile | custom slot | 70 × effect (2 = static), 70 × speed, 70 × extra |
| `0x0B` | Options | profile | | `[3]` arrow swap, `[4]` 0, `[5]` Windows-key lock |
| `0x81` | Read active profile | | | answer byte 2 = profile |
| `0x82` | Read settings block | profile | | answer bytes 8-263 = block |

There is no command to read the keymap or macros back.

## Settings block (256 bytes)

| Offset | Meaning |
|---|---|
| 0 | report-rate index + 1 |
| 3 | effect: 0 wave, 1 breath, 2 rainbow cycle, 3 starlight, 4 encounter, 5 rain, 6 pulse, 7 cross, 8 trigger, 9 ripple, 10 blossom, 11 game mode, 12 static, 15 custom (per-key) |
| 4 | brightness, 0-5 on V3017 (factory value 5) |
| 5 | animation direction, 0-3 (the driver calls it "speed") |
| 11 | animation speed, inverted: 0 = fastest |
| 24-32 | "spectrum" flags; the driver clears them on every write, factory blocks use `1,1,1,0,1,1,1,0,0` |
| 33-125 | effect colors, planar R/G/B planes per effect (see below) |
| 126 | number of custom slots (`255` = none). **Changing this byte makes the keyboard save the block to flash.** |
| 127 | current custom slot |
| 128 | LED status: 1 on, 2 backlight off, 3 all off |

Color slots (offset, count): breath 33 (2), starlight 39 (1), encounter 42 (2), rain 48 (1),
pulse 51 (2), cross 57 (2), trigger 63 (2), ripple 69 (2), blossom 75 (2), static 81 (1),
wave 84 (14). For `n` colors at offset `o`: red = `o .. o+n-1`, green = `o+n ..`, blue = `o+2n ..`.

### Saving to flash

Writing a block with `0x02` changes the running settings. To make them survive a
power cycle, write the block twice: once with byte 126 set to something else, then
with the value you want to keep (`255` for normal effects, the slot count for custom mode).

## Key matrix

70 slots, 14 columns × 5 rows, column-major (`slot = column * 5 + row`). The slot
order and the factory maps are in `mk61control/layout.py`. Values are USB HID usage IDs,
plus these firmware codes:

| Code | Function | Code | Function |
|---|---|---|---|
| `0xAC` | Fn | `0xB2` | play this key's macro |
| `0xA5`-`0xAB` | media stop, prev, play, next, mute, vol+, vol- | `0xAD`-`0xB0` | profile 1-4 |
| `0xB1` | Windows-key lock | `0xB5` | NKRO / 6KRO toggle |
| `0xB7`-`0xBB` | mouse left, right, middle, back, forward | `0xD6` / `0xD7` | brightness + / - |
| `0xD9` | next effect | `0xDE` / `0xDF` | speed - / + |
| `0xF3` | Fn lock | `0xF8` | custom lighting |
| `0xF9` | backlight on/off | `0xFC` | next color |

## Macros (`0x05`)

```
[0] repeat count high, [1] repeat count low,
then up to 84 steps of 3 bytes: [delay_hi | 0x80 if key down, delay_lo, hid_code]
```

Delays below 20 ms are raised to 20 ms. Set the key to `0xB2` in the keymap so it plays the macro.

## Recovery

Holding **Fn + Tab for 5 seconds** resets the keyboard to factory settings, as does command
`0x01` with arg `0xFF`.
