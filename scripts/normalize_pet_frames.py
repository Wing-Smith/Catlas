"""Normalize Calico pet frames to a uniform 256x256 bottom-anchored canvas.

Character height is normalized per pose group so that the walk cycle and
state animations line up when the widget scales every frame to the same
pixel height. Run from the project root:

    .venv/Scripts/python.exe scripts/normalize_pet_frames.py
"""

from __future__ import annotations

import os
import sys

from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PET_DIR = os.path.join(ROOT, "app", "assets", "pet")
CANVAS = 256
BOTTOM_MARGIN = 6
MAX_W = CANVAS - 6

# Character height (px on the 256 canvas) per pose group.
HEIGHTS: dict[str, int] = {}
for _n in ("walk1", "walk2", "walk3", "walk4",
           "step1", "step2", "step3", "step4", "step5", "step6", "standup"):
    HEIGHTS[_n] = 200
HEIGHTS.update({
    "sitdown": 180,
    "crouch": 150,
    "sleep": 150,
    "stretch": 165,
    "pounce": 160,
})
for _n in ("idle", "blink", "look", "ear", "tail1", "tail2", "happy", "happy2"):
    HEIGHTS[_n] = 235


def normalize(name: str, target_h: int) -> tuple[int, int]:
    path = os.path.join(PET_DIR, f"pet_{name}.png")
    im = Image.open(path).convert("RGBA")

    # Trim to the opaque bounding box, ignoring faint alpha noise.
    alpha = im.getchannel("A").point(lambda a: 255 if a > 16 else 0)
    bbox = alpha.getbbox()
    if bbox is None:
        raise RuntimeError(f"{name}: fully transparent image")
    im = im.crop(bbox)

    # Scale so the character is `target_h` tall, but never wider than MAX_W.
    w, h = im.size
    scale = target_h / h
    if w * scale > MAX_W:
        scale = MAX_W / w
    new_w, new_h = max(1, round(w * scale)), max(1, round(h * scale))
    im = im.resize((new_w, new_h), Image.LANCZOS)

    canvas = Image.new("RGBA", (CANVAS, CANVAS), (0, 0, 0, 0))
    canvas.paste(im, ((CANVAS - new_w) // 2, CANVAS - new_h - BOTTOM_MARGIN), im)
    canvas.save(path)
    return new_w, new_h


def main() -> int:
    failed: list[str] = []
    for name, target_h in HEIGHTS.items():
        try:
            w, h = normalize(name, target_h)
            flag = " <- width-capped" if h != target_h else ""
            print(f"[OK] {name:8s} {w:3d}x{h:<3d} (target h={target_h}){flag}")
        except Exception as exc:  # noqa: BLE001
            failed.append(name)
            print(f"[FAIL] {name}: {exc}")
    if failed:
        print(f"failed frames: {', '.join(failed)}")
        return 1
    print(f"all {len(HEIGHTS)} frames normalized -> {PET_DIR}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
