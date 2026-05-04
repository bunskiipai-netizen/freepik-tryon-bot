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
    crop_pair_to_aspect_ratio,
    crop_to_aspect_ratio,
    encode_b64,
    load_asset_bytes,
    mask_filename,
    parse_ratio,
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


def test_parse_ratio_valid() -> None:
    assert parse_ratio("1:1") == 1.0
    assert parse_ratio("16:9") == pytest.approx(16 / 9)
    assert parse_ratio("3:4") == 0.75


def test_parse_ratio_invalid() -> None:
    with pytest.raises(ValueError):
        parse_ratio("16-9")
    with pytest.raises(ValueError):
        parse_ratio("0:1")


@pytest.mark.parametrize("ratio", ["1:1", "3:4", "4:3", "16:9", "9:16"])
def test_crop_to_aspect_ratio_close_to_target(ratio: str) -> None:
    raw = _png_bytes((1000, 1500))  # 2:3 portrait
    out = crop_to_aspect_ratio(raw, ratio)
    with Image.open(io.BytesIO(out)) as im:
        target = parse_ratio(ratio)
        actual = im.size[0] / im.size[1]
        assert abs(actual - target) < 0.05, (
            f"ratio={ratio} expected~{target:.3f} got {actual:.3f}"
        )


def test_crop_to_aspect_ratio_already_matches() -> None:
    raw = _png_bytes((400, 400))  # 1:1
    out = crop_to_aspect_ratio(raw, "1:1")
    with Image.open(io.BytesIO(out)) as im:
        assert abs(im.size[0] / im.size[1] - 1.0) < 0.01


def test_mask_filename_helper() -> None:
    assert mask_filename("mannequin_1.jpg") == "mannequin_1_mask.png"
    assert mask_filename("hanger_2.jpg") == "hanger_2_mask.png"


def _png_mask_bytes(size: tuple[int, int]) -> bytes:
    im = Image.new("L", size, 255)
    buf = io.BytesIO()
    im.save(buf, format="PNG")
    return buf.getvalue()


@pytest.mark.parametrize("ratio", ["1:1", "3:4", "4:3", "16:9", "9:16"])
def test_crop_pair_to_aspect_ratio_keeps_alignment(ratio: str) -> None:
    img = _png_bytes((900, 1200))  # 3:4
    mask = _png_mask_bytes((900, 1200))
    img_out, mask_out = crop_pair_to_aspect_ratio(img, mask, ratio)
    with Image.open(io.BytesIO(img_out)) as im, Image.open(io.BytesIO(mask_out)) as mk:
        assert im.size == mk.size
        target = parse_ratio(ratio)
        actual = im.size[0] / im.size[1]
        assert abs(actual - target) < 0.05
        assert mk.mode == "L"


def test_crop_pair_resizes_mask_to_image_size() -> None:
    img = _png_bytes((600, 800))
    mask = _png_mask_bytes((300, 400))  # half-resolution mask
    img_out, mask_out = crop_pair_to_aspect_ratio(img, mask, "3:4")
    with Image.open(io.BytesIO(img_out)) as im, Image.open(io.BytesIO(mask_out)) as mk:
        assert im.size == mk.size


def test_bundled_masks_present() -> None:
    """Each master must ship with a matching mask of the same dimensions."""
    for name in (*MANNEQUIN_ASSETS, *HANGER_ASSETS):
        master = load_asset_bytes(name)
        mask = load_asset_bytes(mask_filename(name))
        with Image.open(io.BytesIO(master)) as im, Image.open(io.BytesIO(mask)) as mk:
            assert im.size == mk.size, f"{name} mask size mismatch: {im.size} vs {mk.size}"
