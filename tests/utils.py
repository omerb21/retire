import time, itertools
import random

_ctr = itertools.count()

def _checksum(d8: str) -> str:
    total = 0
    for i, ch in enumerate(d8, start=1):
        c = int(ch) * (1 if i % 2 == 1 else 2)
        if c > 9:
            c -= 9
        total += c
    return str((10 - (total % 10)) % 10)

def gen_valid_id() -> str:
    # בסיס בזמן + מונה כדי למנוע התנגשויות גם בריצות מהירות
    seed = int(time.time() * 1000) + next(_ctr)
    d8 = f"{seed % 100_000_000:08d}"
    return d8 + _checksum(d8)

def gen_reg_no() -> str:
    """Generate unique registration number to prevent collisions between tests"""
    return ''.join(str(random.randint(0, 9)) for _ in range(9))
