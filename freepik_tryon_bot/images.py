"""Image utilities: load asset references, resize, base64 encode, build collages."""

from __future__ import annotations

import base64
import io
from importlib import resources
from pathlib import Path

from PIL import Image

ASSET_PACKAGE = "freepik_tryon_bot.assets"

MANNEQUIN_ASSETS: tuple[str, ...] = ("mannequin_1.jpg", "mannequin_2.jpg")
HANGER_ASSETS: tuple[str, ...] = ("hanger_1.jpg", "hanger_2.jpg")

# Per-master framing descriptors — fed into the prompt as part of
# Reference 1's annotation so the model knows exactly what crop/zoom of the
# scene to preserve. CRITICAL: keep these descriptions accurate to each
# bundled image, otherwise the model will drift.
MASTER_FRAMING: dict[str, str] = {
    "mannequin_1.jpg": (
        "TIGHT CLOSE-UP. The frame shows the mannequin's UPPER BODY ONLY: "
        "from the top of the headless mannequin form down to roughly mid-"
        "thigh / knee level. The mannequin's hands are visible but the "
        "feet, base, and floor are NOT visible. The standing mirror behind "
        "the mannequin is partially visible on the LEFT, showing the BACK "
        "of the garment from the same close-up region. A side table with "
        "pampas grass / dried plant in a vase is partially visible on the "
        "RIGHT. White wood-paneled wall behind. Soft daylight from upper "
        "right. The output MUST keep this exact close-up framing — do "
        "NOT extend the frame to show the floor, the mannequin's base, or "
        "the dress hem near the floor. Do NOT zoom out."
    ),
    "mannequin_2.jpg": (
        "WIDE FULL-BODY shot. The frame shows the entire mannequin from "
        "the top of the head fixture all the way down to the floor where "
        "the dress hem rests. Significant headroom above the mannequin. "
        "The standing mirror is fully visible on the LEFT, showing the "
        "BACK of the full-length garment. A round side table with a vase "
        "of dried plants is on the RIGHT. White wood-paneled wall behind. "
        "Soft daylight. The output MUST keep this full-body framing with "
        "the mannequin centered and the entire dress visible from collar "
        "to floor."
    ),
    "hanger_1.jpg": (
        "WIDE SHOT of a horizontal hanging rack. The frame shows the full "
        "length of FOUR dresses hanging from wooden hangers on a single "
        "horizontal pole at the TOP of the frame. The dresses extend "
        "vertically from the hangers down to roughly the bottom of the "
        "frame. Soft beige / warm peach wall behind, with a faint plant-"
        "leaf shadow on the LEFT wall from natural sunlight upper-left. "
        "Significant negative space on the LEFT side of the rack and "
        "smaller negative space on the right. The output MUST keep this "
        "wide framing showing complete dresses from hanger to hem."
    ),
    "hanger_2.jpg": (
        "TIGHT CLOSE-UP of dresses hanging on a rack. The frame shows "
        "only the UPPER TORSO portion of FOUR dresses (collar, button "
        "placket, upper sleeves, top of the bodice) — roughly the top "
        "third of each dress. The wooden hangers and the white horizontal "
        "rack pole are visible at the very top. The dress hems and "
        "lower bodies are NOT visible (cut off below). Soft beige wall "
        "behind. The output MUST keep this exact close-up framing — do "
        "NOT extend the frame downward to show full dresses, do NOT zoom "
        "out, do NOT show the floor or full hems."
    ),
}

MAX_REFERENCE_SIDE = 1280
COLLAGE_TARGET_HEIGHT = 1024
COLLAGE_BG = (250, 248, 244)


def load_asset_bytes(name: str) -> bytes:
    """Read one of the bundled reference JPGs as raw bytes."""
    return resources.files(ASSET_PACKAGE).joinpath(name).read_bytes()


def asset_path(name: str) -> Path:
    """Filesystem path of a bundled asset (for local debugging only)."""
    return Path(str(resources.files(ASSET_PACKAGE).joinpath(name)))


def to_jpeg_bytes(data: bytes, *, max_side: int = MAX_REFERENCE_SIDE, quality: int = 90) -> bytes:
    """Decode ``data``, resize so the longer side <= ``max_side``, re-encode JPEG."""
    with Image.open(io.BytesIO(data)) as im:
        im = im.convert("RGB")
        im.thumbnail((max_side, max_side), Image.LANCZOS)
        buf = io.BytesIO()
        im.save(buf, format="JPEG", quality=quality, optimize=True)
        return buf.getvalue()


def encode_b64(data: bytes) -> str:
    """Base64-encode raw bytes for inline reference image use."""
    return base64.b64encode(data).decode("ascii")


def parse_ratio(ratio: str) -> float:
    """Parse a ratio string like '16:9' or '3:4' into a float."""
    parts = ratio.split(":")
    if len(parts) != 2:
        raise ValueError(f"Invalid ratio: {ratio!r}")
    a, b = (int(p.strip()) for p in parts)
    if a <= 0 or b <= 0:
        raise ValueError(f"Invalid ratio: {ratio!r}")
    return a / b


def crop_to_aspect_ratio(
    data: bytes,
    ratio: str,
    *,
    max_side: int = MAX_REFERENCE_SIDE,
    quality: int = 92,
) -> bytes:
    """Center-crop ``data`` to the requested aspect ratio, then resize+JPEG.

    This keeps the original image's framing (zoom level on the subject) but
    forces the canvas shape to match the selected output ratio so the
    generation model sees a master in the same shape as the requested output.
    """
    target = parse_ratio(ratio)
    with Image.open(io.BytesIO(data)) as im:
        im = im.convert("RGB")
        w, h = im.size
        current = w / h
        if abs(current - target) >= 0.005:
            if current > target:
                # too wide -> trim sides
                new_w = max(1, int(round(h * target)))
                x0 = (w - new_w) // 2
                im = im.crop((x0, 0, x0 + new_w, h))
            else:
                # too tall -> trim top/bottom
                new_h = max(1, int(round(w / target)))
                y0 = (h - new_h) // 2
                im = im.crop((0, y0, w, y0 + new_h))
        im.thumbnail((max_side, max_side), Image.LANCZOS)
        buf = io.BytesIO()
        im.save(buf, format="JPEG", quality=quality, optimize=True)
        return buf.getvalue()


def build_outfit_collage(
    outfits: list[bytes],
    *,
    target_height: int = COLLAGE_TARGET_HEIGHT,
    background: tuple[int, int, int] = COLLAGE_BG,
) -> bytes:
    """Stitch up to 5 outfit photos into one horizontal strip.

    Reference images are capped at 3 by the upstream model, so when the user
    uploads 2-5 outfits we collapse them into a single strip and let the
    prompt describe the left-to-right ordering.
    """
    if not outfits:
        raise ValueError("Minimal 1 foto outfit")
    images: list[Image.Image] = []
    for raw in outfits:
        im = Image.open(io.BytesIO(raw)).convert("RGB")
        ratio = target_height / im.height
        new_w = max(1, int(im.width * ratio))
        images.append(im.resize((new_w, target_height), Image.LANCZOS))

    gap = 16
    total_w = sum(im.width for im in images) + gap * (len(images) - 1)
    canvas = Image.new("RGB", (total_w, target_height), background)
    x = 0
    for im in images:
        canvas.paste(im, (x, 0))
        x += im.width + gap

    if canvas.width > MAX_REFERENCE_SIDE * 2:
        scale = (MAX_REFERENCE_SIDE * 2) / canvas.width
        canvas = canvas.resize(
            (int(canvas.width * scale), int(canvas.height * scale)), Image.LANCZOS
        )

    buf = io.BytesIO()
    canvas.save(buf, format="JPEG", quality=90, optimize=True)
    return buf.getvalue()
