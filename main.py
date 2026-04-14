"""
IELTS Master — Main Entry Point
Runs all agents concurrently: Telegram + Meta webhook + Social monitoring.
Deploy this single file on Railway. Set PORT env var.
"""

import os
import threading
import logging
from flask import Flask

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("main")

# ── Health check server (required by Railway) ─────────────────────────────────

health_app = Flask("health")

@health_app.route("/")
def health():
    return {"status": "alive", "service": "IELTS Master Agent"}, 200

@health_app.route("/health")
def healthcheck():
    return {"status": "ok"}, 200

# ── Start each agent in its own thread ───────────────────────────────────────

def run_telegram():
    try:
        log.info("Starting Telegram bot...")
        from telegram_bot import main as telegram_main
        telegram_main()
    except Exception as e:
        log.error(f"Telegram bot crashed: {e}")

def run_social():
    try:
        log.info("Starting Social agent (Twitter/Reddit/YouTube)...")
        from social_agent import start as social_start
        social_start()
    except Exception as e:
        log.error(f"Social agent crashed: {e}")

def run_meta_webhook():
    try:
        log.info("Starting Meta webhook (Facebook/Instagram)...")
        from meta_agent import create_app
        meta_app = create_app()
        meta_app.run(host="0.0.0.0", port=int(os.environ.get("META_PORT", 5001)))
    except Exception as e:
        log.error(f"Meta agent crashed: {e}")

# ── Entry ─────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    # Start Telegram in thread
    t1 = threading.Thread(target=run_telegram, daemon=True)
    t1.start()

    # Start Social monitoring in thread
    t2 = threading.Thread(target=run_social, daemon=True)
    t2.start()

    # Start Meta webhook in thread (if credentials exist)
    if os.environ.get("META_PAGE_ACCESS_TOKEN"):
        t3 = threading.Thread(target=run_meta_webhook, daemon=True)
        t3.start()

    # Health server on main thread (Railway needs this)
    PORT = int(os.environ.get("PORT", 5000))
    log.info(f"Health server on port {PORT}")
    health_app.run(host="0.0.0.0", port=PORT)
