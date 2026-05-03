# Freepik Tryon Bot — Mannequin Tryon & Hanger

Telegram bot pribadi untuk **mengganti pakaian** pada gambar referensi
(mannequin atau gantungan baju) dengan AI image edit. Sistem memakai
**token-based billing**: 1 token = 1 gambar yang berhasil dikirim ke
user. Admin bisa top-up token via perintah bot. By : Aksara Strategy.

## Fitur

| Fitur | Input user | Output |
|---|---|---|
| 👗 **Mannequin Tryon** | 1 foto outfit | 2 gambar mannequin (pose depan + refleksi cermin) dengan outfit baru. Background, cermin, ruangan, pencahayaan tetap sama. |
| 🧥 **Hanger** | Pilih jumlah outfit (1–5) + foto outfit satu-per-satu | 2 gambar rak gantungan dengan outfit Anda urut kiri-ke-kanan. |

Output selalu 2 gambar per generate karena bot menjalankan 2 task
paralel — satu per master scene yang sudah dibundle di `assets/`.

## Cepat: jalankan lokal

```bash
git clone https://github.com/<owner>/freepik-tryon-bot.git
cd freepik-tryon-bot
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"

cp .env.example .env
# isi:
#   TELEGRAM_BOT_TOKEN=...
#   FREEPIK_API_KEYS=key1,key2          # comma-separated, rotasi otomatis
#   ADMIN_USER_IDS=                      # opsional; user pertama jadi admin kalau kosong
python -m freepik_tryon_bot
```

Lalu di Telegram:

1. Buka bot, ketik `/start`.
2. Pilih **👗 Mannequin Tryon** atau **🧥 Hanger** dari menu.
3. Ikuti petunjuk (upload outfit / pilih jumlah).
4. Tunggu progress 0–100 %, terima 2 gambar hasil + sisa token.

User pertama yang `/start` otomatis menjadi admin (mode bootstrap)
kalau `ADMIN_USER_IDS` kosong. Admin bisa pakai:

```
/grant <user_id> <amount>      # +/- token
/users                          # list user + saldo
/keystatus                      # status pool API key
```

## Token rules

- 1 token dipotong setiap gambar yang **sukses dikirim** ke user.
- Sekali generate normalnya potong 2 token (2 gambar).
- Kalau download/kirim gagal, token tidak dipotong.
- Notifikasi otomatis muncul saat saldo ≤ 10:

  > Token sisa 10 segera hubungi admin untuk Top-up Token
  > By : Aksara Strategy

## Rotasi API key

Set `FREEPIK_API_KEYS=key1,key2,key3,...`. Bot:

- Permanen menonaktifkan key yang balas 401/403 (key invalid).
- Cooldown 120 detik untuk key yang balas 402/429 (kuota/rate limit).
- Retry 5xx/network error sampai 4× lintas key.

Cek status pool kapan saja: `/keystatus` (admin only).

## Deployment

### Docker

```bash
docker build -t freepik-tryon-bot .
docker run -d --restart=always \
    -e TELEGRAM_BOT_TOKEN=... \
    -e FREEPIK_API_KEYS=key1,key2 \
    -e DB_PATH=/app/data/tryon_bot.sqlite3 \
    -v "$PWD/data:/app/data" \
    --name freepik-tryon-bot \
    freepik-tryon-bot
```

### Fly.io / Railway / Heroku

`Procfile` sudah tersedia (`worker: python -m freepik_tryon_bot`).

## Tutorial untuk end-user

`docs/tutorial_tryon_bot.pdf` di-build dari
`scripts/build_tutorial_pdf.py`:

```bash
source .venv/bin/activate
python scripts/build_tutorial_pdf.py
```

## Test & lint

```bash
ruff check .
pytest -q
```

47 test mencakup storage, token system, API key rotation, image utils,
config loader, dan mock HTTP untuk Nano Banana Pro client.

## Arsitektur

Detail lengkap (modul, prompt, polling, key pool) ada di
[`HANDOFF.md`](HANDOFF.md) — dokumen serah-terima yang sengaja ditulis
agar developer / Devin session lain bisa langsung melanjutkan.
