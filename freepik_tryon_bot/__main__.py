"""Entrypoint: ``python -m freepik_tryon_bot``."""

from __future__ import annotations

import logging
import sys

from .apikey_pool import APIKeyPool
from .bot import build_application
from .config import load_config
from .storage import Storage


def main() -> None:
    try:
        config = load_config()
    except RuntimeError as exc:
        sys.stderr.write(f"Config error: {exc}\n")
        sys.exit(2)

    logging.basicConfig(
        level=getattr(logging, config.log_level, logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    storage = Storage(config.db_path)
    if config.admin_user_ids:
        storage.ensure_admins(config.admin_user_ids)
    pool = APIKeyPool(list(config.api_keys))
    app, _bot = build_application(config, storage, pool)
    logging.getLogger(__name__).info(
        "Tryon bot starting (%d API key(s), DB=%s)", len(config.api_keys), config.db_path
    )
    app.run_polling(close_loop=False)


if __name__ == "__main__":
    main()
