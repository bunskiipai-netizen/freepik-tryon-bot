"""Telegram handler / conversation flow for Mannequin Tryon dan Hanger."""

from __future__ import annotations

import asyncio
import contextlib
import io
import logging
from collections.abc import Callable
from dataclasses import dataclass
from html import escape

import httpx
from telegram import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    InputMediaPhoto,
    Update,
)
from telegram.constants import ChatAction, ParseMode
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from .apikey_pool import APIKeyPool
from .config import Config
from .freepik import GenerationError
from .generator import Generator, InpaintTaskInput
from .images import (
    HANGER_ASSETS,
    MANNEQUIN_ASSETS,
    build_outfit_collage,
    crop_pair_to_aspect_ratio,
    encode_b64,
    load_asset_bytes,
    mask_filename,
    to_jpeg_bytes,
)
from .prompts import hanger_prompt, mannequin_prompt
from .storage import Storage, UserRecord

logger = logging.getLogger(__name__)


# ---- callback data tokens -----------------------------------------------

CB_FEATURE_MANNEQUIN = "feat:mannequin"
CB_FEATURE_HANGER = "feat:hanger"
CB_BALANCE = "menu:balance"
CB_HELP = "menu:help"
CB_CANCEL = "flow:cancel"
CB_HANGER_COUNT_PREFIX = "hcnt:"
CB_RATIO_PREFIX = "ratio:"

SUPPORTED_RATIOS: tuple[str, ...] = ("1:1", "3:4", "4:3", "16:9", "9:16")


# ---- session state -------------------------------------------------------


@dataclass
class Session:
    """In-memory per-user flow state."""

    feature: str | None = None  # "mannequin" | "hanger"
    aspect_ratio: str | None = None  # one of SUPPORTED_RATIOS
    expected_outfits: int = 0
    outfits: list[bytes] | None = None  # raw JPG bytes after re-encoding


def get_session(context: ContextTypes.DEFAULT_TYPE) -> Session:
    sess = context.user_data.get("session")  # type: ignore[union-attr]
    if not isinstance(sess, Session):
        sess = Session()
        context.user_data["session"] = sess  # type: ignore[union-attr]
    return sess


def clear_session(context: ContextTypes.DEFAULT_TYPE) -> None:
    context.user_data["session"] = Session()  # type: ignore[union-attr]


# ---- markup helpers ------------------------------------------------------


def main_menu_markup() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("👗 Mannequin Tryon", callback_data=CB_FEATURE_MANNEQUIN),
                InlineKeyboardButton("🧥 Hanger", callback_data=CB_FEATURE_HANGER),
            ],
            [
                InlineKeyboardButton("💎 Saldo Token", callback_data=CB_BALANCE),
                InlineKeyboardButton("❓ Bantuan", callback_data=CB_HELP),
            ],
        ]
    )


def hanger_count_markup() -> InlineKeyboardMarkup:
    row = [
        InlineKeyboardButton(str(n), callback_data=f"{CB_HANGER_COUNT_PREFIX}{n}")
        for n in (1, 2, 3, 4, 5)
    ]
    return InlineKeyboardMarkup([row, [InlineKeyboardButton("✖️ Batal", callback_data=CB_CANCEL)]])


def ratio_markup() -> InlineKeyboardMarkup:
    rows = [
        [
            InlineKeyboardButton("1:1", callback_data=f"{CB_RATIO_PREFIX}1:1"),
            InlineKeyboardButton("3:4", callback_data=f"{CB_RATIO_PREFIX}3:4"),
            InlineKeyboardButton("4:3", callback_data=f"{CB_RATIO_PREFIX}4:3"),
        ],
        [
            InlineKeyboardButton("16:9", callback_data=f"{CB_RATIO_PREFIX}16:9"),
            InlineKeyboardButton("9:16", callback_data=f"{CB_RATIO_PREFIX}9:16"),
        ],
        [InlineKeyboardButton("✖️ Batal", callback_data=CB_CANCEL)],
    ]
    return InlineKeyboardMarkup(rows)


def cancel_only_markup() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[InlineKeyboardButton("✖️ Batal", callback_data=CB_CANCEL)]])


# ---- bot wrapper ---------------------------------------------------------


class TryonBot:
    def __init__(self, config: Config, storage: Storage, generator: Generator) -> None:
        self._cfg = config
        self._storage = storage
        self._generator = generator

    # ---- DB helpers (run in thread) --------------------------------------

    async def _ensure_user(self, update: Update) -> UserRecord:
        u = update.effective_user
        assert u is not None
        record = await asyncio.to_thread(
            self._storage.upsert_user,
            u.id,
            username=u.username,
            full_name=u.full_name,
        )
        return record

    async def _bootstrap_admin_if_needed(self, user_id: int) -> bool:
        if self._cfg.admin_user_ids:
            return user_id in self._cfg.admin_user_ids
        has_admin = await asyncio.to_thread(self._storage.has_admin)
        if not has_admin:
            await asyncio.to_thread(self._storage.upsert_user, user_id, is_admin=True)
            logger.info("Bootstrap: user %d ditetapkan sebagai admin", user_id)
            return True
        record = await asyncio.to_thread(self._storage.get_user, user_id)
        return bool(record and record.is_admin)

    async def _is_admin(self, user_id: int) -> bool:
        if user_id in self._cfg.admin_user_ids:
            return True
        record = await asyncio.to_thread(self._storage.get_user, user_id)
        return bool(record and record.is_admin)

    # ---- standard commands -----------------------------------------------

    async def cmd_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if update.effective_user is None or update.effective_message is None:
            return
        await self._ensure_user(update)
        is_admin = await self._bootstrap_admin_if_needed(update.effective_user.id)
        record = await asyncio.to_thread(self._storage.get_user, update.effective_user.id)
        balance = record.tokens if record else 0
        clear_session(context)
        admin_line = "\n👑 Anda terdaftar sebagai <b>admin</b>." if is_admin else ""
        await update.effective_message.reply_text(
            (
                "<b>Selamat datang!</b>\n\n"
                "Pilih fitur di bawah untuk mulai membuat foto outfit.\n\n"
                f"💎 Saldo token Anda: <b>{balance}</b>\n"
                "1 token = 1 gambar yang berhasil dikirim.\n"
                f"{admin_line}\n\n"
                f"<i>{escape(self._cfg.brand_footer)}</i>"
            ),
            parse_mode=ParseMode.HTML,
            reply_markup=main_menu_markup(),
        )

    async def cmd_help(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if update.effective_message is None:
            return
        await update.effective_message.reply_text(
            (
                "<b>Cara pakai</b>\n\n"
                "1. Pilih <b>Mannequin Tryon</b> atau <b>Hanger</b> dari menu utama.\n"
                "2. Pilih <b>rasio output</b> (1:1, 3:4, 4:3, 16:9, 9:16).\n"
                "3. <b>Mannequin Tryon</b>: kirim 1 foto outfit (baju yang ingin "
                "dipakai mannequin).\n"
                "4. <b>Hanger</b>: pilih jumlah outfit (1–5), lalu kirim foto outfit "
                "satu per satu sesuai urutan kiri-ke-kanan.\n"
                "5. Tunggu progress generate, lalu Anda terima 2 gambar hasil.\n\n"
                "<b>Catatan</b>:\n"
                "• Format foto JPG/PNG, sisi terpanjang ≤ 4096 px.\n"
                "• Latar belakang outfit polos atau flat-lay paling akurat.\n"
                "• Setiap gambar yang berhasil dikirim memotong 1 token.\n\n"
                f"<i>{escape(self._cfg.brand_footer)}</i>"
            ),
            parse_mode=ParseMode.HTML,
            reply_markup=main_menu_markup(),
        )

    async def cmd_menu(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if update.effective_message is None:
            return
        clear_session(context)
        await update.effective_message.reply_text(
            "Pilih fitur:", reply_markup=main_menu_markup()
        )

    async def cmd_myid(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if update.effective_user is None or update.effective_message is None:
            return
        await update.effective_message.reply_text(
            f"User ID Anda: <code>{update.effective_user.id}</code>",
            parse_mode=ParseMode.HTML,
        )

    async def cmd_balance(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if update.effective_user is None or update.effective_message is None:
            return
        balance = await asyncio.to_thread(
            self._storage.get_balance, update.effective_user.id
        )
        await update.effective_message.reply_text(
            f"💎 Saldo token Anda: <b>{balance}</b>",
            parse_mode=ParseMode.HTML,
        )

    async def cmd_cancel(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if update.effective_message is None:
            return
        clear_session(context)
        await update.effective_message.reply_text(
            "Dibatalkan. Pilih lagi:", reply_markup=main_menu_markup()
        )

    # ---- admin commands ---------------------------------------------------

    async def cmd_grant(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if update.effective_user is None or update.effective_message is None:
            return
        if not await self._is_admin(update.effective_user.id):
            await update.effective_message.reply_text("Hanya admin yang bisa pakai perintah ini.")
            return
        args = context.args or []
        if len(args) != 2:
            await update.effective_message.reply_text(
                "Format: <code>/grant &lt;user_id&gt; &lt;jumlah&gt;</code>\n"
                "Contoh: <code>/grant 123456789 50</code>",
                parse_mode=ParseMode.HTML,
            )
            return
        try:
            target = int(args[0])
            amount = int(args[1])
        except ValueError:
            await update.effective_message.reply_text("user_id dan jumlah harus angka.")
            return
        new_balance = await asyncio.to_thread(
            self._storage.grant_tokens,
            target,
            amount,
            actor_id=update.effective_user.id,
        )
        sign = "+" if amount >= 0 else ""
        await update.effective_message.reply_text(
            f"OK. {sign}{amount} token untuk user <code>{target}</code>. "
            f"Saldo sekarang: <b>{new_balance}</b>.",
            parse_mode=ParseMode.HTML,
        )
        try:
            await context.bot.send_message(
                chat_id=target,
                text=(
                    f"💎 Saldo token Anda diperbarui ({sign}{amount}). "
                    f"Total sekarang: <b>{new_balance}</b>."
                ),
                parse_mode=ParseMode.HTML,
            )
        except Exception:  # noqa: BLE001 - target user might not have started bot
            logger.info("Tidak bisa kirim notif top-up ke %d", target)

    async def cmd_users(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if update.effective_user is None or update.effective_message is None:
            return
        if not await self._is_admin(update.effective_user.id):
            await update.effective_message.reply_text("Hanya admin yang bisa pakai perintah ini.")
            return
        users = await asyncio.to_thread(self._storage.list_users)
        if not users:
            await update.effective_message.reply_text("(belum ada user terdaftar)")
            return
        lines = [
            (
                f"{'👑' if u.is_admin else '👤'} <code>{u.user_id}</code> "
                f"@{u.username or '-'} — 💎 {u.tokens}"
            )
            for u in users[:50]
        ]
        await update.effective_message.reply_text(
            "\n".join(lines), parse_mode=ParseMode.HTML
        )

    async def cmd_status(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if update.effective_user is None or update.effective_message is None:
            return
        if not await self._is_admin(update.effective_user.id):
            await update.effective_message.reply_text("Hanya admin.")
            return
        pool_status = self._generator._pool.status()  # type: ignore[attr-defined]
        lines = [
            (
                f"#{s['index'] + 1} {s['fingerprint']} "
                f"{'✅' if s['available'] else '⛔'} "
                f"perm={s['permanent']} fail={s['failures']} "
                f"cd={s['cooldown_remaining']:.0f}s"
            )
            for s in pool_status
        ]
        await update.effective_message.reply_text("\n".join(lines))

    # ---- callback handlers -----------------------------------------------

    async def on_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if update.callback_query is None or update.effective_user is None:
            return
        query = update.callback_query
        data = query.data or ""
        await query.answer()

        if data == CB_FEATURE_MANNEQUIN:
            await self._start_mannequin(update, context)
        elif data == CB_FEATURE_HANGER:
            await self._start_hanger(update, context)
        elif data.startswith(CB_HANGER_COUNT_PREFIX):
            try:
                n = int(data[len(CB_HANGER_COUNT_PREFIX):])
            except ValueError:
                return
            await self._set_hanger_count(update, context, n)
        elif data.startswith(CB_RATIO_PREFIX):
            ratio = data[len(CB_RATIO_PREFIX):]
            if ratio not in SUPPORTED_RATIOS:
                return
            await self._set_ratio(update, context, ratio)
        elif data == CB_BALANCE:
            await self.cmd_balance(update, context)
        elif data == CB_HELP:
            await self.cmd_help(update, context)
        elif data == CB_CANCEL:
            await self.cmd_cancel(update, context)

    async def _start_mannequin(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        assert update.effective_message is not None
        sess = get_session(context)
        sess.feature = "mannequin"
        sess.aspect_ratio = None
        sess.expected_outfits = 0
        sess.outfits = []
        await update.effective_message.reply_text(
            "👗 <b>Mannequin Tryon</b>\n\nPilih rasio output:",
            parse_mode=ParseMode.HTML,
            reply_markup=ratio_markup(),
        )

    async def _start_hanger(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        assert update.effective_message is not None
        sess = get_session(context)
        sess.feature = "hanger"
        sess.aspect_ratio = None
        sess.expected_outfits = 0
        sess.outfits = []
        await update.effective_message.reply_text(
            "🧥 <b>Hanger</b>\n\nPilih rasio output:",
            parse_mode=ParseMode.HTML,
            reply_markup=ratio_markup(),
        )

    async def _set_ratio(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE, ratio: str
    ) -> None:
        assert update.effective_message is not None
        sess = get_session(context)
        if sess.feature is None:
            await update.effective_message.reply_text(
                "Pilih dulu fitur dari menu:", reply_markup=main_menu_markup()
            )
            return
        sess.aspect_ratio = ratio
        if sess.feature == "mannequin":
            sess.expected_outfits = 1
            sess.outfits = []
            await update.effective_message.reply_text(
                f"Rasio: <b>{ratio}</b>.\n\n"
                "Kirim <b>1 foto outfit</b> yang ingin dipakai mannequin. "
                "Foto polos / flat-lay paling akurat.",
                parse_mode=ParseMode.HTML,
                reply_markup=cancel_only_markup(),
            )
        elif sess.feature == "hanger":
            await update.effective_message.reply_text(
                f"Rasio: <b>{ratio}</b>.\n\nPilih jumlah outfit yang akan digantung:",
                parse_mode=ParseMode.HTML,
                reply_markup=hanger_count_markup(),
            )

    async def _set_hanger_count(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE, count: int
    ) -> None:
        assert update.effective_message is not None
        if count < 1 or count > 5:
            return
        sess = get_session(context)
        if sess.feature != "hanger":
            return
        if sess.aspect_ratio is None:
            await update.effective_message.reply_text(
                "Pilih rasio dulu:", reply_markup=ratio_markup()
            )
            return
        sess.expected_outfits = count
        sess.outfits = []
        await update.effective_message.reply_text(
            f"OK. Kirim <b>foto outfit 1/{count}</b> sekarang. "
            "Urutan upload = urutan kiri-ke-kanan di hanger.",
            parse_mode=ParseMode.HTML,
            reply_markup=cancel_only_markup(),
        )

    # ---- photo handler ---------------------------------------------------

    async def on_photo(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if update.effective_message is None or update.effective_user is None:
            return
        message = update.effective_message
        sess = get_session(context)
        if sess.feature is None or sess.expected_outfits == 0:
            await message.reply_text(
                "Pilih dulu fitur dari menu:", reply_markup=main_menu_markup()
            )
            return

        if sess.aspect_ratio is None:
            await message.reply_text(
                "Pilih rasio output dulu:", reply_markup=ratio_markup()
            )
            return

        photo = message.photo[-1] if message.photo else None
        if photo is None and message.document:
            doc = message.document
            if doc.mime_type and doc.mime_type.startswith("image/"):
                photo_file = await doc.get_file()
            else:
                await message.reply_text("Kirim file gambar (JPG/PNG/WebP).")
                return
        elif photo is None:
            await message.reply_text("Kirim sebagai foto, ya.")
            return
        else:
            photo_file = await photo.get_file()

        raw = bytes(await photo_file.download_as_bytearray())
        try:
            jpg = to_jpeg_bytes(raw)
        except Exception:  # noqa: BLE001
            await message.reply_text("Gambar tidak bisa diproses, coba foto lain.")
            return

        outfits = sess.outfits or []
        outfits.append(jpg)
        sess.outfits = outfits

        if len(outfits) < sess.expected_outfits:
            await message.reply_text(
                f"📸 Diterima ({len(outfits)}/{sess.expected_outfits}). "
                f"Kirim foto outfit {len(outfits) + 1}/{sess.expected_outfits}.",
                reply_markup=cancel_only_markup(),
            )
            return

        # Got all outfits — start generation
        await self._run_generation(update, context, sess)

    # ---- generation -------------------------------------------------------

    async def _run_generation(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
        sess: Session,
    ) -> None:
        assert update.effective_message is not None
        assert update.effective_user is not None
        message = update.effective_message
        user_id = update.effective_user.id

        balance = await asyncio.to_thread(self._storage.get_balance, user_id)
        if balance < 2:
            await message.reply_text(
                f"❌ Saldo token kurang. Butuh minimal 2, saldo Anda: {balance}.\n"
                f"Hubungi admin untuk Top-up Token.\n\n<i>{escape(self._cfg.brand_footer)}</i>",
                parse_mode=ParseMode.HTML,
            )
            clear_session(context)
            return

        await context.bot.send_chat_action(message.chat_id, ChatAction.UPLOAD_PHOTO)
        progress_msg = await message.reply_text("⏳ Memulai generate… 0%")

        # Build per-task inpainting inputs (image + mask + style references).
        outfits = sess.outfits or []
        aspect_ratio = sess.aspect_ratio or self._cfg.aspect_ratio
        if sess.feature == "mannequin":
            assets = MANNEQUIN_ASSETS
            style_b64s = [encode_b64(outfits[0])]
            inpaint_tasks: list[InpaintTaskInput] = []
            for asset in assets:
                master_bytes = load_asset_bytes(asset)
                mask_bytes = load_asset_bytes(mask_filename(asset))
                cropped_img, cropped_mask = crop_pair_to_aspect_ratio(
                    master_bytes, mask_bytes, aspect_ratio
                )
                inpaint_tasks.append(
                    InpaintTaskInput(
                        image_b64=encode_b64(cropped_img),
                        mask_b64=encode_b64(cropped_mask),
                        prompt=mannequin_prompt(asset),
                        style_reference_images_b64=style_b64s,
                    )
                )
        elif sess.feature == "hanger":
            assets = HANGER_ASSETS
            collage = build_outfit_collage(outfits)
            style_b64s = [encode_b64(collage)]
            inpaint_tasks = []
            for asset in assets:
                master_bytes = load_asset_bytes(asset)
                mask_bytes = load_asset_bytes(mask_filename(asset))
                cropped_img, cropped_mask = crop_pair_to_aspect_ratio(
                    master_bytes, mask_bytes, aspect_ratio
                )
                inpaint_tasks.append(
                    InpaintTaskInput(
                        image_b64=encode_b64(cropped_img),
                        mask_b64=encode_b64(cropped_mask),
                        prompt=hanger_prompt(asset, len(outfits)),
                        style_reference_images_b64=style_b64s,
                    )
                )
        else:
            await message.reply_text("State error. Mulai ulang dengan /menu.")
            clear_session(context)
            return

        last_text = ""

        async def on_progress(pct: float, status: str) -> None:
            nonlocal last_text
            bar_blocks = max(0, min(20, int(pct * 20)))
            bar = "█" * bar_blocks + "░" * (20 - bar_blocks)
            text = f"⏳ Generating…\n[{bar}] {int(pct * 100)}%"
            if text == last_text:
                return
            last_text = text
            with contextlib.suppress(Exception):
                await progress_msg.edit_text(text)

        try:
            result = await self._generator.run_inpaint_batch(
                tasks=inpaint_tasks,
                on_progress=on_progress,
            )
        except GenerationError as exc:
            logger.exception("Generation gagal")
            try:
                await progress_msg.edit_text(f"❌ Gagal generate: {exc}")
            except Exception:  # noqa: BLE001
                await message.reply_text(f"❌ Gagal generate: {exc}")
            clear_session(context)
            return
        except Exception as exc:  # noqa: BLE001
            logger.exception("Unexpected error")
            try:
                await progress_msg.edit_text(f"❌ Error: {exc}")
            except Exception:  # noqa: BLE001
                await message.reply_text(f"❌ Error: {exc}")
            clear_session(context)
            return

        with contextlib.suppress(Exception):
            await progress_msg.edit_text("✅ Generate sukses, mengirim gambar…")

        # Download + send
        media: list[InputMediaPhoto] = []
        downloaded: list[bytes] = []
        async with httpx.AsyncClient(timeout=60.0) as http:
            for url in result.image_urls[:2]:
                try:
                    r = await http.get(url)
                    r.raise_for_status()
                    downloaded.append(r.content)
                except Exception:  # noqa: BLE001
                    logger.exception("Gagal download %s", url)

        if not downloaded:
            with contextlib.suppress(Exception):
                await progress_msg.edit_text("❌ Gagal download hasil. Token tidak dipotong.")
            clear_session(context)
            return

        # Build media group
        for idx, content in enumerate(downloaded):
            media.append(
                InputMediaPhoto(
                    media=io.BytesIO(content),
                    filename=f"hasil_{idx + 1}.jpg",
                )
            )
        try:
            await context.bot.send_media_group(message.chat_id, media)
        except Exception:
            logger.exception("send_media_group gagal, fallback per gambar")
            for idx, content in enumerate(downloaded):
                try:
                    await context.bot.send_photo(message.chat_id, io.BytesIO(content))
                except Exception:  # noqa: BLE001
                    logger.exception("send_photo gagal idx=%d", idx)

        # Deduct one token per delivered image
        delivered = len(downloaded)
        new_balance = balance
        for _ in range(delivered):
            updated = await asyncio.to_thread(
                self._storage.consume_token, user_id, reason="image_delivered"
            )
            if updated is None:
                break
            new_balance = updated

        suffix = ""
        if new_balance <= self._cfg.low_token_threshold:
            suffix = (
                f"\n\n⚠️ <b>Token sisa {new_balance} segera hubungi admin "
                "untuk Top-up Token</b>"
            )
        await message.reply_text(
            (
                f"✅ Berhasil! {delivered} gambar terkirim.\n"
                f"💎 Sisa token: <b>{new_balance}</b>"
                f"{suffix}\n\n<i>{escape(self._cfg.brand_footer)}</i>"
            ),
            parse_mode=ParseMode.HTML,
            reply_markup=main_menu_markup(),
        )
        clear_session(context)


# ---- application factory --------------------------------------------------


def build_application(
    config: Config,
    storage: Storage,
    pool: APIKeyPool,
    *,
    generator_factory: Callable[[APIKeyPool], Generator] | None = None,
) -> tuple[Application, TryonBot]:
    if generator_factory is None:
        gen = Generator(
            pool,
            poll_interval=config.poll_interval,
            poll_timeout=config.poll_timeout,
            progress_min_interval=config.progress_min_interval,
        )
    else:
        gen = generator_factory(pool)
    bot = TryonBot(config=config, storage=storage, generator=gen)

    app = Application.builder().token(config.telegram_bot_token).build()

    app.add_handler(CommandHandler("start", bot.cmd_start))
    app.add_handler(CommandHandler("menu", bot.cmd_menu))
    app.add_handler(CommandHandler("help", bot.cmd_help))
    app.add_handler(CommandHandler("myid", bot.cmd_myid))
    app.add_handler(CommandHandler("saldo", bot.cmd_balance))
    app.add_handler(CommandHandler("balance", bot.cmd_balance))
    app.add_handler(CommandHandler("cancel", bot.cmd_cancel))
    app.add_handler(CommandHandler("batal", bot.cmd_cancel))
    app.add_handler(CommandHandler("grant", bot.cmd_grant))
    app.add_handler(CommandHandler("users", bot.cmd_users))
    app.add_handler(CommandHandler("listusers", bot.cmd_users))
    app.add_handler(CommandHandler("keystatus", bot.cmd_status))
    app.add_handler(CallbackQueryHandler(bot.on_callback))
    app.add_handler(MessageHandler(filters.PHOTO | filters.Document.IMAGE, bot.on_photo))

    return app, bot


__all__ = [
    "Session",
    "TryonBot",
    "build_application",
    "main_menu_markup",
]
