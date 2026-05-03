"""Tests for image utilities."""

from __future__ import annotations

import base64
import io

import pytest
from PIL import Image

from freepik_tryon_bot.images import (
    HANGER_ASSETS,
    MANNEQUIN_ASSETS,
    build_outfit_collage,
    encode_b64,
    load_asset_bytes,
    to_jpeg_bytes,
)


def _png_bytes(size: tuple[int, int] = (200, 300), color: str = "red") -> bytes:
    im = Image.new("RGB", size, color)
    buf = io.BytesIO()
    im.save(buf, format="PNG")
    return buf.getvalue()


def test_to_jpeg_bytes_resizes_and_encodes() -> None:
    raw = _png_bytes((4000, 2000))
    out = to_jpeg_bytes(raw, max_side=512)
    with Image.open(io.BytesIO(out)) as im:
        assert im.format == "JPEG"
        assert max(im.size) <= 512


def test_encode_b64_roundtrip() -> None:
    s = encode_b64(b"hello world")
    assert base64.b64decode(s) == b"hello world"


def test_build_outfit_collage_one_image() -> None:
    raw = _png_bytes((300, 400), "blue")
    out = build_outfit_collage([raw])
    with Image.open(io.BytesIO(out)) as im:
        assert im.format == "JPEG"
        assert im.size[0] > 0
        assert im.size[1] > 0


def test_build_outfit_collage_five_images_within_limit() -> None:
    raws = [_png_bytes((300, 400), c) for c in ("red", "blue", "green", "yellow", "purple")]
    out = build_outfit_collage(raws)
    with Image.open(io.BytesIO(out)) as im:
        # Should fit within configured cap
        assert max(im.size) <= 2 * 1280


def test_build_outfit_collage_empty() -> None:
    with pytest.raises(ValueError):
        build_outfit_collage([])


def test_assets_present() -> None:
    for name in (*MANNEQUIN_ASSETS, *HANGER_ASSETS):
        data = load_asset_bytes(name)
        assert len(data) > 0
        with Image.open(io.BytesIO(data)) as im:
            assert im.format == "JPEG"
