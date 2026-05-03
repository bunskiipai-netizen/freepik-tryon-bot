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
