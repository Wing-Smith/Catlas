"""Offscreen smoke test for the Calico pet animation with v3 frames."""

import os
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PySide6.QtWidgets import QApplication

app = QApplication([])

from app.ui.pet_area import PetArea, _WALK_CYCLE, _WALK_FRAME_S  # noqa: E402
from app.ui.pet_area import _POUNCE, _STRETCH, _CROUCH  # noqa: E402

pet = PetArea()

# 1. All 24 frames loaded at a uniform canvas size.
sizes = {n: pm.size().toTuple() for n, pm in pet._frames.items()}
assert len(sizes) == 24, f"expected 24 frames, got {len(sizes)}"
assert len(set(sizes.values())) == 1, f"frame sizes differ: {set(sizes.values())}"
print(f"[OK] 24 frames, uniform size {next(iter(sizes.values()))}")

# 2. Walk cycle covers all 8 frames.
seen = set()
for i in range(8):
    t = i * _WALK_FRAME_S + 0.01
    seen.add(int(t / _WALK_FRAME_S) % 8)
assert seen == set(range(8)), f"walk cycle incomplete: {seen}"
assert len(_WALK_CYCLE) == 8
assert sorted(_WALK_CYCLE) == sorted(["step1", "step2", "walk3", "step3",
                                      "step4", "step5", "walk3", "step6"])
print("[OK] 8-frame walk cycle covers step1..step6 + walk3 x2")

# 3. Drive the state machine: pounce chain CROUCH -> POUNCE -> STRETCH.
pet._clock.restart()
pet._after = _POUNCE
pet._set_state(_CROUCH, 0.3)
assert pet._state == _CROUCH
for _ in range(400):
    pet._tick(1 / 60)
    if pet._state == _POUNCE:
        break
assert pet._state == _POUNCE, f"never reached POUNCE, stuck in {pet._state}"
for _ in range(1200):
    pet._tick(1 / 60)
    if pet._state == _STRETCH:
        break
assert pet._state == _STRETCH, f"never reached STRETCH, stuck in {pet._state}"
print("[OK] pounce chain CROUCH -> POUNCE -> STRETCH works")

# 4. Compose cross-fade produces a pixmap for a transition pair.
pm = pet._compose("step1", "step2", 0.45)
assert not pm.isNull()
print("[OK] cross-fade compose(step1, step2, 0.45) renders")

print("ALL PET SMOKE CHECKS PASSED")
