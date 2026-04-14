"""
IELTS Master — Telegram Bot
24/7 live: auto-replies to every DM + daily scheduled posts to channels.
"""

import os
import asyncio
import logging
from datetime import time
from telegram import Update, Bot
from telegram.ext import (
    ApplicationBuilder, MessageHandler, CommandHandler,
    filters, ContextTypes
)
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from agent_brain import get_reply, generate_post

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("telegram_bot")

BOT_TOKEN   = os.environ["TELEGRAM_BOT_TOKEN"]
CHANNEL_MN  = os.environ.get("TELEGRAM_CHANNEL_MN")   # Mongolian group chat ID
CHANNEL_KZ  = os.environ.get("TELEGRAM_CHANNEL_KZ")   # Kazakh group chat ID
CHANNEL_UZ  = os.environ.get("TELEGRAM_CHANNEL_UZ")   # Uzbek group chat ID

# ── Message handler ───────────────────────────────────────────────────────────

async def handle_message(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Reply to every DM and group mention with Claude-powered response."""
    if not update.message or not update.message.text:
        return

    msg = update.message.text
    chat_type = update.message.chat.type
    username = update.message.from_user.username or "unknown"

    # In groups: only reply if bot is mentioned or it's a reply to bot
    if chat_type in ("group", "supergroup"):
        bot_username = ctx.bot.username
        if f"@{bot_username}" not in msg:
            if not (update.message.reply_to_message and
                    update.message.reply_to_message.from_user.id == ctx.bot.id):
                return
        msg = msg.replace(f"@{bot_username}", "").strip()

    log.info(f"Message from @{username} ({chat_type}): {msg[:60]}")

    # Show typing indicator
    await ctx.bot.send_chat_action(
        chat_id=update.effective_chat.id,
        action="typing"
    )

    result = get_reply(platform="telegram", message=msg)

    if result["reply"]:
        await update.message.reply_text(result["reply"])
        log.info(f"Replied to @{username} | intent={result['intent']}")
    else:
        log.info(f"Skipped reply to @{username} | intent={result['intent']}")

# ── Scheduled post jobs ───────────────────────────────────────────────────────

async def post_daily_mn(ctx: ContextTypes.DEFAULT_TYPE):
    """Daily Mongolian writing tip — 9am UB time."""
    if not CHANNEL_MN:
        return
    result = generate_post("telegram_mn", "tip")
    if result.get("post"):
        await ctx.bot.send_message(chat_id=CHANNEL_MN, text=result["post"])
        log.info("Daily MN tip posted")

async def post_daily_kz(ctx: ContextTypes.DEFAULT_TYPE):
    """Daily Kazakh writing tip — 9am Almaty time."""
    if not CHANNEL_KZ:
        return
    result = generate_post("telegram_kz", "tip")
    if result.get("post"):
        await ctx.bot.send_message(chat_id=CHANNEL_KZ, text=result["post"])
        log.info("Daily KZ tip posted")

async def post_daily_uz(ctx: ContextTypes.DEFAULT_TYPE):
    """Daily Uzbek writing tip — 9am Tashkent time."""
    if not CHANNEL_UZ:
        return
    result = generate_post("telegram_uz", "tip")
    if result.get("post"):
        await ctx.bot.send_message(chat_id=CHANNEL_UZ, text=result["post"])
        log.info("Daily UZ tip posted")

async def post_weekly_challenge(ctx: ContextTypes.DEFAULT_TYPE):
    """Every Monday — 21-Day Challenge invite to all channels."""
    for channel, lang in [(CHANNEL_MN,"telegram_mn"),(CHANNEL_KZ,"telegram_kz"),(CHANNEL_UZ,"telegram_uz")]:
        if channel:
            result = generate_post(lang, "challenge")
            if result.get("post"):
                await ctx.bot.send_message(chat_id=channel, text=result["post"])
    log.info("Weekly challenge posts sent")

async def post_flash_sale(ctx: ContextTypes.DEFAULT_TYPE):
    """Flash sale blast — call manually or schedule around exam season."""
    for channel, lang in [(CHANNEL_MN,"telegram_mn"),(CHANNEL_KZ,"telegram_kz"),(CHANNEL_UZ,"telegram_uz")]:
        if channel:
            result = generate_post(lang, "flash_sale")
            if result.get("post"):
                await ctx.bot.send_message(chat_id=channel, text=result["post"])
    log.info("Flash sale posts sent")

# ── Command handlers ──────────────────────────────────────────────────────────

async def cmd_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Сайн байна уу! 👋\n\n"
        "IELTS Master-д тавтай морил.\n"
        "Бичгийн даалгавраа сайжруулахад туслая!\n\n"
        "🌐 ieltsmaster.org — үнэгүй эхлэх"
    )

async def cmd_start_kz(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Сәлем! IELTS Master-ге қош келдіңіз.\n"
        "Жазу дағдыларыңызды жақсартуға көмектесеміз!\n\n"
        "🌐 ieltsmaster.org — тегін бастаңыз"
    )

# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    # Handlers
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    # Scheduler
    scheduler = AsyncIOScheduler(timezone="Asia/Ulaanbaatar")

    # Daily tips — 9am in each timezone
    scheduler.add_job(post_daily_mn, "cron", hour=9, minute=0, args=[app])
    scheduler.add_job(post_daily_kz, "cron", hour=9, minute=0,
                      timezone="Asia/Almaty", args=[app])
    scheduler.add_job(post_daily_uz, "cron", hour=9, minute=0,
                      timezone="Asia/Tashkent", args=[app])

    # Weekly Monday challenge post
    scheduler.add_job(post_weekly_challenge, "cron", day_of_week="mon",
                      hour=10, minute=0, args=[app])

    scheduler.start()
    log.info("Telegram bot started — polling 24/7")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
