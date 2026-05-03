"""Prompt templates used to drive the underlying generation model.

Notes on language: prompts are in English because the generation model
responds best to English instructions. End-user-facing copy lives in
``bot.py`` and is in Indonesian.
"""

from __future__ import annotations

MANNEQUIN_PROMPT = (
    "Editorial fashion photo. The first reference image shows a dress form "
    "(mannequin) and a tall standing mirror behind it. The second reference "
    "image is a flat-lay or product shot of a single piece of women's clothing. "
    "Replace ONLY the garment currently worn by the mannequin with the "
    "garment shown in the second reference. Match the cut, color, fabric, "
    "pattern, length, sleeves, neckline, and any prints exactly. The garment "
    "reflected in the standing mirror behind the mannequin must show the "
    "BACK side of the same garment, fully consistent in color, pattern, and "
    "fabric. Keep the mannequin pose, mannequin material, hand position, "
    "the mirror, the room, the soft daylight, the white wall paneling, the "
    "side table with vase, and every other element of the scene completely "
    "unchanged. Do not change camera angle, framing, lighting, color grade, "
    "or background props. The result must look like the same scene with only "
    "the outfit swapped. Maintain photorealism, natural drape, realistic "
    "shadows, and consistent shading on the new garment. Keep the original "
    "image's aspect ratio."
)

HANGER_PROMPT_TEMPLATE = (
    "Editorial flat catalog photo of garments hanging on a clothing rack. "
    "The first reference image is the master scene: a horizontal wooden rack "
    "with multiple wooden hangers and warm beige background, soft daylight, "
    "and consistent color grading. The second reference image is a strip of "
    "{count} garment{plural} arranged left to right (numbered 1 to {count}). "
    "Replace the {count} garment{plural} hanging on the rack — left to right "
    "— with the {count} garment{plural} from the second reference image, "
    "preserving their left-to-right order so that garment 1 is on the "
    "left-most hanger, garment 2 on the next hanger, and so on. Keep the "
    "rack, hangers, wall color, lighting, soft shadows, camera angle, "
    "framing, and overall tone exactly the same as the master scene. Each "
    "garment must hang naturally on its hanger with realistic drape, the "
    "correct color, fabric, neckline, sleeves, length, buttons, and any "
    "prints copied accurately from the strip reference. {extra_garments}"
    "Do not add any text, watermark, or logo. Keep the original image's "
    "aspect ratio."
)

HANGER_EXTRA_TEMPLATE = (
    "If the master rack shows more hangers than provided garments, leave the "
    "extra hangers EMPTY (no garment hanging on them). If the master rack "
    "shows fewer hangers, add additional matching wooden hangers to fit all "
    "{count} provided garments. "
)


def hanger_prompt(count: int) -> str:
    plural = "s" if count != 1 else ""
    extra = HANGER_EXTRA_TEMPLATE.format(count=count) if count != 4 else ""
    return HANGER_PROMPT_TEMPLATE.format(
        count=count,
        plural=plural,
        extra_garments=extra,
    )
