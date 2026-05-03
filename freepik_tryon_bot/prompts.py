"""Prompt templates used to drive the underlying generation model.

Notes on language: prompts are in English because the generation model
responds best to English instructions. End-user-facing copy lives in
``bot.py`` and is in Indonesian.
"""

from __future__ import annotations

MANNEQUIN_PROMPT = (
    "Editorial fashion photo. The first reference image is the MASTER "
    "scene: a dress form / mannequin shown in a specific styled "
    "environment (room, mirror behind or beside, wall, props, lighting). "
    "The second reference image is a flat-lay or product shot of a "
    "single garment.\n\n"
    "TASK: Treat the master scene as a pixel-accurate ground truth. "
    "Output an image that is IDENTICAL to the master scene except that "
    "the garment currently worn by the mannequin is replaced by the "
    "garment from the second reference. NOTHING else may be modified.\n\n"
    "STRICT PRESERVATION RULES — do not change ANY of these, not even "
    "subtly:\n"
    "- The mannequin itself: exact pose, exact height in frame, exact "
    "  head shape (or absence of head), neck shape, shoulders, arm "
    "  position, hand position, body proportions, material colour and "
    "  finish (matte vs glossy), seams, mounting pole/base.\n"
    "- The room and every prop: mirror (frame, glass tone, reflection "
    "  geometry), tall standing mirror, walls, paint colour, wood "
    "  paneling, floor texture, side tables, vases, plants, rugs, "
    "  ceiling, anything visible.\n"
    "- Lighting: direction, intensity, soft shadows, highlights, color "
    "  grade, white balance, ambient hue.\n"
    "- Camera composition: this is the most important constraint. The "
    "  camera angle, framing, perspective, focal length, and zoom level "
    "  MUST be byte-for-byte the same as the master scene. The CLOSE-UP "
    "  framing of the master scene must be preserved exactly: the "
    "  mannequin's silhouette must occupy the SAME pixel region, the "
    "  same crop on top/bottom/left/right, the same subject-to-frame "
    "  ratio. Do NOT zoom in or out, do NOT shift the mannequin within "
    "  the frame, do NOT recompose, do NOT tilt or rotate the camera, "
    "  do NOT add or remove negative space, do NOT change the aspect of "
    "  the master scene's framing. If the master scene is a close-up, "
    "  the result must be the same close-up.\n\n"
    "REFLECTION RULE: if the mannequin appears in a mirror within the "
    "master scene, the reflection in the result must show the BACK (or "
    "side, whichever the master mirror shows) of the new garment, "
    "consistent in color, pattern, and fabric with the new garment.\n\n"
    "GARMENT FIDELITY (only this changes): copy color, fabric, weave, "
    "prints, texture, length, neckline, sleeves, hemline, buttons, "
    "zippers, and any text/logo exactly from the second reference. "
    "Drape it realistically on the mannequin with natural folds and "
    "shadows consistent with the master scene's lighting.\n\n"
    "Do NOT add text, watermark, logo, or any element not present in "
    "the master scene. Do NOT remove anything that exists in the "
    "master scene other than the original garment that is being "
    "replaced."
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
