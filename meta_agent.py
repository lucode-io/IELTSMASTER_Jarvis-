"""
IELTS Master — Facebook & Instagram Agent
- Auto-replies to Facebook Page comments and DMs
- Auto-posts to Facebook Page
- Auto-posts to Instagram (feed + reels via container API)
- Runs as a Flask webhook server — deploy on Railway
"""

import os
import hmac
import hashlib
import logging
import requests
from flask import Flask, request, jsonify
from apscheduler.schedulers.background import BackgroundScheduler
from agent_brain import get_reply, generate_post

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("meta_agent")

app = Flask(__name__)

# ── Credentials ───────────────────────────────────────────────────────────────
PAGE_ACCESS_TOKEN    = os.environ["META_PAGE_ACCESS_TOKEN"]
PAGE_ID              = os.environ["META_PAGE_ID"]
IG_USER_ID           = os.environ["META_IG_USER_ID"]
WEBHOOK_VERIFY_TOKEN = os.environ["META_WEBHOOK_VERIFY_TOKEN"]
APP_SECRET           = os.environ.get("META_APP_SECRET", "")

GRAPH = "https://graph.facebook.com/v19.0"

# ── Webhook verification ──────────────────────────────────────────────────────

@app.route("/webhook/facebook", methods=["GET"])
def fb_verify():
    mode  = request.args.get("hub.mode")
    token = request.args.get("hub.verify_token")
    challenge = request.args.get("hub.challenge")
    if mode == "subscribe" and token == WEBHOOK_VERIFY_TOKEN:
        log.info("Facebook webhook verified")
        return challenge, 200
    return "Forbidden", 403

# ── Incoming Facebook events ──────────────────────────────────────────────────

@app.route("/webhook/facebook", methods=["POST"])
def fb_webhook():
    # Verify signature
    if APP_SECRET:
        sig = request.headers.get("X-Hub-Signature-256", "")
        expected = "sha256=" + hmac.new(
            APP_SECRET.encode(), request.data, hashlib.sha256
        ).hexdigest()
        if not hmac.compare_digest(sig, expected):
            return "Invalid signature", 403

    data = request.json
    for entry in data.get("entry", []):
        # Page comments
        for change in entry.get("changes", []):
            if change.get("field") == "feed":
                val = change.get("value", {})
                if val.get("item") == "comment" and val.get("verb") == "add":
                    handle_fb_comment(val)

        # Page DMs (Messenger)
        for msg_event in entry.get("messaging", []):
            if "message" in msg_event:
                handle_fb_dm(msg_event)

    return "OK", 200

def handle_fb_comment(val):
    comment_id = val.get("comment_id")
    message    = val.get("message", "")
    sender_id  = val.get("from", {}).get("id")

    # Don't reply to own page comments
    if sender_id == PAGE_ID:
        return

    log.info(f"FB comment: {message[:60]}")
    result = get_reply("facebook", message)
    if result["reply"]:
        reply_to_fb_comment(comment_id, result["reply"])

def handle_fb_dm(msg_event):
    sender_id = msg_event["sender"]["id"]
    message   = msg_event.get("message", {}).get("text", "")

    if sender_id == PAGE_ID or not message:
        return

    log.info(f"FB DM from {sender_id}: {message[:60]}")
    result = get_reply("facebook", message)
    if result["reply"]:
        send_fb_dm(sender_id, result["reply"])

def reply_to_fb_comment(comment_id, text):
    url = f"{GRAPH}/{comment_id}/comments"
    r = requests.post(url, params={
        "access_token": PAGE_ACCESS_TOKEN,
        "message": text
    })
    if r.ok:
        log.info(f"FB comment replied: {comment_id}")
    else:
        log.error(f"FB comment reply failed: {r.text}")

def send_fb_dm(recipient_id, text):
    url = f"{GRAPH}/me/messages"
    r = requests.post(url, params={"access_token": PAGE_ACCESS_TOKEN}, json={
        "recipient": {"id": recipient_id},
        "message": {"text": text}
    })
    if r.ok:
        log.info(f"FB DM sent to {recipient_id}")
    else:
        log.error(f"FB DM failed: {r.text}")

# ── Post to Facebook Page ─────────────────────────────────────────────────────

def post_to_facebook(text: str, link: str = None):
    url = f"{GRAPH}/{PAGE_ID}/feed"
    payload = {"message": text, "access_token": PAGE_ACCESS_TOKEN}
    if link:
        payload["link"] = link
    r = requests.post(url, data=payload)
    if r.ok:
        log.info(f"Facebook post published: {r.json().get('id')}")
        return r.json().get("id")
    else:
        log.error(f"Facebook post failed: {r.text}")
        return None

# ── Post to Instagram ─────────────────────────────────────────────────────────

def post_instagram_image(image_url: str, caption: str):
    """Post a single image to Instagram feed."""
    # Step 1: Create media container
    r = requests.post(f"{GRAPH}/{IG_USER_ID}/media", params={
        "image_url": image_url,
        "caption": caption,
        "access_token": PAGE_ACCESS_TOKEN
    })
    if not r.ok:
        log.error(f"IG container failed: {r.text}")
        return None

    container_id = r.json().get("id")
    log.info(f"IG container created: {container_id}")

    # Step 2: Publish container
    r2 = requests.post(f"{GRAPH}/{IG_USER_ID}/media_publish", params={
        "creation_id": container_id,
        "access_token": PAGE_ACCESS_TOKEN
    })
    if r2.ok:
        log.info(f"Instagram image published: {r2.json().get('id')}")
        return r2.json().get("id")
    else:
        log.error(f"IG publish failed: {r2.text}")
        return None

def post_instagram_reel(video_url: str, caption: str, thumbnail_url: str = None):
    """Post a Reel to Instagram."""
    params = {
        "media_type": "REELS",
        "video_url": video_url,
        "caption": caption,
        "share_to_feed": "true",
        "access_token": PAGE_ACCESS_TOKEN
    }
    if thumbnail_url:
        params["thumb_offset"] = "2000"

    r = requests.post(f"{GRAPH}/{IG_USER_ID}/media", params=params)
    if not r.ok:
        log.error(f"IG Reel container failed: {r.text}")
        return None

    container_id = r.json().get("id")
    log.info(f"IG Reel container: {container_id} — waiting for processing...")

    # Wait for video processing (poll status)
    import time
    for attempt in range(12):  # max 2 minutes
        time.sleep(10)
        status_r = requests.get(f"{GRAPH}/{container_id}", params={
            "fields": "status_code",
            "access_token": PAGE_ACCESS_TOKEN
        })
        status = status_r.json().get("status_code")
        log.info(f"IG Reel status: {status} (attempt {attempt+1})")
        if status == "FINISHED":
            break
        if status == "ERROR":
            log.error("IG Reel processing failed")
            return None

    # Publish
    r2 = requests.post(f"{GRAPH}/{IG_USER_ID}/media_publish", params={
        "creation_id": container_id,
        "access_token": PAGE_ACCESS_TOKEN
    })
    if r2.ok:
        log.info(f"Instagram Reel published: {r2.json().get('id')}")
        return r2.json().get("id")
    else:
        log.error(f"IG Reel publish failed: {r2.text}")
        return None

# ── Instagram comment webhook ─────────────────────────────────────────────────

@app.route("/webhook/instagram", methods=["GET"])
def ig_verify():
    mode      = request.args.get("hub.mode")
    token     = request.args.get("hub.verify_token")
    challenge = request.args.get("hub.challenge")
    if mode == "subscribe" and token == WEBHOOK_VERIFY_TOKEN:
        return challenge, 200
    return "Forbidden", 403

@app.route("/webhook/instagram", methods=["POST"])
def ig_webhook():
    data = request.json
    for entry in data.get("entry", []):
        for change in entry.get("changes", []):
            if change.get("field") == "comments":
                val = change.get("value", {})
                comment_id = val.get("id")
                text       = val.get("text", "")
                media_id   = val.get("media", {}).get("id")
                log.info(f"IG comment on {media_id}: {text[:60]}")
                result = get_reply("instagram", text)
                if result["reply"]:
                    reply_to_ig_comment(comment_id, result["reply"])
    return "OK", 200

def reply_to_ig_comment(comment_id, text):
    r = requests.post(f"{GRAPH}/{comment_id}/replies", params={
        "message": text,
        "access_token": PAGE_ACCESS_TOKEN
    })
    if r.ok:
        log.info(f"IG comment replied: {comment_id}")
    else:
        log.error(f"IG comment reply failed: {r.text}")

# ── Scheduled posts ───────────────────────────────────────────────────────────

def scheduled_facebook_post():
    """Daily Facebook post — value content."""
    result = generate_post("facebook", "tip")
    if result.get("post"):
        post_to_facebook(result["post"])
        log.info("Scheduled FB post done")

def scheduled_instagram_tip():
    """Daily Instagram caption — generate text (image upload manual or via Higgsfield URL)."""
    result = generate_post("instagram", "tip")
    if result.get("post"):
        log.info(f"IG caption ready:\n{result['post']}")
        # To auto-post: call post_instagram_image(your_image_url, result["post"])
        # Image must be a publicly accessible URL (e.g. uploaded to Cloudinary/S3)

scheduler = BackgroundScheduler(timezone="Asia/Ulaanbaatar")
scheduler.add_job(scheduled_facebook_post, "cron", hour=9, minute=30)
scheduler.add_job(scheduled_instagram_tip, "cron", hour=10, minute=0)

# ── App entry ─────────────────────────────────────────────────────────────────

def create_app():
    scheduler.start()
    log.info("Meta agent started — Facebook + Instagram webhooks live")
    return app

if __name__ == "__main__":
    create_app()
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5001)))
