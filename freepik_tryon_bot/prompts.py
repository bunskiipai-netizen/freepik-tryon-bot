"""Prompt templates used to drive the underlying generation model.

Notes on language: prompts are in English because the generation model
responds best to English instructions. End-user-facing copy lives in
``bot.py`` and is in Indonesian.
"""

from __future__ import annotations

MANNEQUIN_PROMPT = (
    "Editorial fashion photo. The first reference image is the MASTER scene: "
    "a dress form (mannequin) standing in a styled room with a tall mirror "
    "behind/beside it. The second reference image is a flat-lay or product "
    "shot of a single garment.\n\n"
    "TASK: Replace ONLY the garment currently on the mannequin with the "
    "garment from the second reference. Keep absolutely everything else "
    "from the master scene IDENTICAL.\n\n"
    "Strict preservation rules (do not change ANY of these):\n"
    "- The mannequin itself: pose, height, head/no-head, neck shape, "
    "  shoulders, arm position, hand position, material colour and finish.\n"
    "- The mirror, the room, the wall paint, the wood paneling, the floor, "
    "  the side table, the vase, any props.\n"
    "- The lighting direction, soft shadows, color grading, white balance.\n"
    "- The camera angle, framing, perspective, focal length, and zoom level. "
    "  Do not crop, tilt, rotate, or zoom in or out.\n\n"
    "Reflection rule: the garment reflected in the mirror must show the BACK "
    "side of the same garment, fully consistent in color, pattern, and "
    "fabric. If the mirror reflects only the back, replace that reflection "
    "to match the new garment's back accordingly.\n\n"
    "Garment fidelity: copy color, fabric, weave, prints, texture, length, "
    "neckline, sleeves, hemline, buttons, zippers, and any text/logo "
    "exactly from the second reference. Drape it realistically on the "
    "mannequin with natural folds and shadows.\n\n"
    "Do not add text, watermark, logo, or any element not present in the "
    "master scene."
)

HANGER_PROMPT_TEMPLATE = (
    "Editorial flat catalog photo of garments hanging on a clothing rack.\n\n"
    "Reference image 1 is the MASTER scene. You MUST preserve the master "
    "scene EXACTLY:\n"
    "- The hanging rack itself (the horizontal pole/bar, its material, "
    "  color, texture, mounting hardware) must stay identical — same "
    "  position in the frame, same length, same height.\n"
    "- The hangers themselves stay identical in shape, material, and color "
    "  (only the garment hanging from each hanger changes).\n"
    "- The wall, floor, room, wall colour/texture, lighting, soft shadows, "
    "  color grade, white balance, and any props must stay identical.\n"
    "- The camera angle, framing, perspective, focal length, and zoom "
    "  level must stay identical. Do NOT crop, tilt, rotate, recompose, "
    "  zoom, or shift the rack within the frame.\n"
    "- Do NOT add, remove, or move any element of the rack, hooks, "
    "  hangers (only the cloth on each hanger changes), or background.\n\n"
    "Reference image 2 is a HORIZONTAL STRIP of {count} garment{plural} "
    "numbered 1 to {count} from left to right.\n\n"
    "TASK: Hang exactly {count} garment{plural} on the rack, using the "
    "{count} garment{plural} from the strip in the same left-to-right "
    "order — strip-garment 1 on the leftmost hanger of the chosen "
    "centred group, strip-garment 2 next, and so on.\n\n"
    "Composition rules (CRITICAL):\n"
    "- The {count} garment{plural} must be CENTERED as a group on the "
    "  rack, with even horizontal spacing between adjacent garments, "
    "  regardless of count. Never align flush-left or flush-right. The "
    "  horizontal midpoint of the row of garments must coincide with the "
    "  horizontal midpoint of the rack.\n"
    "- {extra_garments}\n"
    "- Each garment hangs naturally from a hanger with realistic drape, "
    "  full length visible, no overlap with adjacent garments.\n\n"
    "Garment fidelity: copy color, fabric, weave, prints, texture, "
    "length, neckline, sleeves, hemline, buttons, zippers, and any "
    "text/logo exactly from the strip reference.\n\n"
    "Do NOT add text, watermark, logo, extra props, or any element not "
    "present in the master scene."
)


def hanger_prompt(count: int) -> str:
    plural = "s" if count != 1 else ""
    if count == 1:
        extra = (
            "Since there is only one garment, hang it on the single "
            "hanger that is exactly at the horizontal centre of the rack. "
            "All other hangers on the rack must remain empty (no garment "
            "hanging on them)."
        )
    elif count < 4:
        extra = (
            f"Use {count} hangers placed contiguously and centred on "
            "the rack, with even spacing. Any remaining hangers on the "
            "rack must remain empty (no garment hanging on them)."
        )
    elif count == 4:
        extra = (
            "Use 4 hangers placed contiguously and centred on the rack "
            "with even spacing. Any remaining hangers stay empty."
        )
    else:  # 5
        extra = (
            "Use 5 hangers placed contiguously and centred on the rack "
            "with even spacing. If the master scene shows fewer than 5 "
            "hangers, add additional hangers that exactly match the "
            "existing hangers' shape, material, and colour to fit all "
            "5 garments. Maintain symmetric centred composition."
        )
    return HANGER_PROMPT_TEMPLATE.format(
        count=count,
        plural=plural,
        extra_garments=extra,
    )


__all__ = ["MANNEQUIN_PROMPT", "HANGER_PROMPT_TEMPLATE", "hanger_prompt"]
