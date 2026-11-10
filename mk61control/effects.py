"""Hardware lighting effects stored in the profile settings block."""

from dataclasses import dataclass


@dataclass(frozen=True)
class Effect:
    id: int
    name: str
    colors: int = 0          # number of color slots
    offset: int | None = None  # where the planar R/G/B color slots start in the block


EFFECTS = [
    Effect(0, "Wave", 14, 84),
    Effect(1, "Breath", 2, 33),
    Effect(2, "Rainbow cycle"),
    Effect(3, "Starlight", 1, 39),
    Effect(4, "Encounter", 2, 42),
    Effect(5, "Rain", 1, 48),
    Effect(6, "Pulse", 2, 51),
    Effect(7, "Cross", 2, 57),
    Effect(8, "Trigger", 2, 63),
    Effect(9, "Ripple", 2, 69),
    Effect(10, "Blossom", 2, 75),
    Effect(11, "Game mode (WASD)"),
    Effect(12, "Static", 1, 81),
    Effect(15, "Per-key (custom)"),
]

BY_ID = {e.id: e for e in EFFECTS}
CUSTOM = 15

# Short CLI names
SLUGS = {
    "wave": 0, "breath": 1, "cycle": 2, "starlight": 3, "encounter": 4, "rain": 5,
    "pulse": 6, "cross": 7, "trigger": 8, "ripple": 9, "blossom": 10, "game": 11,
    "static": 12, "custom": 15,
}
