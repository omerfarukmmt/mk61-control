import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
sys.path.insert(0, os.path.dirname(__file__))
import fake_hid
import mk61control.device as dev
dev.hid = fake_hid
from mk61control.device import MK61, Lighting, speed_to_fw, speed_from_fw


def test_roundtrip():
    with MK61() as kb:
        assert kb.info.firmware_str == "V3017"
        assert kb.active_profile() == 1
        L = kb.read_lighting(1)
        assert L.effect == 12 and L.colors == [(255, 80, 0)]
        kb.write_lighting(2, Lighting(effect=0, brightness=4, speed=80, direction=2,
                                      colors=[(1, 2, 3)] * 14))
        b = kb.read_block(2)
        assert b[84] == 1 and b[98] == 2 and b[112] == 3 and b[126] == 255
        assert all(b[i] == 0 for i in range(24, 33))
        kb.write_per_key(3, {0: (9, 9, 9)})
        assert kb.read_block(3)[3] == 15 and kb.read_block(3)[126] == 1


def test_speed_mapping():
    for s in (0, 25, 50, 100):
        assert abs(speed_from_fw(speed_to_fw(s)) - s) <= 1


def test_backup_restore():
    with MK61() as kb:
        data = kb.backup()
        kb.write_lighting(4, Lighting(effect=1, colors=[(5, 5, 5), (6, 6, 6)]))
        kb.restore(data)
        assert kb.read_block(4) == data["blocks"]["4"]


if __name__ == "__main__":
    test_roundtrip(); test_speed_mapping(); test_backup_restore(); print("ok")


def test_unchanged_write_keeps_bytes():
    with MK61() as kb:
        before = kb.read_block(1)
        kb.write_lighting(1, kb.read_lighting(1))
        after = kb.read_block(1)
        assert [i for i in range(256) if before[i] != after[i] and i not in range(24, 33)] == []
