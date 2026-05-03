"""Prompt templates used to drive the underlying generation model.

The bot uses Ideogram masked inpainting (image + mask + style reference)
where the mask itself locks the framing — only black mask regions are
regenerated, white regions are preserved pixel-accurately. So the prompts
here are short and focused on garment fidelity, not framing preservation.

Notes on language: prompts are in English because the generation model
responds best to English instructions. End-user-facing copy lives in
``bot.py`` and is in Indonesian.
"""

from __future__ import annotations

# ----- Mannequin Tryon ----------------------------------------------------

MANNEQUIN_PROMPT_CLOSEUP = (
    "Replace the masked region with a long modest woman's dress that exactly "
    "matches the colour, fabric pattern, weave, neckline, sleeve style, and "
    "drape of the style reference image. Show only the upper body to mid-"
    "thigh portion of the dress (the close-up region defined by the mask), "
    "with realistic folds and soft daylight. Include the mirror reflection "
    "of the dress on the left side, showing the back/side of the same "
    "garment. Keep the painted fabric inside the masked area only; do not "
    "alter anything outside the mask."
)

MANNEQUIN_PROMPT_FULLBODY = (
    "Replace the masked region with a long modest woman's dress that exactly "
    "matches the colour, fabric pattern, weave, neckline, sleeve style, and "
    "drape of the style reference image. Show the full-length dress hanging "
    "naturally on the mannequin from collar to floor, with realistic folds "
    "and soft daylight. Include the mirror reflection of the dress on the "
    "left side, showing the back of the same garment top to bottom. Keep "
    "the painted fabric inside the masked area only; do not alter anything "
    "outside the mask."
)

MANNEQUIN_PROMPTS: dict[str, str] = {
    "mannequin_1.jpg": MANNEQUIN_PROMPT_CLOSEUP,
    "mannequin_2.jpg": MANNEQUIN_PROMPT_FULLBODY,
}


def mannequin_prompt(asset_name: str) -> str:
    return MANNEQUIN_PROMPTS.get(asset_name, MANNEQUIN_PROMPT_FULLBODY)


# ----- Hanger -------------------------------------------------------------

_HANGER_BASE_WIDE = (
    "Replace the masked region with {count} long modest woman's "
    "dress{plural} hanging from the existing wooden hangers on the "
    "horizontal rack. Each dress must exactly match the colour, fabric "
    "pattern, weave, neckline, sleeve style, and drape shown in the style "
    "reference image. Render the full length of every dress from hanger to "
    "hem with realistic folds and soft natural daylight. {composition} "
    "Keep the painted fabric inside the masked area only; do not alter "
    "anything outside the mask."
)

_HANGER_BASE_CLOSEUP = (
    "Replace the masked region with the upper-torso portion of {count} "
    "long modest woman's dress{plural} hanging from the existing wooden "
    "hangers on the horizontal rack. Show only the collar, neckline, "
    "shoulders, button placket, and upper sleeves of each dress (the "
    "close-up region defined by the mask). Each dress must exactly match "
    "the colour, fabric pattern, weave, neckline, sleeve style, and drape "
    "shown in the style reference image. {composition} Keep the painted "
    "fabric inside the masked area only; do not alter anything outside "
    "the mask."
)


def _composition_clause(count: int) -> str:
    if count == 1:
        return (
            "There must be exactly ONE dress, hanging on the central hanger, "
            "horizontally centred within the masked area. The other hanger "
            "positions must remain empty."
        )
    if count == 2:
        return (
            "There must be exactly TWO dresses, hanging on the two central "
            "hangers with even spacing. They must be horizontally centred "
            "as a group within the masked area. Other hanger positions stay empty."
        )
    if count == 3:
        return (
            "There must be exactly THREE dresses, contiguous and horizontally "
            "centred as a group within the masked area, with even spacing "
            "between them. Other hanger positions stay empty."
        )
    if count == 4:
        return (
            "There must be exactly FOUR dresses, evenly spaced left-to-right "
            "across the masked area, occupying all four hanger positions."
        )
    return (
        "There must be exactly FIVE dresses, evenly spaced left-to-right "
        "across the masked area. If only four hangers are visible, add one "
        "additional matching wooden hanger so all five dresses fit symmetrically."
    )


def hanger_prompt(asset_name: str, count: int) -> str:
    plural = "es" if count != 1 else ""
    base = _HANGER_BASE_CLOSEUP if asset_name == "hanger_2.jpg" else _HANGER_BASE_WIDE
    return base.format(
        count=count,
        plural=plural,
        composition=_composition_clause(count),
    )


__all__ = [
    "MANNEQUIN_PROMPTS",
    "MANNEQUIN_PROMPT_CLOSEUP",
    "MANNEQUIN_PROMPT_FULLBODY",
    "hanger_prompt",
    "mannequin_prompt",
]
