import os
import threading
import logging
from flask import Flask

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("main")

app = Flask(__name__)

@app.route("/")
def root():
    return {"status": "alive", "service": "IELTS Master Agent"}, 200

@app.route("/health")
def health():
    return {"status": "ok"}, 200

@app.route("/healthz")
def healthz():
    return {"status": "ok"}, 200

@app.route("/webhook/telegram-webhook", methods=["POST", "GET"])
def telegram_webhook_placeholder():
    return {"ok": True}, 200

def run_telegram():
    try:
        log.info("Starting Telegram bot...")
        from telegram_bot import main as telegram_main
        telegram_main()
    except Exception as e:
        log.error(f"Telegram bot error: {e}")

def run_social():
    try:
        log.info("Starting Social agent...")
        from social_agent import start as social_start
        social_start()
    except Exception as e:
        log.error(f"Social agent error: {e}")

if __name__ == "__main__":
    # Start background agents after short delay
    def start_agents():
        import time
        time.sleep(3)
        t1 = threading.Thread(target=run_telegram, daemon=True)
        t1.start()
        if os.environ.get("META_PAGE_ACCESS_TOKEN"):
            t2 = threading.Thread(target=run_social, daemon=True)
            t2.start()

    threading.Thread(target=start_agents, daemon=True).start()

    # Flask starts immediately so Railway healthcheck passes
    PORT = int(os.environ.get("PORT", 8080))
    log.info(f"Starting health server on port {PORT}")
    app.run(host="0.0.0.0", port=PORT, debug=False)
