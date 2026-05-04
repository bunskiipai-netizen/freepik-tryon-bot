"""Prompt templates for the Seedream 4.5 Edit virtual try-on flow.

The bot sends two reference images per task to Seedream 4.5 Edit:

1. **Master scene** — a mannequin or hanger reference image. Seedream's
   "preserves subject details, lighting, and color tone" property keeps
   the room, mannequin/rack, lighting, framing, and colour grade intact.
2. **Source outfit** — a flat-lay or worn photo of the dress that should
   be transferred onto the master scene.

The prompts below describe the swap explicitly: copy the outfit from
reference 2 onto the subject in reference 1, preserving everything else.

End-user-facing copy lives in ``bot.py`` and is in Indonesian; the model
prompts here are in English because the upstream model responds best to
English instructions.
"""

from __future__ import annotations

# ----- Mannequin Tryon ----------------------------------------------------

MANNEQUIN_PROMPT_CLOSEUP = (
    "Image 1 is the master scene of a mannequin in a clothing display room "
    "(close-up framing showing the upper body to roughly mid-thigh). "
    "Image 2 is the source outfit. "
    "Replace ONLY the outfit currently on the mannequin in image 1 with the "
    "outfit from image 2, copying it exactly: same colour, same pattern, "
    "same fabric, same neckline, same cut, same length, same sleeve style. "
    "Preserve everything else from image 1: the mannequin form and pose, "
    "the head fixture, the standing mirror on the left, the side table and "
    "props on the right, the wood-paneled wall, the floor, the lighting, "
    "and the camera framing. "
    "The mirror reflection on the left must show the back/side of the new "
    "outfit consistently. "
    "Keep the same close-up shot type and subject-to-frame ratio as image 1 "
    "— do not zoom out, do not extend the frame downward to show feet."
)

MANNEQUIN_PROMPT_FULLBODY = (
    "Image 1 is the master scene of a mannequin in a clothing display room "
    "(full-body framing showing the entire mannequin from head fixture to "
    "the floor). "
    "Image 2 is the source outfit. "
    "Replace ONLY the outfit currently on the mannequin in image 1 with the "
    "outfit from image 2, copying it exactly: same colour, same pattern, "
    "same fabric, same neckline, same cut, same length, same sleeve style. "
    "Preserve everything else from image 1: the mannequin form and pose, "
    "the head fixture, the standing mirror on the left, the side table and "
    "props on the right, the wood-paneled wall, the floor, the lighting, "
    "and the full-body camera framing with the entire dress visible from "
    "collar to floor. "
    "The mirror reflection on the left must show the back of the full-"
    "length new outfit consistently."
)

MANNEQUIN_PROMPTS: dict[str, str] = {
    "mannequin_1.jpg": MANNEQUIN_PROMPT_CLOSEUP,
    "mannequin_2.jpg": MANNEQUIN_PROMPT_FULLBODY,
}


def mannequin_prompt(asset_name: str) -> str:
    """Return the Seedream prompt for a mannequin master image."""
    return MANNEQUIN_PROMPTS.get(asset_name, MANNEQUIN_PROMPT_FULLBODY)


# ----- Hanger -------------------------------------------------------------

_HANGER_BASE_WIDE = (
    "Image 1 is the master scene of clothing rack: a horizontal wooden pole "
    "near the top of the frame with wooden hangers, dresses hanging from "
    "those hangers, and a soft beige / warm peach wall behind. The framing "
    "is a wide shot showing the full length of the dresses from hanger to "
    "hem. "
    "Image{plural_ref} {ref_list} {provide_word} the source outfit{plural} "
    "to place on the rack. "
    "{composition} "
    "Preserve everything else from image 1: the wooden hangers, the rack "
    "pole, the wall colour and texture, the floor, the lighting, the "
    "shadows, and the wide camera framing showing complete dresses from "
    "hanger to hem. "
    "Each dress must be copied from its source reference exactly: same "
    "colour, same pattern, same fabric, same neckline, same cut, same "
    "length, same sleeve style. Do not blend, average, or recolour the "
    "outfits — each output dress must look identical to its source."
)

_HANGER_BASE_CLOSEUP = (
    "Image 1 is the master scene of a clothing rack — close-up framing "
    "showing only the upper torso portion of the dresses (collar, neckline, "
    "shoulders, button placket, upper sleeves) hanging from wooden hangers "
    "on a horizontal pole. Soft beige wall behind. The dress hems and "
    "lower bodies are NOT visible (cut off below). "
    "Image{plural_ref} {ref_list} {provide_word} the source outfit{plural} "
    "to place on the rack. "
    "{composition} "
    "Preserve everything else from image 1: the wooden hangers, the rack "
    "pole, the wall, the lighting, and the close-up camera framing — do "
    "NOT zoom out, do NOT extend the frame to show full dresses or hems. "
    "Each dress must be copied from its source reference exactly: same "
    "colour, same pattern, same fabric, same neckline, same sleeve style. "
    "Do not blend, average, or recolour the outfits — each output dress "
    "must look identical to its source."
)


def _composition_clause(count: int) -> str:
    """Describe how many dresses to render and how to centre them."""
    if count == 1:
        return (
            "There must be exactly ONE dress on the rack, hanging on the "
            "central hanger and horizontally centred in the frame. The "
            "other hanger positions must remain empty. The single dress "
            "must be a faithful copy of the source outfit (image 2)."
        )
    if count == 2:
        return (
            "There must be exactly TWO dresses on the rack, on the two "
            "central hangers with even spacing, horizontally centred as a "
            "group. Other hanger positions stay empty. The leftmost dress "
            "matches image 2, the next dress matches image 3."
        )
    if count == 3:
        return (
            "There must be exactly THREE dresses on the rack, contiguous "
            "and horizontally centred as a group with even spacing. Other "
            "hanger positions stay empty. Left-to-right: dress 1 matches "
            "image 2, dress 2 matches image 3, dress 3 matches image 4."
        )
    if count == 4:
        return (
            "There must be exactly FOUR dresses on the rack, evenly spaced "
            "left-to-right occupying all four hanger positions. Left-to-"
            "right: dress 1 matches image 2, dress 2 matches image 3, "
            "dress 3 matches image 4, dress 4 matches image 5."
        )
    return (
        "There must be exactly FIVE dresses on the rack, evenly spaced "
        "left-to-right. If only four hangers are visible in the master, "
        "add one matching wooden hanger so all five dresses fit "
        "symmetrically, still horizontally centred. Left-to-right the "
        "dresses are the source outfit references in upload order."
    )


def hanger_prompt(asset_name: str, count: int, *, single_outfit: bool = False) -> str:
    """Return the Seedream prompt for a hanger master image.

    ``single_outfit`` is True when the bot supplied exactly one outfit
    reference image (Seedream gets only 2 inputs total). All hangers
    should display copies of that single outfit. When False, the bot
    supplied one outfit per hanger position (image 2 = leftmost hanger,
    image 3 = next, etc.).
    """
    plural = "es" if count != 1 else ""
    base = _HANGER_BASE_CLOSEUP if asset_name == "hanger_2.jpg" else _HANGER_BASE_WIDE
    if single_outfit:
        plural_ref = ""
        ref_list = "Image 2"
        provide_word = "is"
        composition = _composition_clause_single(count)
    else:
        last_idx = count + 1  # because images are 1-indexed and ref starts at image 2
        if count == 1:
            plural_ref = ""
            ref_list = "Image 2"
        else:
            ref_list = ", ".join(f"image {i}" for i in range(2, last_idx + 1))
            plural_ref = "s"
        provide_word = "are" if count > 1 else "is"
        composition = _composition_clause(count)
    return base.format(
        plural_ref=plural_ref,
        ref_list=ref_list,
        provide_word=provide_word,
        plural=plural,
        composition=composition,
    )


def _composition_clause_single(count: int) -> str:
    """Composition clause when only ONE outfit reference covers all hangers."""
    if count == 1:
        return (
            "There must be exactly ONE dress on the rack, hanging on the "
            "central hanger and horizontally centred in the frame. The "
            "other hanger positions must remain empty. The dress must be a "
            "faithful copy of the source outfit (image 2)."
        )
    if count == 2:
        return (
            "There must be exactly TWO dresses on the rack, on the two "
            "central hangers with even spacing, horizontally centred as a "
            "group. Other hanger positions stay empty. BOTH dresses must "
            "be identical copies of the source outfit (image 2) — same "
            "colour, same pattern, same cut. Do not vary the colour or "
            "pattern between dresses."
        )
    if count == 3:
        return (
            "There must be exactly THREE identical dresses on the rack, "
            "contiguous and horizontally centred as a group with even "
            "spacing. Other hanger positions stay empty. ALL three dresses "
            "must be identical copies of the source outfit (image 2) — "
            "same colour, same pattern, same cut. Do not vary the colour "
            "or pattern between dresses."
        )
    if count == 4:
        return (
            "There must be exactly FOUR identical dresses on the rack, "
            "evenly spaced left-to-right occupying all four hanger "
            "positions. ALL four dresses must be identical copies of the "
            "source outfit (image 2) — same colour, same pattern, same "
            "cut. Do not vary the colour or pattern between dresses."
        )
    return (
        "There must be exactly FIVE identical dresses on the rack, evenly "
        "spaced left-to-right. If only four hangers are visible in the "
        "master, add one matching wooden hanger so all five dresses fit "
        "symmetrically, still horizontally centred. ALL five dresses must "
        "be identical copies of the source outfit (image 2) — same colour, "
        "same pattern, same cut. Do not vary the colour or pattern."
    )
