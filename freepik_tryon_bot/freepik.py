"""Async client untuk Freepik image generation / editing endpoints.

Supported endpoints:

- ``POST /v1/ai/text-to-image/seedream-v4-5-edit`` — image-to-image
  editing with up to 5 reference images. The model preserves subject
  details, lighting, and color tone of reference image #1 while editing
  according to the prompt + additional reference images. This is the
  workflow used by the bot to swap the outfit on a mannequin/hanger
  master while preserving the rest of the scene.
- ``POST /v1/ai/text-to-image/nano-banana-pro`` — text + reference image
  generation (legacy / kept for backward compatibility).
- ``POST /v1/ai/ideogram-image-edit`` — masked inpainting (legacy /
  kept for backward compatibility).

The client itself only knows about one API key per instance — rotation is
handled by the orchestration layer (`generator.py`) which leases a key from
:class:`freepik_tryon_bot.apikey_pool.APIKeyPool` per request.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

import httpx

logger = logging.getLogger(__name__)

API_BASE = "https://api.freepik.com"
NANO_BANANA_PRO_PATH = "/v1/ai/text-to-image/nano-banana-pro"
IDEOGRAM_EDIT_PATH = "/v1/ai/ideogram-image-edit"
SEEDREAM_EDIT_PATH = "/v1/ai/text-to-image/seedream-v4-5-edit"

TERMINAL_STATUSES = {"COMPLETED", "FAILED", "CANCELED", "CANCELLED", "ERROR"}
SUCCESS_STATUS = "COMPLETED"


class GenerationError(RuntimeError):
    """Raised when the upstream model returns an error or a task fails."""


class AuthError(GenerationError):
    """Invalid / unauthorized API key (401/403)."""


class QuotaError(GenerationError):
    """Quota exhausted or payment required (402/429 in some shapes)."""


class TransientError(GenerationError):
    """5xx / network-ish error worth retrying on a different key."""


@dataclass
class TaskResult:
    task_id: str
    status: str
    image_urls: list[str]
    raw_status: dict[str, Any]

    @property
    def primary_image(self) -> str | None:
        return self.image_urls[0] if self.image_urls else None


def _extract_image_urls(payload: dict[str, Any]) -> list[str]:
    """Pull image URLs out of a task-status payload, defensively."""
    data = payload.get("data") or {}
    candidates: list[Any] = []
    for key in ("generated", "images", "outputs", "result", "results"):
        value = data.get(key)
        if value is not None:
            candidates.append(value)
    urls: list[str] = []
    for value in candidates:
        if isinstance(value, str):
            urls.append(value)
        elif isinstance(value, list):
            for item in value:
                if isinstance(item, str):
                    urls.append(item)
                elif isinstance(item, dict):
                    for k in ("url", "image_url", "uri", "image"):
                        v = item.get(k)
                        if isinstance(v, str):
                            urls.append(v)
                            break
        elif isinstance(value, dict):
            for k in ("url", "image_url", "uri", "image"):
                v = value.get(k)
                if isinstance(v, str):
                    urls.append(v)
                    break
    return urls


def _extract_progress(payload: dict[str, Any]) -> float | None:
    data = payload.get("data") or {}
    for key in ("progress", "percent", "completion"):
        value = data.get(key)
        if isinstance(value, int | float):
            v = float(value)
            return v / 100.0 if v > 1 else v
    return None


def _extract_status(payload: dict[str, Any]) -> str:
    data = payload.get("data") or {}
    status = data.get("status")
    if isinstance(status, str):
        return status.upper()
    return "UNKNOWN"


def _classify_http_error(status_code: int, body_text: str) -> GenerationError:
    if status_code in (401, 403):
        return AuthError(f"API key ditolak (HTTP {status_code})")
    if status_code in (402, 429):
        return QuotaError(f"Kuota habis atau rate-limited (HTTP {status_code})")
    if 500 <= status_code < 600:
        return TransientError(f"Server upstream error (HTTP {status_code}): {body_text[:160]}")
    return GenerationError(f"HTTP {status_code}: {body_text[:240]}")


@dataclass(frozen=True)
class ReferenceImage:
    image_b64_or_url: str
    text: str | None = None
    mime_type: str | None = None

    def to_payload(self) -> dict[str, Any]:
        item: dict[str, Any] = {"image": self.image_b64_or_url}
        if self.text:
            item["text"] = self.text
        if self.mime_type:
            item["mime_type"] = self.mime_type
        return item


class FreepikImageClient:
    """Minimal async client for Nano Banana Pro image edit/generation."""

    def __init__(
        self,
        api_key: str,
        *,
        base_url: str = API_BASE,
        timeout: float = 60.0,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")
        self._owns_client = client is None
        self._client = client or httpx.AsyncClient(
            timeout=timeout,
            headers={"x-freepik-api-key": api_key},
        )

    async def __aenter__(self) -> FreepikImageClient:
        return self

    async def __aexit__(self, *exc: object) -> None:
        await self.aclose()

    async def aclose(self) -> None:
        if self._owns_client:
            await self._client.aclose()

    async def create_task(
        self,
        *,
        prompt: str,
        reference_images: list[ReferenceImage],
        aspect_ratio: str = "3:4",
        resolution: str = "2K",
    ) -> str:
        url = f"{self._base_url}{NANO_BANANA_PRO_PATH}"
        body: dict[str, Any] = {
            "prompt": prompt,
            "aspect_ratio": aspect_ratio,
            "resolution": resolution,
        }
        if reference_images:
            body["reference_images"] = [r.to_payload() for r in reference_images]
        try:
            resp = await self._client.post(url, json=body)
        except httpx.HTTPError as exc:
            raise TransientError(f"Network error: {exc}") from exc
        if resp.status_code >= 400:
            raise _classify_http_error(resp.status_code, resp.text)
        data = resp.json()
        task_id = (data.get("data") or {}).get("task_id")
        if not isinstance(task_id, str):
            raise GenerationError(f"Tidak ada task_id pada response: {data}")
        return task_id

    async def create_seedream_edit_task(
        self,
        *,
        prompt: str,
        reference_images_b64_or_url: list[str],
        aspect_ratio: str = "traditional_3_4",
        seed: int | None = None,
    ) -> str:
        """Submit a Seedream 4.5 image-edit task.

        ``reference_images_b64_or_url`` accepts either base64 strings or
        publicly accessible URLs (1-5 entries). The first entry is treated
        by the model as the master scene whose subject details, lighting,
        and color tone are preserved.
        """
        if not 1 <= len(reference_images_b64_or_url) <= 5:
            raise ValueError("Seedream edit requires 1-5 reference images")
        url = f"{self._base_url}{SEEDREAM_EDIT_PATH}"
        body: dict[str, Any] = {
            "prompt": prompt,
            "reference_images": list(reference_images_b64_or_url),
            "aspect_ratio": aspect_ratio,
        }
        if seed is not None:
            body["seed"] = int(seed)
        try:
            resp = await self._client.post(url, json=body)
        except httpx.HTTPError as exc:
            raise TransientError(f"Network error: {exc}") from exc
        if resp.status_code >= 400:
            raise _classify_http_error(resp.status_code, resp.text)
        data = resp.json()
        task_id = (data.get("data") or {}).get("task_id")
        if not isinstance(task_id, str):
            raise GenerationError(f"Tidak ada task_id pada response: {data}")
        return task_id

    async def create_inpaint_task(
        self,
        *,
        image_b64: str,
        mask_b64: str,
        prompt: str,
        style_reference_images_b64: list[str] | None = None,
        rendering_speed: str = "DEFAULT",
        magic_prompt: str = "OFF",
    ) -> str:
        """Submit a masked inpainting task to the Ideogram edit endpoint.

        ``image_b64`` is the base64-encoded master scene, ``mask_b64`` is
        the same-size mask where BLACK pixels mark regions to regenerate
        and WHITE pixels mark regions to preserve. The output retains the
        master's exact dimensions and composition; only the black region
        is repainted.
        """
        url = f"{self._base_url}{IDEOGRAM_EDIT_PATH}"
        body: dict[str, Any] = {
            "image": image_b64,
            "mask": mask_b64,
            "prompt": prompt,
            "rendering_speed": rendering_speed,
            "magic_prompt": magic_prompt,
        }
        if style_reference_images_b64:
            body["style_reference_images"] = list(style_reference_images_b64)
        try:
            resp = await self._client.post(url, json=body)
        except httpx.HTTPError as exc:
            raise TransientError(f"Network error: {exc}") from exc
        if resp.status_code >= 400:
            raise _classify_http_error(resp.status_code, resp.text)
        data = resp.json()
        task_id = (data.get("data") or {}).get("task_id")
        if not isinstance(task_id, str):
            raise GenerationError(f"Tidak ada task_id pada response: {data}")
        return task_id

    async def get_task(
        self, task_id: str, *, path: str = NANO_BANANA_PRO_PATH
    ) -> dict[str, Any]:
        url = f"{self._base_url}{path}/{task_id}"
        try:
            resp = await self._client.get(url)
        except httpx.HTTPError as exc:
            raise TransientError(f"Network error: {exc}") from exc
        if resp.status_code >= 400:
            raise _classify_http_error(resp.status_code, resp.text)
        return resp.json()

    async def wait_for_task(
        self,
        task_id: str,
        *,
        path: str = NANO_BANANA_PRO_PATH,
        poll_interval: float = 4.0,
        timeout: float = 600.0,  # noqa: ASYNC109 - upstream API exposes timeout knob
        on_progress: Callable[[str, float | None], Awaitable[None]] | None = None,
    ) -> TaskResult:
        loop = asyncio.get_event_loop()
        deadline = loop.time() + timeout
        while True:
            payload = await self.get_task(task_id, path=path)
            status = _extract_status(payload)
            progress = _extract_progress(payload)
            if on_progress is not None:
                try:
                    await on_progress(status, progress)
                except Exception:  # noqa: BLE001 - progress is best-effort
                    logger.debug("on_progress callback gagal", exc_info=True)
            if status in TERMINAL_STATUSES:
                if status != SUCCESS_STATUS:
                    raise GenerationError(f"Task {task_id} berakhir dengan status {status}")
                return TaskResult(
                    task_id=task_id,
                    status=status,
                    image_urls=_extract_image_urls(payload),
                    raw_status=payload,
                )
            if loop.time() >= deadline:
                raise TransientError(f"Timeout menunggu task {task_id} (>{timeout:.0f}s)")
            await asyncio.sleep(poll_interval)
