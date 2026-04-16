"""
IELTS Master — Complete Social Media Automation Stack v3
100% working on Railway. Flask starts instantly. No import-time side effects.

Handles:
- Telegram: DMs, group mentions, voice commands (Jarvis), scheduled posts
- Facebook: page comments, DMs, scheduled posts
- Instagram: comments, image posts, Reels via Cloudinary URL
- Twitter/X: mention monitoring, daily posts
- Reddit: keyword monitoring, draft replies
- Jarvis: natural language control via Telegram voice/text
"""

import os, json, logging, threading, time, requests, telebot
from flask import Flask, request, jsonify
from brain import get_reply, generate_post, jarvis_command

# ── Logging ───────────────────────────────────────────────────────────────────
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("app")

# ── Config ────────────────────────────────────────────────────────────────────
TG_TOKEN       = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TG_CHANNEL_MN  = os.environ.get("TELEGRAM_CHANNEL_MN", "")
TG_CHANNEL_KZ  = os.environ.get("TELEGRAM_CHANNEL_KZ", "")
TG_CHANNEL_UZ  = os.environ.get("TELEGRAM_CHANNEL_UZ", "")
TG_OWNER_ID    = os.environ.get("TELEGRAM_OWNER_ID", "")   # Your personal Telegram ID for Jarvis

META_TOKEN     = os.environ.get("META_PAGE_ACCESS_TOKEN", "")
META_PAGE_ID   = os.environ.get("META_PAGE_ID", "")
META_IG_ID     = os.environ.get("META_IG_USER_ID", "")
META_VERIFY    = os.environ.get("META_WEBHOOK_VERIFY_TOKEN", "ieltsmaster2026")

TW_KEY         = os.environ.get("TWITTER_API_KEY", "")
TW_SECRET      = os.environ.get("TWITTER_API_SECRET", "")
TW_AT          = os.environ.get("TWITTER_ACCESS_TOKEN", "")
TW_ATS         = os.environ.get("TWITTER_ACCESS_SECRET", "")
TW_BEARER      = os.environ.get("TWITTER_BEARER_TOKEN", "")
TW_USER_ID     = os.environ.get("TWITTER_USER_ID", "")

RD_ID          = os.environ.get("REDDIT_CLIENT_ID", "")
RD_SECRET      = os.environ.get("REDDIT_CLIENT_SECRET", "")
RD_USER        = os.environ.get("REDDIT_USERNAME", "")
RD_PASS        = os.environ.get("REDDIT_PASSWORD", "")

RAILWAY_URL    = os.environ.get("RAILWAY_PUBLIC_DOMAIN", "")
GRAPH          = "https://graph.facebook.com/v19.0"

# ── Flask app — created immediately ──────────────────────────────────────────
app = Flask(__name__)

# ── Health endpoints — these answer INSTANTLY ─────────────────────────────────
@app.route("/")
@app.route("/health")
@app.route("/healthz")
def health():
    return jsonify({"status": "ok", "service": "IELTS Master"}), 200

# ── Telegram bot setup ────────────────────────────────────────────────────────
bot = telebot.TeleBot(TG_TOKEN, threaded=False) if TG_TOKEN else None

def is_owner(message) -> bool:
    owner_id = os.environ.get("TELEGRAM_OWNER_ID", "").strip()
    if not owner_id:
        return False
    return str(message.from_user.id) == owner_id

if bot:
    # /start command
    @bot.message_handler(commands=["start"])
    def tg_start(msg):
        bot.reply_to(msg,
            "Сайн байна уу! IELTS Master-д тавтай морил.\n"
            "Бичгийн даалгавраа сайжруулахад туслая!\n\n"
            "🌐 ieltsmaster.org — үнэгүй эхлэх"
        )

    # Jarvis voice command — only for owner
    @bot.message_handler(content_types=["voice"])
    def tg_voice(msg):
        if not is_owner(msg):
            return
        # Download voice file
        try:
            file_info = bot.get_file(msg.voice.file_id)
            file_url = f"https://api.telegram.org/file/bot{TG_TOKEN}/{file_info.file_path}"
            # For now respond that voice received — transcription needs Whisper API
            bot.reply_to(msg,
                "🎤 Voice received. To enable full voice transcription, add OPENAI_API_KEY "
                "to Railway variables. For now, send text commands to Jarvis."
            )
        except Exception as e:
            log.error(f"Voice error: {e}")

    # Jarvis text command — only for owner, starts with /jarvis or "jarvis"
    @bot.message_handler(
        func=lambda m: is_owner(m) and m.text and
        (m.text.lower().startswith("jarvis") or m.text.startswith("/jarvis"))
    )
    def tg_jarvis(msg):
        command = msg.text.replace("/jarvis", "").replace("jarvis", "").strip()
        if not command:
            bot.reply_to(msg, "Ready. Give me a command.")
            return
        bot.send_chat_action(msg.chat.id, "typing")
        response = jarvis_command(command)
        # Split long responses
        if len(response) <= 4096:
            bot.reply_to(msg, response)
        else:
            for i in range(0, len(response), 4096):
                bot.send_message(msg.chat.id, response[i:i+4096])
        log.info(f"Jarvis command: {command[:60]}")

    # Regular text messages — reply as IELTS Master agent
    @bot.message_handler(func=lambda m: True, content_types=["text"])
    def tg_message(msg):
        text = msg.text or ""
        chat_id = msg.chat.id
        chat_type = msg.chat.type

        # In groups: only reply when mentioned or reply to bot
        if chat_type in ("group", "supergroup"):
            try:
                me = bot.get_me()
                mention = f"@{me.username}"
                is_reply = (
                    msg.reply_to_message and
                    msg.reply_to_message.from_user and
                    msg.reply_to_message.from_user.id == me.id
                )
                if mention not in text and not is_reply:
                    return
                text = text.replace(mention, "").strip()
            except Exception:
                return

        if not text:
            return

        try:
            bot.send_chat_action(chat_id, "typing")
        except Exception:
            pass

        result = get_reply("telegram", text)
        if not result["skip"] and result["reply"]:
            try:
                bot.reply_to(msg, result["reply"])
            except Exception as e:
                log.error(f"TG reply failed: {e}")

# ── Telegram webhook endpoint ─────────────────────────────────────────────────
@app.route("/webhook/telegram", methods=["POST"])
def tg_webhook():
    if not bot:
        return jsonify({"ok": True}), 200
    try:
        update = telebot.types.Update.de_json(request.get_data(as_text=True))
        bot.process_new_updates([update])
    except Exception as e:
        log.error(f"TG webhook error: {e}")
    return jsonify({"ok": True}), 200

# ── Facebook webhooks ─────────────────────────────────────────────────────────
@app.route("/webhook/facebook", methods=["GET"])
def fb_verify():
    if request.args.get("hub.verify_token") == META_VERIFY:
        return request.args.get("hub.challenge", ""), 200
    return "Forbidden", 403

@app.route("/webhook/facebook", methods=["POST"])
def fb_event():
    data = request.json or {}
    for entry in data.get("entry", []):
        for change in entry.get("changes", []):
            if change.get("field") == "feed":
                val = change.get("value", {})
                if val.get("item") == "comment" and val.get("verb") == "add":
                    text = val.get("message", "")
                    cid  = val.get("comment_id", "")
                    sid  = val.get("from", {}).get("id", "")
                    if text and sid != META_PAGE_ID:
                        result = get_reply("facebook", text)
                        if not result["skip"] and result["reply"] and META_TOKEN and cid:
                            requests.post(
                                f"{GRAPH}/{cid}/comments",
                                params={"access_token": META_TOKEN},
                                json={"message": result["reply"]},
                                timeout=10
                            )
        for msg_event in entry.get("messaging", []):
            if "message" in msg_event:
                sender = msg_event["sender"]["id"]
                text   = msg_event.get("message", {}).get("text", "")
                if text and sender != META_PAGE_ID and META_TOKEN:
                    result = get_reply("facebook", text)
                    if not result["skip"] and result["reply"]:
                        requests.post(
                            f"{GRAPH}/me/messages",
                            params={"access_token": META_TOKEN},
                            json={"recipient":{"id":sender},"message":{"text":result["reply"]}},
                            timeout=10
                        )
    return jsonify({"ok": True}), 200

# ── Instagram webhooks ────────────────────────────────────────────────────────
@app.route("/webhook/instagram", methods=["GET"])
def ig_verify():
    if request.args.get("hub.verify_token") == META_VERIFY:
        return request.args.get("hub.challenge", ""), 200
    return "Forbidden", 403

@app.route("/webhook/instagram", methods=["POST"])
def ig_event():
    data = request.json or {}
    for entry in data.get("entry", []):
        for change in entry.get("changes", []):
            if change.get("field") == "comments":
                val  = change.get("value", {})
                text = val.get("text", "")
                cid  = val.get("id", "")
                if text and META_TOKEN and cid:
                    result = get_reply("instagram", text)
                    if not result["skip"] and result["reply"]:
                        requests.post(
                            f"{GRAPH}/{cid}/replies",
                            params={"access_token": META_TOKEN},
                            json={"message": result["reply"]},
                            timeout=10
                        )
    return jsonify({"ok": True}), 200

# ── Posting helpers ───────────────────────────────────────────────────────────
def send_telegram(chat_id: str, text: str) -> bool:
    if not TG_TOKEN or not chat_id or not text:
        return False
    r = requests.post(
        f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage",
        json={"chat_id": chat_id, "text": text},
        timeout=15
    )
    ok = r.ok and r.json().get("ok")
    log.info(f"TG post {'ok' if ok else 'FAILED'}: {chat_id}")
    return ok

def post_fb(text: str) -> str | None:
    if not META_TOKEN or not META_PAGE_ID or not text:
        return None
    r = requests.post(
        f"{GRAPH}/{META_PAGE_ID}/feed",
        data={"message": text, "access_token": META_TOKEN},
        timeout=15
    )
    pid = r.json().get("id") if r.ok else None
    log.info(f"FB post {'ok: ' + str(pid) if pid else 'FAILED'}")
    return pid

def post_ig_image(image_url: str, caption: str) -> str | None:
    """Post image to Instagram. image_url must be public HTTPS."""
    if not META_TOKEN or not META_IG_ID:
        return None
    r = requests.post(
        f"{GRAPH}/{META_IG_ID}/media",
        params={"image_url": image_url, "caption": caption, "access_token": META_TOKEN},
        timeout=15
    )
    if not r.ok:
        log.error(f"IG image container failed: {r.text[:100]}")
        return None
    cid = r.json().get("id")
    r2 = requests.post(
        f"{GRAPH}/{META_IG_ID}/media_publish",
        params={"creation_id": cid, "access_token": META_TOKEN},
        timeout=15
    )
    mid = r2.json().get("id") if r2.ok else None
    log.info(f"IG image {'published: ' + str(mid) if mid else 'FAILED'}")
    return mid

def post_ig_reel(video_url: str, caption: str) -> str | None:
    """
    Post Reel to Instagram.
    video_url: public HTTPS mp4 (upload to Cloudinary first).
    Requirements: H.264, 3-90 seconds, 9:16 ratio recommended.
    """
    if not META_TOKEN or not META_IG_ID:
        return None
    r = requests.post(
        f"{GRAPH}/{META_IG_ID}/media",
        params={
            "media_type": "REELS",
            "video_url": video_url,
            "caption": caption,
            "share_to_feed": "true",
            "access_token": META_TOKEN,
        },
        timeout=30
    )
    if not r.ok:
        log.error(f"IG reel container failed: {r.text[:100]}")
        return None
    cid = r.json().get("id")
    log.info(f"IG reel container: {cid} — polling...")
    for attempt in range(18):  # max 3 min
        time.sleep(10)
        sr = requests.get(
            f"{GRAPH}/{cid}",
            params={"fields": "status_code", "access_token": META_TOKEN},
            timeout=15
        )
        status = sr.json().get("status_code", "")
        log.info(f"IG reel status: {status} ({attempt+1}/18)")
        if status == "FINISHED":
            break
        if status == "ERROR":
            log.error("IG reel processing failed")
            return None
    r3 = requests.post(
        f"{GRAPH}/{META_IG_ID}/media_publish",
        params={"creation_id": cid, "access_token": META_TOKEN},
        timeout=15
    )
    mid = r3.json().get("id") if r3.ok else None
    log.info(f"IG reel {'published: ' + str(mid) if mid else 'FAILED'}")
    return mid

def post_tweet(text: str) -> None:
    if not all([TW_KEY, TW_SECRET, TW_AT, TW_ATS]):
        return
    try:
        import tweepy
        tw = tweepy.Client(
            consumer_key=TW_KEY, consumer_secret=TW_SECRET,
            access_token=TW_AT, access_token_secret=TW_ATS
        )
        tw.create_tweet(text=text[:280])
        log.info("Tweet posted")
    except Exception as e:
        log.error(f"Tweet failed: {e}")

# ── Manual trigger endpoints ──────────────────────────────────────────────────
@app.route("/post/reel", methods=["POST"])
def trigger_reel():
    """POST {"video_url":"...","caption":"..."} — posts reel to Instagram."""
    data = request.json or {}
    url  = data.get("video_url", "")
    cap  = data.get("caption", "") or generate_post("instagram", "demo").get("post", "")
    if not url:
        return jsonify({"error": "video_url required"}), 400
    mid = post_ig_reel(url, cap)
    return jsonify({"ok": bool(mid), "media_id": mid}), (200 if mid else 500)

@app.route("/post/instagram", methods=["POST"])
def trigger_ig_image():
    """POST {"image_url":"...","caption":"..."}"""
    data = request.json or {}
    url  = data.get("image_url", "")
    cap  = data.get("caption", "") or generate_post("instagram", "tip").get("post", "")
    if not url:
        return jsonify({"error": "image_url required"}), 400
    mid = post_ig_image(url, cap)
    return jsonify({"ok": bool(mid), "media_id": mid}), (200 if mid else 500)

@app.route("/post/facebook", methods=["POST"])
def trigger_fb():
    """POST {"text":"..."} or leave empty for auto-generated."""
    data = request.json or {}
    text = data.get("text", "") or generate_post("facebook", data.get("type","tip")).get("post","")
    pid = post_fb(text)
    return jsonify({"ok": bool(pid), "post_id": pid}), (200 if pid else 500)

@app.route("/post/telegram", methods=["POST"])
def trigger_tg():
    """POST {"chat_id":"...","text":"...","type":"tip"}"""
    data    = request.json or {}
    chat_id = data.get("chat_id", TG_CHANNEL_MN)
    lang    = data.get("lang", "telegram_mn")
    text    = data.get("text", "") or generate_post(lang, data.get("type","tip")).get("post","")
    ok = send_telegram(chat_id, text)
    return jsonify({"ok": ok}), (200 if ok else 500)

@app.route("/jarvis", methods=["POST"])
def jarvis_api():
    """POST {"command":"write a flash sale post"} — Jarvis HTTP API."""
    data    = request.json or {}
    command = data.get("command", "")
    if not command:
        return jsonify({"error": "command required"}), 400
    response = jarvis_command(command, data.get("context", ""))
    return jsonify({"response": response}), 200

# ── Scheduler jobs ────────────────────────────────────────────────────────────
def job_daily_mn():
    r = generate_post("telegram_mn", "tip")
    if r.get("post") and TG_CHANNEL_MN:
        send_telegram(TG_CHANNEL_MN, r["post"])

def job_daily_kz():
    r = generate_post("telegram_kz", "tip")
    if r.get("post") and TG_CHANNEL_KZ:
        send_telegram(TG_CHANNEL_KZ, r["post"])

def job_daily_uz():
    r = generate_post("telegram_uz", "tip")
    if r.get("post") and TG_CHANNEL_UZ:
        send_telegram(TG_CHANNEL_UZ, r["post"])

def job_weekly_challenge():
    for ch, lang in [(TG_CHANNEL_MN,"telegram_mn"),(TG_CHANNEL_KZ,"telegram_kz"),(TG_CHANNEL_UZ,"telegram_uz")]:
        if ch:
            r = generate_post(lang, "challenge")
            if r.get("post"):
                send_telegram(ch, r["post"])

def job_facebook_daily():
    r = generate_post("facebook", "tip")
    if r.get("post"):
        post_fb(r["post"])

def job_instagram_caption():
    r = generate_post("instagram", "tip")
    if r.get("post"):
        log.info(f"=== IG CAPTION ===\n{r['post']}\n=== END ===")
        # To auto-post: post_ig_image(YOUR_IMAGE_URL, r["post"])

def job_twitter_daily():
    r = generate_post("twitter", "tip")
    if r.get("post"):
        post_tweet(r["post"])

_replied_tweets  = set()
_replied_reddit  = set()
REDDIT_KEYWORDS  = ["ielts writing","band score","task 2","ielts prep","ielts ai","ielts band 7"]
REDDIT_SUBS      = ["learnEnglish","Mongolia","Kazakhstan","Uzbekistan","studyAbroad"]
REDDIT_DRAFTS    = "/tmp/reddit_drafts.jsonl"

def job_check_twitter():
    if not all([TW_KEY, TW_SECRET, TW_AT, TW_ATS, TW_USER_ID]):
        return
    try:
        import tweepy
        tw = tweepy.Client(
            bearer_token=TW_BEARER,
            consumer_key=TW_KEY, consumer_secret=TW_SECRET,
            access_token=TW_AT, access_token_secret=TW_ATS,
            wait_on_rate_limit=True
        )
        mentions = tw.get_users_mentions(id=TW_USER_ID, max_results=10, tweet_fields=["text"])
        if not mentions.data:
            return
        for tweet in mentions.data:
            if tweet.id in _replied_tweets:
                continue
            result = get_reply("twitter", tweet.text)
            if not result["skip"] and result["reply"]:
                tw.create_tweet(text=result["reply"][:280], in_reply_to_tweet_id=tweet.id)
                _replied_tweets.add(tweet.id)
                log.info(f"Twitter replied: {tweet.id}")
    except Exception as e:
        log.error(f"Twitter check failed: {e}")

def job_check_reddit():
    if not all([RD_ID, RD_SECRET, RD_USER, RD_PASS]):
        return
    try:
        import praw
        reddit = praw.Reddit(
            client_id=RD_ID, client_secret=RD_SECRET,
            username=RD_USER, password=RD_PASS,
            user_agent="IELTSMasterMonitor/1.0"
        )
        for sub_name in REDDIT_SUBS:
            for comment in reddit.subreddit(sub_name).comments(limit=20):
                if comment.id in _replied_reddit:
                    continue
                if any(kw in comment.body.lower() for kw in REDDIT_KEYWORDS):
                    _replied_reddit.add(comment.id)
                    result = get_reply("reddit", comment.body)
                    if not result["skip"] and result["reply"]:
                        with open(REDDIT_DRAFTS, "a") as f:
                            f.write(json.dumps({
                                "id": comment.id, "sub": sub_name,
                                "original": comment.body[:200],
                                "draft_reply": result["reply"],
                                "url": f"https://reddit.com{comment.permalink}"
                            }) + "\n")
                        log.info(f"Reddit draft: r/{sub_name}")
            time.sleep(2)
    except Exception as e:
        log.error(f"Reddit check failed: {e}")

# ── Startup — runs in background AFTER Flask binds ────────────────────────────
_started = False

def _startup():
    """Runs once after gunicorn binds. Flask healthcheck is already answering."""
    global _started
    if _started:
        return
    _started = True

    # Register Telegram webhook
    if TG_TOKEN and RAILWAY_URL:
        webhook_url = f"https://{RAILWAY_URL}/webhook/telegram"
        try:
            r = requests.get(
                f"https://api.telegram.org/bot{TG_TOKEN}/setWebhook",
                params={"url": webhook_url}, timeout=10
            )
            if r.ok and r.json().get("ok"):
                log.info(f"Telegram webhook set: {webhook_url}")
            else:
                log.error(f"Telegram webhook failed: {r.text}")
        except Exception as e:
            log.error(f"Webhook registration error: {e}")

    # Start scheduler
    from apscheduler.schedulers.background import BackgroundScheduler
    scheduler = BackgroundScheduler(timezone="Asia/Ulaanbaatar")
    scheduler.add_job(job_daily_mn,          "cron", hour=9,  minute=0)
    scheduler.add_job(job_daily_kz,          "cron", hour=9,  minute=0,  timezone="Asia/Almaty")
    scheduler.add_job(job_daily_uz,          "cron", hour=9,  minute=0,  timezone="Asia/Tashkent")
    scheduler.add_job(job_weekly_challenge,  "cron", day_of_week="mon", hour=10, minute=0)
    scheduler.add_job(job_facebook_daily,    "cron", hour=9,  minute=30)
    scheduler.add_job(job_instagram_caption, "cron", hour=10, minute=0)
    scheduler.add_job(job_twitter_daily,     "cron", hour=8,  minute=0)
    scheduler.add_job(job_check_twitter,     "interval", minutes=15)
    scheduler.add_job(job_check_reddit,      "interval", minutes=30)
    scheduler.start()
    log.info("Scheduler running — all jobs active")

# Hook startup to first request so Flask is fully bound first
@app.before_request
def before_first():
    if not _started:
        t = threading.Thread(target=_startup, daemon=True)
        t.start()

if __name__ == "__main__":
    PORT = int(os.environ.get("PORT", 8080))
    log.info(f"Starting on port {PORT}")
    app.run(host="0.0.0.0", port=PORT, debug=False, use_reloader=False)
