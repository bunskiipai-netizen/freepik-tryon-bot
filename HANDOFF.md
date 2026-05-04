# Handoff: Freepik Tryon Bot (Mannequin Tryon + Hanger)

This document is everything a fresh Devin session (or a human dev) needs
to keep building / running the **Mannequin Tryon + Hanger** Telegram bot
that lives in this repo as the `freepik_tryon_bot` package.

---

## 1. What this bot does

A private Telegram bot that swaps the outfit on bundled reference images
using a Freepik image-edit model. It produces **2 outputs per generation**.

### Two features

| Feature | User input | Output |
|---|---|---|
| **Mannequin Tryon** | 1 outfit photo | 2 mannequin scenes (front + mirror reflection back) with the new outfit applied. |
| **Hanger** | Number of outfits (1–5) + N outfit photos in order | 2 hanger-rack scenes with the uploaded outfits hanging left-to-right. |

The bundled reference images live in `freepik_tryon_bot/assets/`:

- `mannequin_1.jpg`, `mannequin_2.jpg` (mannequin in front of standing mirror).
- `hanger_1.jpg`, `hanger_2.jpg` (4 garments on a wooden rack).

The bot keeps background, tone, camera angle, and overall mood consistent
because each generation passes the master scene as reference image #1
and the user’s outfit (single image or stitched collage) as reference
image #2. The prompt explicitly tells the model to leave everything
except the garments untouched.

---

## 2. Token economy

- 1 token = 1 successfully delivered output image.
- Each successful generation normally consumes 2 tokens (2 outputs).
- `consume_token` is atomic in SQLite (`UPDATE … WHERE tokens > 0`).
- If a generation fails or download fails, no token is consumed.
- When balance ≤ `LOW_TOKEN_THRESHOLD` (default 10), the success message
  appends “Token sisa X segera hubungi admin untuk Top-up Token”
  followed by the brand footer (`By : Aksara Strategy`).

Admin commands:

| Command | Effect |
|---|---|
| `/grant <user_id> <amount>` | Add or subtract tokens, with audit log + notifies the target. |
| `/users` (or `/listusers`) | List all users + tokens. |
| `/keystatus` | Inspect API-key pool (which keys are disabled / cooling down). |

Bootstrap admin: if `ADMIN_USER_IDS` is empty, the first user who runs
`/start` becomes admin.

---

## 3. API: Freepik Nano Banana Pro

**Endpoint** (do not surface this name to end users):

```
POST https://api.freepik.com/v1/ai/text-to-image/nano-banana-pro
GET  https://api.freepik.com/v1/ai/text-to-image/nano-banana-pro/{task_id}
```

Headers: `x-freepik-api-key: <FPSX…>`

Body fields used:

```jsonc
{
  "prompt": "...",                // < 3000 chars
  "reference_images": [           // up to 3 images
    { "image": "<base64 or URL>", "text": "...", "mime_type": "image/jpeg" }
  ],
  "aspect_ratio": "3:4",          // matches our bundled refs
  "resolution": "2K"
}
```

Polling response: `data.status` ∈ `{CREATED, IN_PROGRESS, COMPLETED, FAILED, …}`.
On `COMPLETED`, `data.generated[]` contains image URLs (sometimes objects
with `url`/`image_url`/`uri`).

Refs to docs (community uses the term **"Nano Banana 2"** for this model):

- <https://docs.freepik.com/api-reference/text-to-image/nano-banana-pro/overview>
- <https://docs.freepik.com/api-reference/text-to-image/post-nano-banana-pro>
- <https://docs.freepik.com/api-reference/text-to-image/get-task-id-nano-banana-pro>

---

## 4. Architecture

```
freepik_tryon_bot/
├── __init__.py
├── __main__.py        # entrypoint: python -m freepik_tryon_bot
├── config.py          # env / .env loader (Config dataclass)
├── storage.py         # SQLite: users + tokens + audit log
├── apikey_pool.py     # round-robin pool with cooldown / permanent-disable
├── freepik.py         # async Nano Banana Pro client (httpx)
├── generator.py       # orchestrates 2 parallel tasks per user request
├── images.py          # base64, resize, outfit collage builder
├── prompts.py         # MANNEQUIN_PROMPT and HANGER_PROMPT_TEMPLATE
├── bot.py             # Telegram conversation handler
└── assets/            # bundled mannequin + hanger reference JPGs
scripts/
└── build_tutorial_pdf.py   # generates docs/tutorial_tryon_bot.pdf
tests/
└── test_tryon_*.py
```

Critical design choices:

1. **2 outputs per generation** — `Generator.run_batch` runs one task per
   bundled main image (`reference_groups[i]`). Both run in parallel with
   `asyncio.gather`. Progress is averaged; the Telegram message is
   edited with a 0–100 % bar.
2. **Reference images**: max 3 per task. Mannequin uses 2 (master scene +
   outfit). Hanger uses 2 (master scene + collage of all uploaded outfits
   stitched horizontally with `images.build_outfit_collage`).
3. **Key rotation**: each task leases a key from `APIKeyPool`. On 401/403
   the key is permanently disabled. On 402/429 it’s cooled down 120 s.
   Any 5xx / network error gets a 10 s cooldown and a retry on the next
   key. `max_attempts_per_task = 4`.
4. **No mention of Freepik / Gemini / Nano Banana in user-facing copy.**
   All progress text is generic ("Generating…", "model").
5. **Bundled reference images** are checked-in JPGs (≤ 1280 px). They’re
   loaded via `importlib.resources` so they survive `pip install`.

---

## 5. Local dev quickstart

```bash
git clone https://github.com/bunskiipai-netizen/freepik-veo-bot.git
cd freepik-veo-bot
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"

cp .env.example .env
# edit .env:
#   TELEGRAM_BOT_TOKEN=8600338340:AAH1d6h…             (from BotFather)
#   FREEPIK_API_KEYS=FPSX…key1,FPSX…key2               (comma-separated, rotation)
#   ADMIN_USER_IDS=<your telegram id>                  (optional; bootstrap mode otherwise)
#   DB_PATH=data/tryon_bot.sqlite3                     (recommended: separate DB)
python -m freepik_tryon_bot
```

`python -m freepik_veo_bot` (the existing veo bot) still works — they
share dependencies but live in separate packages.

CI: `ruff check .` + `pytest -q` (see `.github/workflows/ci.yml`).
Build the tutorial PDF: `python scripts/build_tutorial_pdf.py`.

---

## 6. Deploying

### Docker (VPS)

```bash
docker build -t freepik-tryon-bot .
docker run -d --restart=always \
    -e TELEGRAM_BOT_TOKEN=xxxxxxxx \
    -e FREEPIK_API_KEYS=FPSX...,FPSX... \
    -e DB_PATH=/app/data/tryon_bot.sqlite3 \
    -v "$PWD/data:/app/data" \
    --name freepik-tryon-bot \
    freepik-tryon-bot \
    python -m freepik_tryon_bot
```

(The Dockerfile installs both packages; choose entrypoint via the final
`python -m …` argument or override `CMD`.)

### Fly.io

`fly.toml` already exists for the veo bot. Easiest path: provision a
second app for the tryon bot, set the same volume mount but a different
DB filename, and override the start command in `fly.toml` to
`python -m freepik_tryon_bot`.

### Railway

`railway.json` runs the Dockerfile’s default CMD. To run the tryon bot,
override the start command to `python -m freepik_tryon_bot` in Railway’s
service settings.

---

## 7. Things you might want to extend

- **Webhook polling** — currently we poll. The API supports
  `webhook_url`; switching to webhooks would shave latency, but Telegram
  bot already runs polling so polling Freepik keeps deployment simple.
- **More pose variants** — additional bundled mannequin scenes (e.g.
  side angle). Just add JPGs to `freepik_tryon_bot/assets/` and extend
  the `MANNEQUIN_ASSETS` / `HANGER_ASSETS` tuples in `images.py`.
- **Per-user analytics** — token audit log already exists in
  `token_audit` table; surface it via a `/usage` admin command.
- **Refund on partial failure** — currently we charge per delivered
  image, which is the safe default. If you want stricter atomicity,
  refund the partial token if only 1 of 2 images was delivered.

---

## 8. Known limitations

- Reference images are capped at 3 by the upstream model. For 5 outfits
  on Hanger, the bot stitches a collage. If you find quality drops past
  3 outfits, consider running 2 sequential passes (fewer outfits per
  pass, then composite).
- Telegram media-group limit is 10 — fine for our 2-output flow.
- Telegram messages have a 4096-char limit; token notifications stay
  well below this.

---

## 9. Quick troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| `Semua API key habis/ditolak` | All keys permanently failed | Add fresh keys to `FREEPIK_API_KEYS`, restart bot. |
| `❌ Gagal generate: HTTP 400` | Reference image too large or wrong format | Re-upload outfit smaller; the bot also resizes to 1280 px max but very large originals can still 413. |
| `Saldo token kurang` | User has < 2 tokens | Admin: `/grant <user_id> <amount>`. |
| Progress bar stuck | Upstream backlog | Wait — `POLL_TIMEOUT` default 600 s, after which the task is aborted. |

---

## 10. Pop-quiz answers for the next Devin

- **Where are user-facing strings?** All in `freepik_tryon_bot/bot.py`. The
  prompts in `prompts.py` are model-facing (English) and never shown.
- **Why the Hanger collage?** Upstream caps reference_images at 3.
  Master scene + collage = 2 references, fits within the cap.
- **Why 2 outputs per generation?** The user requirement. We run one
  Nano Banana Pro task per bundled main image and gather them.
- **How do tokens get deducted?** After each downloaded output, in
  `_run_generation` after `send_media_group` succeeds.

---

_Authored 2026 — “By : Aksara Strategy.”_
