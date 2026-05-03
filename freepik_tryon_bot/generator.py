"""Orchestration: spawn the two Nano Banana Pro tasks (one per main image),
poll them in parallel, surface aggregated progress, and return the URLs.

This layer also owns API-key rotation: each task picks a key from the pool
and re-leases on auth/quota errors.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass

import httpx

from .apikey_pool import APIKeyPool
from .freepik import (
    IDEOGRAM_EDIT_PATH,
    AuthError,
    FreepikImageClient,
    GenerationError,
    QuotaError,
    ReferenceImage,
    TaskResult,
    TransientError,
)

logger = logging.getLogger(__name__)

ProgressCb = Callable[[float, str], Awaitable[None]]


@dataclass
class GenerationResult:
    image_urls: list[str]
    task_ids: list[str]


@dataclass(frozen=True)
class InpaintTaskInput:
    """One per output image: master + mask + per-task prompt + style refs."""

    image_b64: str
    mask_b64: str
    prompt: str
    style_reference_images_b64: list[str] | None = None


@dataclass
class _TaskProgress:
    pct: float = 0.0
    status: str = "PENDING"
    done: bool = False
    image_url: str | None = None


_PROGRESS_BY_STATUS = {
    "PENDING": 0.05,
    "CREATED": 0.10,
    "QUEUED": 0.15,
    "IN_PROGRESS": 0.50,
    "RUNNING": 0.50,
    "PROCESSING": 0.50,
    "COMPLETED": 1.0,
}


class Generator:
    """High-level: run N parallel Nano Banana Pro tasks with key rotation."""

    def __init__(
        self,
        pool: APIKeyPool,
        *,
        poll_interval: float = 4.0,
        poll_timeout: float = 600.0,
        progress_min_interval: float = 2.0,
        max_attempts_per_task: int = 4,
    ) -> None:
        self._pool = pool
        self._poll_interval = poll_interval
        self._poll_timeout = poll_timeout
        self._progress_min_interval = progress_min_interval
        self._max_attempts = max_attempts_per_task

    async def run_batch(
        self,
        *,
        prompt: str,
        reference_groups: list[list[ReferenceImage]],
        aspect_ratio: str,
        resolution: str,
        on_progress: ProgressCb | None = None,
    ) -> GenerationResult:
        """Run one task per reference group in parallel.

        ``reference_groups[i]`` is the list of reference images sent to task i.
        Returns image URLs in the same order as ``reference_groups``. If any
        task fails after retries, raises :class:`GenerationError`.
        """
        n = len(reference_groups)
        progresses = [_TaskProgress() for _ in range(n)]

        progress_lock = asyncio.Lock()
        last_emitted_pct = -1.0

        async def report() -> None:
            nonlocal last_emitted_pct
            if on_progress is None:
                return
            async with progress_lock:
                avg = sum(p.pct for p in progresses) / n
                pct = min(0.99, avg) if not all(p.done for p in progresses) else 1.0
                # avoid spamming Telegram edit-message — only emit on noticeable change
                if abs(pct - last_emitted_pct) < 0.04 and pct < 1.0:
                    return
                last_emitted_pct = pct
                status_summary = ", ".join(
                    f"#{i + 1}:{p.status[:3]}" for i, p in enumerate(progresses)
                )
                try:
                    await on_progress(pct, status_summary)
                except Exception:  # noqa: BLE001 - never let UI errors break generation
                    logger.debug("on_progress callback gagal", exc_info=True)

        async def run_one(idx: int) -> None:
            refs = reference_groups[idx]
            attempt = 0
            last_exc: Exception | None = None
            while attempt < self._max_attempts:
                attempt += 1
                key = self._pool.lease()
                if key is None:
                    raise GenerationError(
                        "Semua API key habis/ditolak. Hubungi admin untuk update key."
                    )
                try:
                    async with httpx.AsyncClient(
                        timeout=60.0,
                        headers={"x-freepik-api-key": key},
                    ) as http:
                        client = FreepikImageClient(api_key=key, client=http)
                        task_id = await client.create_task(
                            prompt=prompt,
                            reference_images=refs,
                            aspect_ratio=aspect_ratio,
                            resolution=resolution,
                        )
                        progresses[idx].status = "CREATED"
                        progresses[idx].pct = max(progresses[idx].pct, 0.10)
                        await report()

                        async def cb(status: str, p: float | None) -> None:
                            progresses[idx].status = status
                            base = _PROGRESS_BY_STATUS.get(status, 0.4)
                            if p is not None:
                                # Smooth: model progress field 0..1 used directly
                                progresses[idx].pct = max(progresses[idx].pct, p)
                            else:
                                progresses[idx].pct = max(progresses[idx].pct, base)
                            await report()

                        result: TaskResult = await client.wait_for_task(
                            task_id,
                            poll_interval=self._poll_interval,
                            timeout=self._poll_timeout,
                            on_progress=cb,
                        )
                        url = result.primary_image
                        if not url:
                            raise GenerationError(
                                f"Task {task_id} sukses tapi tidak ada URL gambar"
                            )
                        progresses[idx].pct = 1.0
                        progresses[idx].status = "COMPLETED"
                        progresses[idx].done = True
                        progresses[idx].image_url = url
                        self._pool.report_success(key)
                        await report()
                        return
                except AuthError as exc:
                    self._pool.report_failure(key, permanent=True)
                    last_exc = exc
                    logger.warning("Task #%d gagal auth, rotasi key. %s", idx + 1, exc)
                    continue
                except QuotaError as exc:
                    self._pool.report_failure(key, permanent=False, cooldown_seconds=120.0)
                    last_exc = exc
                    logger.warning("Task #%d kuota/rate limit, rotasi key. %s", idx + 1, exc)
                    continue
                except TransientError as exc:
                    self._pool.report_failure(key, permanent=False, cooldown_seconds=10.0)
                    last_exc = exc
                    logger.warning("Task #%d transient error, retry. %s", idx + 1, exc)
                    await asyncio.sleep(min(2.0 * attempt, 8.0))
                    continue
                except GenerationError as exc:
                    last_exc = exc
                    logger.warning("Task #%d generation error: %s", idx + 1, exc)
                    break
            raise last_exc or GenerationError(f"Task #{idx + 1} gagal tanpa exception")

        await asyncio.gather(*(run_one(i) for i in range(n)))

        urls = [p.image_url for p in progresses if p.image_url]
        return GenerationResult(image_urls=urls, task_ids=[])

    async def run_inpaint_batch(
        self,
        *,
        tasks: list[InpaintTaskInput],
        on_progress: ProgressCb | None = None,
    ) -> GenerationResult:
        """Run one Ideogram inpainting task per ``tasks`` entry, in parallel.

        Each entry produces exactly one output image of the same dimensions
        as its input master + mask. The same key-rotation / retry logic as
        :py:meth:`run_batch` applies (auth -> blacklist, quota -> cooldown,
        transient -> retry on a different key).
        """
        n = len(tasks)
        progresses = [_TaskProgress() for _ in range(n)]
        progress_lock = asyncio.Lock()
        last_emitted_pct = -1.0

        async def report() -> None:
            nonlocal last_emitted_pct
            if on_progress is None:
                return
            async with progress_lock:
                avg = sum(p.pct for p in progresses) / n
                pct = min(0.99, avg) if not all(p.done for p in progresses) else 1.0
                if abs(pct - last_emitted_pct) < 0.04 and pct < 1.0:
                    return
                last_emitted_pct = pct
                status_summary = ", ".join(
                    f"#{i + 1}:{p.status[:3]}" for i, p in enumerate(progresses)
                )
                try:
                    await on_progress(pct, status_summary)
                except Exception:  # noqa: BLE001
                    logger.debug("on_progress callback gagal", exc_info=True)

        async def run_one(idx: int) -> None:
            task = tasks[idx]
            attempt = 0
            last_exc: Exception | None = None
            while attempt < self._max_attempts:
                attempt += 1
                key = self._pool.lease()
                if key is None:
                    raise GenerationError(
                        "Semua API key habis/ditolak. Hubungi admin untuk update key."
                    )
                try:
                    async with httpx.AsyncClient(
                        timeout=120.0,
                        headers={"x-freepik-api-key": key},
                    ) as http:
                        client = FreepikImageClient(api_key=key, client=http)
                        task_id = await client.create_inpaint_task(
                            image_b64=task.image_b64,
                            mask_b64=task.mask_b64,
                            prompt=task.prompt,
                            style_reference_images_b64=task.style_reference_images_b64,
                        )
                        progresses[idx].status = "CREATED"
                        progresses[idx].pct = max(progresses[idx].pct, 0.10)
                        await report()

                        async def cb(status: str, p: float | None) -> None:
                            progresses[idx].status = status
                            base = _PROGRESS_BY_STATUS.get(status, 0.4)
                            if p is not None:
                                progresses[idx].pct = max(progresses[idx].pct, p)
                            else:
                                progresses[idx].pct = max(progresses[idx].pct, base)
                            await report()

                        result: TaskResult = await client.wait_for_task(
                            task_id,
                            path=IDEOGRAM_EDIT_PATH,
                            poll_interval=self._poll_interval,
                            timeout=self._poll_timeout,
                            on_progress=cb,
                        )
                        url = result.primary_image
                        if not url:
                            raise GenerationError(
                                f"Task {task_id} sukses tapi tidak ada URL gambar"
                            )
                        progresses[idx].pct = 1.0
                        progresses[idx].status = "COMPLETED"
                        progresses[idx].done = True
                        progresses[idx].image_url = url
                        self._pool.report_success(key)
                        await report()
                        return
                except AuthError as exc:
                    self._pool.report_failure(key, permanent=True)
                    last_exc = exc
                    logger.warning("Inpaint task #%d auth gagal, rotasi key. %s", idx + 1, exc)
                    continue
                except QuotaError as exc:
                    self._pool.report_failure(key, permanent=False, cooldown_seconds=120.0)
                    last_exc = exc
                    logger.warning("Inpaint task #%d kuota/rate, rotasi key. %s", idx + 1, exc)
                    continue
                except TransientError as exc:
                    self._pool.report_failure(key, permanent=False, cooldown_seconds=10.0)
                    last_exc = exc
                    logger.warning("Inpaint task #%d transient, retry. %s", idx + 1, exc)
                    await asyncio.sleep(min(2.0 * attempt, 8.0))
                    continue
                except GenerationError as exc:
                    last_exc = exc
                    logger.warning("Inpaint task #%d generation error: %s", idx + 1, exc)
                    break
            raise last_exc or GenerationError(f"Inpaint task #{idx + 1} gagal tanpa exception")

        await asyncio.gather(*(run_one(i) for i in range(n)))

        urls = [p.image_url for p in progresses if p.image_url]
        return GenerationResult(image_urls=urls, task_ids=[])
