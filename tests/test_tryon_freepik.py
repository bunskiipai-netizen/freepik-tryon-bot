"""Tests for the Nano Banana Pro async client (mocked HTTP)."""

from __future__ import annotations

import httpx
import pytest
import respx

from freepik_tryon_bot.freepik import (
    AuthError,
    FreepikImageClient,
    QuotaError,
    ReferenceImage,
    TransientError,
)

BASE = "https://api.freepik.com"
PATH = "/v1/ai/text-to-image/nano-banana-pro"


@pytest.fixture()
def client() -> FreepikImageClient:
    http = httpx.AsyncClient(headers={"x-freepik-api-key": "k"})
    return FreepikImageClient(api_key="k", client=http)


@respx.mock
async def test_create_task_returns_id(client: FreepikImageClient) -> None:
    route = respx.post(f"{BASE}{PATH}").mock(
        return_value=httpx.Response(
            200, json={"data": {"task_id": "tid", "status": "CREATED"}}
        )
    )
    tid = await client.create_task(
        prompt="hello",
        reference_images=[ReferenceImage("aaa", text="x", mime_type="image/jpeg")],
    )
    assert tid == "tid"
    assert route.called
    sent = route.calls[0].request
    assert b'"prompt":"hello"' in sent.content
    assert b'"reference_images"' in sent.content


@respx.mock
async def test_create_task_auth_error(client: FreepikImageClient) -> None:
    respx.post(f"{BASE}{PATH}").mock(
        return_value=httpx.Response(401, json={"message": "Invalid API key"})
    )
    with pytest.raises(AuthError):
        await client.create_task(prompt="hi", reference_images=[])


@respx.mock
async def test_create_task_quota_error(client: FreepikImageClient) -> None:
    respx.post(f"{BASE}{PATH}").mock(return_value=httpx.Response(429, text="rate"))
    with pytest.raises(QuotaError):
        await client.create_task(prompt="hi", reference_images=[])


@respx.mock
async def test_create_task_5xx_is_transient(client: FreepikImageClient) -> None:
    respx.post(f"{BASE}{PATH}").mock(return_value=httpx.Response(503, text="down"))
    with pytest.raises(TransientError):
        await client.create_task(prompt="hi", reference_images=[])


@respx.mock
async def test_wait_for_task_polls_until_completed(client: FreepikImageClient) -> None:
    respx.get(f"{BASE}{PATH}/tid").mock(
        side_effect=[
            httpx.Response(
                200,
                json={"data": {"task_id": "tid", "status": "IN_PROGRESS", "progress": 30}},
            ),
            httpx.Response(
                200,
                json={
                    "data": {
                        "task_id": "tid",
                        "status": "COMPLETED",
                        "generated": ["https://cdn.example.com/result.jpg"],
                    }
                },
            ),
        ]
    )
    progress_calls: list[tuple[str, float | None]] = []

    async def cb(status: str, p: float | None) -> None:
        progress_calls.append((status, p))

    result = await client.wait_for_task(
        "tid", poll_interval=0.0, on_progress=cb
    )
    assert result.status == "COMPLETED"
    assert result.image_urls == ["https://cdn.example.com/result.jpg"]
    assert any(s == "IN_PROGRESS" for s, _ in progress_calls)


@respx.mock
async def test_wait_for_task_failed_raises(client: FreepikImageClient) -> None:
    respx.get(f"{BASE}{PATH}/tid").mock(
        return_value=httpx.Response(
            200, json={"data": {"task_id": "tid", "status": "FAILED"}}
        )
    )
    from freepik_tryon_bot.freepik import GenerationError

    with pytest.raises(GenerationError):
        await client.wait_for_task("tid", poll_interval=0.0)
