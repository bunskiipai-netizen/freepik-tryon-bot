"""Tests for the Freepik async client (mocked HTTP)."""

from __future__ import annotations

import httpx
import pytest
import respx

from freepik_tryon_bot.freepik import (
    IDEOGRAM_EDIT_PATH,
    SEEDREAM_EDIT_PATH,
    AuthError,
    FreepikImageClient,
    QuotaError,
    ReferenceImage,
    TransientError,
)

BASE = "https://api.freepik.com"
PATH = "/v1/ai/text-to-image/nano-banana-pro"
EDIT = IDEOGRAM_EDIT_PATH
SEED = SEEDREAM_EDIT_PATH


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


@respx.mock
async def test_create_inpaint_task_returns_id(client: FreepikImageClient) -> None:
    route = respx.post(f"{BASE}{EDIT}").mock(
        return_value=httpx.Response(
            200, json={"data": {"task_id": "edit-tid", "status": "CREATED"}}
        )
    )
    tid = await client.create_inpaint_task(
        image_b64="IMG", mask_b64="MSK", prompt="replace dress",
        style_reference_images_b64=["REF"],
    )
    assert tid == "edit-tid"
    assert route.called
    sent = route.calls[0].request.content
    assert b'"image":"IMG"' in sent
    assert b'"mask":"MSK"' in sent
    assert b'"prompt":"replace dress"' in sent
    assert b'"style_reference_images":["REF"]' in sent
    assert b'"rendering_speed":"DEFAULT"' in sent
    assert b'"magic_prompt":"OFF"' in sent


@respx.mock
async def test_create_inpaint_task_auth_error(client: FreepikImageClient) -> None:
    respx.post(f"{BASE}{EDIT}").mock(return_value=httpx.Response(403, text="nope"))
    with pytest.raises(AuthError):
        await client.create_inpaint_task(
            image_b64="i", mask_b64="m", prompt="p"
        )


@respx.mock
async def test_wait_for_task_uses_custom_path(client: FreepikImageClient) -> None:
    respx.get(f"{BASE}{EDIT}/tid").mock(
        return_value=httpx.Response(
            200,
            json={
                "data": {
                    "task_id": "tid",
                    "status": "COMPLETED",
                    "generated": ["https://cdn.example.com/edit.png"],
                }
            },
        )
    )
    result = await client.wait_for_task(
        "tid", path=EDIT, poll_interval=0.0
    )
    assert result.image_urls == ["https://cdn.example.com/edit.png"]


@respx.mock
async def test_create_seedream_edit_task_returns_id(client: FreepikImageClient) -> None:
    route = respx.post(f"{BASE}{SEED}").mock(
        return_value=httpx.Response(
            200, json={"data": {"task_id": "sd-tid", "status": "CREATED"}}
        )
    )
    tid = await client.create_seedream_edit_task(
        prompt="swap the dress",
        reference_images_b64_or_url=["MASTER_B64", "OUTFIT_B64"],
        aspect_ratio="traditional_3_4",
    )
    assert tid == "sd-tid"
    sent = route.calls[0].request.content
    assert b'"prompt":"swap the dress"' in sent
    assert b'"reference_images":["MASTER_B64","OUTFIT_B64"]' in sent
    assert b'"aspect_ratio":"traditional_3_4"' in sent


@respx.mock
async def test_create_seedream_edit_task_auth_error(client: FreepikImageClient) -> None:
    respx.post(f"{BASE}{SEED}").mock(return_value=httpx.Response(401, text="nope"))
    with pytest.raises(AuthError):
        await client.create_seedream_edit_task(
            prompt="x", reference_images_b64_or_url=["A"]
        )


async def test_create_seedream_edit_task_validates_ref_count(
    client: FreepikImageClient,
) -> None:
    with pytest.raises(ValueError):
        await client.create_seedream_edit_task(
            prompt="x", reference_images_b64_or_url=[]
        )
    with pytest.raises(ValueError):
        await client.create_seedream_edit_task(
            prompt="x", reference_images_b64_or_url=["a"] * 6
        )
