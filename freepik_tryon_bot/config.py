"""Environment-driven configuration loader for the tryon bot."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

DEFAULT_DB_PATH = "data/tryon_bot.sqlite3"
DEFAULT_LOW_TOKEN_THRESHOLD = 10
DEFAULT_POLL_INTERVAL = 4.0
DEFAULT_POLL_TIMEOUT = 600.0
DEFAULT_PROGRESS_MIN_INTERVAL = 2.0
DEFAULT_RESOLUTION = "2K"
DEFAULT_ASPECT_RATIO = "3:4"
DEFAULT_BRAND_FOOTER = "By : Aksara Strategy"


@dataclass(frozen=True)
class Config:
    telegram_bot_token: str
    api_keys: tuple[str, ...]
    admin_user_ids: frozenset[int]
    db_path: Path
    log_level: str
    poll_interval: float
    poll_timeout: float
    progress_min_interval: float
    low_token_threshold: int
    resolution: str
    aspect_ratio: str
    brand_footer: str
    extra: dict[str, str] = field(default_factory=dict)


def _parse_int_list(raw: str | None) -> frozenset[int]:
    if not raw:
        return frozenset()
    out: set[int] = set()
    for part in raw.split(","):
        part = part.strip()
        if not part:
            continue
        try:
            out.add(int(part))
        except ValueError:
            continue
    return frozenset(out)


def _parse_keys(raw: str | None) -> tuple[str, ...]:
    if not raw:
        return ()
    return tuple(p.strip() for p in raw.split(",") if p.strip())


def _parse_float(raw: str | None, default: float) -> float:
    if not raw:
        return default
    try:
        return float(raw)
    except ValueError:
        return default


def _parse_int(raw: str | None, default: int) -> int:
    if not raw:
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def load_config(env_file: str | os.PathLike[str] | None = ".env") -> Config:
    """Read configuration from environment variables (and optional .env)."""
    if env_file:
        path = Path(env_file)
        if path.is_file():
            load_dotenv(path, override=False)

    token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    if not token:
        raise RuntimeError(
            "TELEGRAM_BOT_TOKEN belum di-set. Set di environment atau file .env."
        )

    keys = _parse_keys(os.getenv("FREEPIK_API_KEYS"))
    if not keys:
        single = os.getenv("FREEPIK_API_KEY", "").strip()
        if single:
            keys = (single,)
    if not keys:
        raise RuntimeError(
            "FREEPIK_API_KEYS belum di-set. Pisahkan dengan koma untuk rotasi otomatis."
        )

    return Config(
        telegram_bot_token=token,
        api_keys=keys,
        admin_user_ids=_parse_int_list(os.getenv("ADMIN_USER_IDS")),
        db_path=Path(os.getenv("DB_PATH", DEFAULT_DB_PATH)),
        log_level=os.getenv("LOG_LEVEL", "INFO").upper(),
        poll_interval=_parse_float(os.getenv("POLL_INTERVAL"), DEFAULT_POLL_INTERVAL),
        poll_timeout=_parse_float(os.getenv("POLL_TIMEOUT"), DEFAULT_POLL_TIMEOUT),
        progress_min_interval=_parse_float(
            os.getenv("PROGRESS_MIN_INTERVAL"), DEFAULT_PROGRESS_MIN_INTERVAL
        ),
        low_token_threshold=_parse_int(
            os.getenv("LOW_TOKEN_THRESHOLD"), DEFAULT_LOW_TOKEN_THRESHOLD
        ),
        resolution=os.getenv("OUTPUT_RESOLUTION", DEFAULT_RESOLUTION),
        aspect_ratio=os.getenv("OUTPUT_ASPECT_RATIO", DEFAULT_ASPECT_RATIO),
        brand_footer=os.getenv("BRAND_FOOTER", DEFAULT_BRAND_FOOTER),
    )
