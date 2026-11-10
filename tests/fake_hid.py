"""A fake MK61 for tests: answers feature reports like the real keyboard (V3017)."""
import copy

FACTORY = [0] * 256
for i, v in {0: 1, 4: 5, 11: 32, 12: 5, 13: 5, 14: 60, 15: 100, 16: 50, 17: 50, 18: 50, 19: 50,
             20: 30, 21: 30, 22: 30, 24: 1, 25: 1, 26: 1, 28: 1, 29: 1, 30: 1, 126: 255,
             127: 255, 128: 1}.items():
    FACTORY[i] = v
for i in (33, 36, 39, 40, 41, 42, 43, 44, 49, 51, 52, 53, 57, 58, 59, 63, 64, 65, 69, 70, 71,
          75, 76, 77, 81):
    FACTORY[i] = 255


class FakeKeyboard:
    def __init__(self):
        self.blocks = {p: list(FACTORY) for p in (1, 2, 3, 4)}
        self.blocks[1][3] = 12
        self.blocks[1][81:84] = [255, 80, 0]
        self.active = 1
        self.last = None
        self.log = []

    def handle(self, buf):
        cmd, a1 = buf[1], buf[2]
        self.log.append((cmd, a1, buf[3]))
        if cmd == 0x01:
            if a1 == 0xFF:
                self.blocks = {p: list(FACTORY) for p in (1, 2, 3, 4)}
                self.active = 1
            else:
                self.active = a1
            self.last = None
        elif cmd == 0x02:
            self.blocks[a1] = list(buf[8:264])
        elif cmd == 0x81:
            r = [0] * 264
            r[0], r[1], r[2] = 7, 0x81, self.active
            self.last = r
        elif cmd == 0x82:
            r = [0] * 264
            r[0], r[1], r[2] = 7, 0x82, a1
            r[8:264] = self.blocks[a1]
            self.last = r


KB = FakeKeyboard()


class device:
    def open_path(self, path):
        pass

    def close(self):
        pass

    def send_feature_report(self, buf):
        assert len(buf) == 264 and buf[0] == 7
        KB.handle(list(buf))
        return 264

    def get_feature_report(self, rid, n):
        return list(KB.last) if KB.last else [7, 0] + [0] * 262


def enumerate(vid=0, pid=0):
    return [{"vendor_id": 0x2442, "product_id": 0x0030, "usage_page": 0xFF01, "usage": 1,
             "path": b"fake", "product_string": "USB APP", "release_number": 0x3017,
             "interface_number": 2}]
