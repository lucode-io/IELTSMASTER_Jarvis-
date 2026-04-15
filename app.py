"""
IELTS Master — Main Flask Application
Single file that does everything:
  - Health check endpoint (Railway needs this)
  - Telegram webhook (receives every DM and group message)
  - Facebook webhook (receives page comments + DMs)
  - Instagram webhook (receives comments)
  - APScheduler: daily posts to all Telegram channels
  - APScheduler: daily Facebook page post
  - APScheduler: daily Instagram caption generation
  - Twitter: monitors mentions every 15 min + auto-reply
  - Reddit: monitors keywords every 30 min + saves draft replies

Deploy on Railway. Set all env vars in Railway Variables tab.
"""

import os
import json
import logging
import requests
import telebot

from flask import Flask, request, jsonify
from apscheduler.schedulers.background import BackgroundScheduler
from brain import get_reply, generate_post

# ── Logging ───────────────────────────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s"
)
log = logging.getLogger("app")

# ── Environment variables ─────────────────────────────────────────────────────

TG_TOKEN          = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TG_CHANNEL_MN     = os.environ.get("TELEGRAM_CHANNEL_MN", "")
TG_CHANNEL_KZ     = os.environ.get("TELEGRAM_CHANNEL_KZ", "")
TG_CHANNEL_UZ     = os.environ.get("TELEGRAM_CHANNEL_UZ", "")

META_PAGE_TOKEN   = os.environ.get("META_PAGE_ACCESS_TOKEN", "")
META_PAGE_ID      = os.environ.get("META_PAGE_ID", "")
META_IG_USER_ID   = os.environ.get("META_IG_USER_ID", "")
META_VERIFY_TOKEN = os.environ.get("META_WEBHOOK_VERIFY_TOKEN", "ieltsmaster2026")

TWITTER_KEY       = os.environ.get("TWITTER_API_KEY", "")
TWITTER_SECRET    = os.environ.get("TWITTER_API_SECRET", "")
TWITTER_AT        = os.environ.get("TWITTER_ACCESS_TOKEN", "")
TWITTER_ATS       = os.environ.get("TWITTER_ACCESS_SECRET", "")
TWITTER_BEARER    = os.environ.get("TWITTER_BEARER_TOKEN", "")
TWITTER_USER_ID   = os.environ.get("TWITTER_USER_ID", "")

REDDIT_CLIENT_ID  = os.environ.get("REDDIT_CLIENT_ID", "")
REDDIT_SECRET     = os.environ.get("REDDIT_CLIENT_SECRET", "")
REDDIT_USERNAME   = os.environ.get("REDDIT_USERNAME", "")
REDDIT_PASSWORD   = os.environ.get("REDDIT_PASSWORD", "")

RAILWAY_URL       = os.environ.get("RAILWAY_PUBLIC_DOMAIN", "")

GRAPH = "https://graph.facebook.com/v19.0"

# ── Telegram bot ──────────────────────────────────────────────────────────────

bot = telebot.TeleBot(TG_TOKEN, threaded=False) if TG_TOKEN else None

if bot:
    @bot.message_handler(commands=["start"])
    def tg_start(message):
        bot.reply_to(
            message,
            "Сайн байна уу! IELTS Master-д тавтай морил.\n"
            "Бичгийн даалгавраа сайжруулахад туслая!\n\n"
            "🌐 ieltsmaster.org — үнэгүй эхлэх"
        )

    @bot.message_handler(func=lambda m: True, content_types=["text"])
    def tg_message(message):
        text = message.text or ""
        chat_id = message.chat.id
        chat_type = message.chat.type

        # In groups: only reply when bot is mentioned or it's a reply to bot
        if chat_type in ("group", "supergroup"):
            bot_info = bot.get_me()
            mention = f"@{bot_info.username}"
            is_reply_to_bot = (
                message.reply_to_message and
                message.reply_to_message.from_user and
                message.reply_to_message.from_user.id == bot_info.id
            )
            if mention not in text and not is_reply_to_bot:
                return
            text = text.replace(mention, "").strip()

        if not text:
            return

        try:
            bot.send_chat_action(chat_id, "typing")
        except Exception:
            pass

        result = get_reply("telegram", text)
        if not result["skip"] and result["reply"]:
            try:
                bot.reply_to(message, result["reply"])
                log.info(f"TG reply sent — intent={result['intent']} chat={chat_id}")
            except Exception as e:
                log.error(f"TG send failed: {e}")

# ── Flask app ─────────────────────────────────────────────────────────────────

app = Flask(__name__)

# Health check — Railway pings this to confirm service is alive
@app.route("/")
@app.route("/health")
@app.route("/healthz")
def health():
    return jsonify({"status": "ok", "service": "IELTS Master Agent"}), 200

# ── Telegram webhook endpoint ─────────────────────────────────────────────────

@app.route("/webhook/telegram", methods=["POST"])
def telegram_webhook():
    if not bot:
        return jsonify({"ok": True}), 200
    try:
        json_str = request.get_data(as_text=True)
        update = telebot.types.Update.de_json(json_str)
        bot.process_new_updates([update])
    except Exception as e:
        log.error(f"Telegram webhook error: {e}")
    return jsonify({"ok": True}), 200

# ── Facebook webhook endpoints ────────────────────────────────────────────────

@app.route("/webhook/facebook", methods=["GET"])
def fb_verify():
    mode      = request.args.get("hub.mode")
    token     = request.args.get("hub.verify_token")
    challenge = request.args.get("hub.challenge")
    if mode == "subscribe" and token == META_VERIFY_TOKEN:
        log.info("Facebook webhook verified")
        return challenge, 200
    return "Forbidden", 403

@app.route("/webhook/facebook", methods=["POST"])
def fb_event():
    data = request.json or {}
    for entry in data.get("entry", []):
        # Page comments
        for change in entry.get("changes", []):
            field = change.get("field", "")
            val   = change.get("value", {})
            if field == "feed" and val.get("item") == "comment" and val.get("verb") == "add":
                _handle_fb_comment(val)
        # Messenger DMs
        for msg_event in entry.get("messaging", []):
            if "message" in msg_event:
                _handle_fb_dm(msg_event)
    return jsonify({"ok": True}), 200

def _handle_fb_comment(val):
    comment_id = val.get("comment_id")
    text       = val.get("message", "")
    sender_id  = val.get("from", {}).get("id", "")
    if not text or sender_id == META_PAGE_ID:
        return
    log.info(f"FB comment: {text[:60]}")
    result = get_reply("facebook", text)
    if not result["skip"] and result["reply"]:
        _fb_reply_comment(comment_id, result["reply"])

def _handle_fb_dm(evt):
    sender_id = evt.get("sender", {}).get("id", "")
    text      = evt.get("message", {}).get("text", "")
    if not text or sender_id == META_PAGE_ID:
        return
    log.info(f"FB DM from {sender_id}: {text[:60]}")
    result = get_reply("facebook", text)
    if not result["skip"] and result["reply"]:
        _fb_send_dm(sender_id, result["reply"])

def _fb_reply_comment(comment_id, text):
    if not META_PAGE_TOKEN or not comment_id:
        return
    r = requests.post(
        f"{GRAPH}/{comment_id}/comments",
        params={"access_token": META_PAGE_TOKEN},
        json={"message": text},
        timeout=10
    )
    if r.ok:
        log.info(f"FB comment replied: {comment_id}")
    else:
        log.error(f"FB comment reply failed: {r.status_code} {r.text[:100]}")

def _fb_send_dm(recipient_id, text):
    if not META_PAGE_TOKEN:
        return
    r = requests.post(
        f"{GRAPH}/me/messages",
        params={"access_token": META_PAGE_TOKEN},
        json={"recipient": {"id": recipient_id}, "message": {"text": text}},
        timeout=10
    )
    if r.ok:
        log.info(f"FB DM sent to {recipient_id}")
    else:
        log.error(f"FB DM failed: {r.status_code} {r.text[:100]}")

# ── Instagram webhook endpoints ───────────────────────────────────────────────

@app.route("/webhook/instagram", methods=["GET"])
def ig_verify():
    mode      = request.args.get("hub.mode")
    token     = request.args.get("hub.verify_token")
    challenge = request.args.get("hub.challenge")
    if mode == "subscribe" and token == META_VERIFY_TOKEN:
        log.info("Instagram webhook verified")
        return challenge, 200
    return "Forbidden", 403

@app.route("/webhook/instagram", methods=["POST"])
def ig_event():
    data = request.json or {}
    for entry in data.get("entry", []):
        for change in entry.get("changes", []):
            if change.get("field") == "comments":
                val        = change.get("value", {})
                comment_id = val.get("id", "")
                text       = val.get("text", "")
                if text:
                    log.info(f"IG comment: {text[:60]}")
                    result = get_reply("instagram", text)
                    if not result["skip"] and result["reply"]:
                        _ig_reply_comment(comment_id, result["reply"])
    return jsonify({"ok": True}), 200

def _ig_reply_comment(comment_id, text):
    if not META_PAGE_TOKEN or not comment_id:
        return
    r = requests.post(
        f"{GRAPH}/{comment_id}/replies",
        params={"access_token": META_PAGE_TOKEN},
        json={"message": text},
        timeout=10
    )
    if r.ok:
        log.info(f"IG comment replied: {comment_id}")
    else:
        log.error(f"IG reply failed: {r.status_code} {r.text[:100]}")

# ── Posting functions ─────────────────────────────────────────────────────────

def post_telegram(chat_id: str, text: str) -> bool:
    """Send a message to a Telegram chat/channel."""
    if not TG_TOKEN or not chat_id or not text:
        return False
    r = requests.post(
        f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage",
        json={"chat_id": chat_id, "text": text},
        timeout=15
    )
    ok = r.ok and r.json().get("ok")
    if ok:
        log.info(f"TG posted to {chat_id}")
    else:
        log.error(f"TG post failed: {r.text[:100]}")
    return ok

def post_facebook(text: str, link: str = None) -> str | None:
    """Post to Facebook Page. Returns post ID or None."""
    if not META_PAGE_TOKEN or not META_PAGE_ID or not text:
        return None
    payload = {"message": text, "access_token": META_PAGE_TOKEN}
    if link:
        payload["link"] = link
    r = requests.post(f"{GRAPH}/{META_PAGE_ID}/feed", data=payload, timeout=15)
    if r.ok:
        post_id = r.json().get("id")
        log.info(f"FB post published: {post_id}")
        return post_id
    else:
        log.error(f"FB post failed: {r.status_code} {r.text[:100]}")
        return None

def post_instagram_image(image_url: str, caption: str) -> str | None:
    """Post an image to Instagram. image_url must be a public HTTPS URL."""
    if not META_PAGE_TOKEN or not META_IG_USER_ID:
        return None
    # Step 1: create container
    r = requests.post(
        f"{GRAPH}/{META_IG_USER_ID}/media",
        params={
            "image_url": image_url,
            "caption": caption,
            "access_token": META_PAGE_TOKEN,
        },
        timeout=15
    )
    if not r.ok:
        log.error(f"IG image container failed: {r.text[:100]}")
        return None
    container_id = r.json().get("id")
    # Step 2: publish
    r2 = requests.post(
        f"{GRAPH}/{META_IG_USER_ID}/media_publish",
        params={"creation_id": container_id, "access_token": META_PAGE_TOKEN},
        timeout=15
    )
    if r2.ok:
        media_id = r2.json().get("id")
        log.info(f"IG image published: {media_id}")
        return media_id
    else:
        log.error(f"IG image publish failed: {r2.text[:100]}")
        return None

def post_instagram_reel(video_url: str, caption: str) -> str | None:
    """
    Post a Reel to Instagram.
    video_url must be a publicly accessible HTTPS .mp4 URL (e.g. Cloudinary).
    Video requirements: H.264, max 90 seconds, min 3 seconds, 9:16 aspect ratio recommended.
    """
    if not META_PAGE_TOKEN or not META_IG_USER_ID:
        log.warning("IG Reel skipped — missing credentials")
        return None

    import time

    # Step 1: create container
    r = requests.post(
        f"{GRAPH}/{META_IG_USER_ID}/media",
        params={
            "media_type": "REELS",
            "video_url": video_url,
            "caption": caption,
            "share_to_feed": "true",
            "access_token": META_PAGE_TOKEN,
        },
        timeout=30
    )
    if not r.ok:
        log.error(f"IG Reel container failed: {r.text[:100]}")
        return None

    container_id = r.json().get("id")
    log.info(f"IG Reel container created: {container_id} — polling status...")

    # Step 2: poll until video is processed (max 3 min)
    for attempt in range(18):
        time.sleep(10)
        status_r = requests.get(
            f"{GRAPH}/{container_id}",
            params={"fields": "status_code", "access_token": META_PAGE_TOKEN},
            timeout=15
        )
        status = status_r.json().get("status_code", "")
        log.info(f"IG Reel status: {status} (attempt {attempt + 1})")
        if status == "FINISHED":
            break
        if status == "ERROR":
            log.error("IG Reel processing failed")
            return None

    # Step 3: publish
    r3 = requests.post(
        f"{GRAPH}/{META_IG_USER_ID}/media_publish",
        params={"creation_id": container_id, "access_token": META_PAGE_TOKEN},
        timeout=15
    )
    if r3.ok:
        media_id = r3.json().get("id")
        log.info(f"IG Reel published: {media_id}")
        return media_id
    else:
        log.error(f"IG Reel publish failed: {r3.text[:100]}")
        return None

# Manual trigger endpoint — call from command center to post a reel now
@app.route("/post/reel", methods=["POST"])
def trigger_reel():
    """
    POST body: {"video_url": "https://...", "caption": "..."}
    Used by the Command Center to post a reel without touching code.
    """
    data      = request.json or {}
    video_url = data.get("video_url", "")
    caption   = data.get("caption", "")
    if not video_url:
        return jsonify({"error": "video_url required"}), 400
    if not caption:
        result = generate_post("instagram", "demo")
        caption = result.get("post", "")
    media_id = post_instagram_reel(video_url, caption)
    if media_id:
        return jsonify({"ok": True, "media_id": media_id}), 200
    return jsonify({"ok": False, "error": "post failed"}), 500

# Manual trigger for Facebook post
@app.route("/post/facebook", methods=["POST"])
def trigger_facebook():
    data = request.json or {}
    text = data.get("text", "")
    if not text:
        result = generate_post("facebook", data.get("type", "tip"))
        text = result.get("post", "")
    post_id = post_facebook(text)
    if post_id:
        return jsonify({"ok": True, "post_id": post_id}), 200
    return jsonify({"ok": False}), 500

# Manual trigger for Telegram post
@app.route("/post/telegram", methods=["POST"])
def trigger_telegram():
    data    = request.json or {}
    chat_id = data.get("chat_id", TG_CHANNEL_MN)
    text    = data.get("text", "")
    if not text:
        result = generate_post("telegram_mn", data.get("type", "tip"))
        text = result.get("post", "")
    ok = post_telegram(chat_id, text)
    return jsonify({"ok": ok}), 200 if ok else 500

# ── Twitter / X monitoring ────────────────────────────────────────────────────

_replied_tweets = set()

def check_twitter():
    """Check for new mentions and auto-reply. Runs every 15 min."""
    if not all([TWITTER_KEY, TWITTER_SECRET, TWITTER_AT, TWITTER_ATS, TWITTER_USER_ID]):
        return
    try:
        import tweepy
        tw = tweepy.Client(
            bearer_token=TWITTER_BEARER,
            consumer_key=TWITTER_KEY,
            consumer_secret=TWITTER_SECRET,
            access_token=TWITTER_AT,
            access_token_secret=TWITTER_ATS,
            wait_on_rate_limit=True
        )
        mentions = tw.get_users_mentions(
            id=TWITTER_USER_ID,
            max_results=10,
            tweet_fields=["text"]
        )
        if not mentions.data:
            return
        for tweet in mentions.data:
            if tweet.id in _replied_tweets:
                continue
            log.info(f"Twitter mention: {tweet.text[:60]}")
            result = get_reply("twitter", tweet.text)
            if not result["skip"] and result["reply"]:
                tw.create_tweet(
                    text=result["reply"][:280],
                    in_reply_to_tweet_id=tweet.id
                )
                _replied_tweets.add(tweet.id)
                log.info(f"Twitter replied to {tweet.id}")
    except Exception as e:
        log.error(f"Twitter check failed: {e}")

def post_tweet(text: str):
    """Post a tweet."""
    if not all([TWITTER_KEY, TWITTER_SECRET, TWITTER_AT, TWITTER_ATS]):
        return
    try:
        import tweepy
        tw = tweepy.Client(
            consumer_key=TWITTER_KEY,
            consumer_secret=TWITTER_SECRET,
            access_token=TWITTER_AT,
            access_token_secret=TWITTER_ATS
        )
        r = tw.create_tweet(text=text[:280])
        log.info(f"Tweet posted: {r.data['id']}")
    except Exception as e:
        log.error(f"Tweet failed: {e}")

# ── Reddit monitoring ─────────────────────────────────────────────────────────

REDDIT_KEYWORDS = [
    "ielts writing", "band score", "task 2", "task2",
    "ielts prep", "ielts tool", "ielts ai", "ielts band 7",
]
REDDIT_SUBS = [
    "learnEnglish", "Mongolia", "Kazakhstan",
    "Uzbekistan", "studyAbroad",
]
REDDIT_DRAFTS = "/tmp/reddit_drafts.jsonl"
_replied_reddit = set()

def check_reddit():
    """
    Monitor Reddit for IELTS keyword mentions.
    Saves draft replies to file — NEVER auto-posts (ban risk).
    Review drafts daily and post manually.
    """
    if not all([REDDIT_CLIENT_ID, REDDIT_SECRET, REDDIT_USERNAME, REDDIT_PASSWORD]):
        return
    try:
        import praw
        import time as t
        reddit = praw.Reddit(
            client_id=REDDIT_CLIENT_ID,
            client_secret=REDDIT_SECRET,
            username=REDDIT_USERNAME,
            password=REDDIT_PASSWORD,
            user_agent="IELTSMasterMonitor/1.0"
        )
        for sub_name in REDDIT_SUBS:
            sub = reddit.subreddit(sub_name)
            for comment in sub.comments(limit=20):
                if comment.id in _replied_reddit:
                    continue
                body_lower = comment.body.lower()
                if any(kw in body_lower for kw in REDDIT_KEYWORDS):
                    _replied_reddit.add(comment.id)
                    result = get_reply("reddit", comment.body)
                    if not result["skip"] and result["reply"]:
                        draft = {
                            "id": comment.id,
                            "sub": sub_name,
                            "original": comment.body[:200],
                            "draft_reply": result["reply"],
                            "url": f"https://reddit.com{comment.permalink}"
                        }
                        with open(REDDIT_DRAFTS, "a") as f:
                            f.write(json.dumps(draft) + "\n")
                        log.info(f"Reddit draft saved: r/{sub_name} — {comment.id}")
            t.sleep(2)
    except Exception as e:
        log.error(f"Reddit check failed: {e}")

# ── Scheduled jobs ────────────────────────────────────────────────────────────

def job_daily_mn():
    result = generate_post("telegram_mn", "tip")
    if result.get("post") and TG_CHANNEL_MN:
        post_telegram(TG_CHANNEL_MN, result["post"])

def job_daily_kz():
    result = generate_post("telegram_kz", "tip")
    if result.get("post") and TG_CHANNEL_KZ:
        post_telegram(TG_CHANNEL_KZ, result["post"])

def job_daily_uz():
    result = generate_post("telegram_uz", "tip")
    if result.get("post") and TG_CHANNEL_UZ:
        post_telegram(TG_CHANNEL_UZ, result["post"])

def job_weekly_challenge():
    """Every Monday: post 21-Day Challenge invite to all channels."""
    for channel, lang in [
        (TG_CHANNEL_MN, "telegram_mn"),
        (TG_CHANNEL_KZ, "telegram_kz"),
        (TG_CHANNEL_UZ, "telegram_uz"),
    ]:
        if channel:
            result = generate_post(lang, "challenge")
            if result.get("post"):
                post_telegram(channel, result["post"])

def job_facebook_daily():
    result = generate_post("facebook", "tip")
    if result.get("post"):
        post_facebook(result["post"])

def job_instagram_caption():
    """
    Generates daily Instagram caption and logs it.
    To auto-post: call post_instagram_image(your_image_url, result["post"])
    Image must be a Cloudinary public URL.
    """
    result = generate_post("instagram", "tip")
    if result.get("post"):
        log.info(f"=== INSTAGRAM CAPTION READY ===\n{result['post']}\n=== END ===")

def job_twitter_daily():
    result = generate_post("twitter", "tip")
    if result.get("post"):
        post_tweet(result["post"])

def _start_scheduler():
    scheduler = BackgroundScheduler(timezone="Asia/Ulaanbaatar")
    # Telegram daily tips — 9am in each timezone
    scheduler.add_job(job_daily_mn, "cron", hour=9,  minute=0)
    scheduler.add_job(job_daily_kz, "cron", hour=9,  minute=0,
                      timezone="Asia/Almaty")
    scheduler.add_job(job_daily_uz, "cron", hour=9,  minute=0,
                      timezone="Asia/Tashkent")
    # Facebook daily post — 9:30am UB
    scheduler.add_job(job_facebook_daily, "cron", hour=9, minute=30)
    # Instagram caption — 10am UB
    scheduler.add_job(job_instagram_caption, "cron", hour=10, minute=0)
    # Twitter daily — 8am UB
    scheduler.add_job(job_twitter_daily, "cron", hour=8, minute=0)
    # Weekly Monday challenge
    scheduler.add_job(job_weekly_challenge, "cron",
                      day_of_week="mon", hour=10, minute=0)
    # Twitter mentions — every 15 min
    scheduler.add_job(check_twitter, "interval", minutes=15)
    # Reddit monitoring — every 30 min
    scheduler.add_job(check_reddit, "interval", minutes=30)

    scheduler.start()
    log.info("Scheduler started — all jobs active")
    return scheduler

# ── Telegram webhook registration ─────────────────────────────────────────────

def _register_telegram_webhook():
    """Auto-register Telegram webhook on startup if RAILWAY_PUBLIC_DOMAIN is set."""
    if not TG_TOKEN or not RAILWAY_URL:
        log.warning("Telegram webhook not registered — TG_TOKEN or RAILWAY_PUBLIC_DOMAIN missing")
        return
    webhook_url = f"https://{RAILWAY_URL}/webhook/telegram"
    r = requests.get(
        f"https://api.telegram.org/bot{TG_TOKEN}/setWebhook",
        params={"url": webhook_url},
        timeout=10
    )
    if r.ok and r.json().get("ok"):
        log.info(f"Telegram webhook set: {webhook_url}")
    else:
        log.error(f"Telegram webhook failed: {r.text}")

# ── Application factory ───────────────────────────────────────────────────────

scheduler = _start_scheduler()
_register_telegram_webhook()

if __name__ == "__main__":
    PORT = int(os.environ.get("PORT", 8080))
    log.info(f"Starting IELTS Master Agent on port {PORT}")
    app.run(host="0.0.0.0", port=PORT, debug=False, use_reloader=False)
