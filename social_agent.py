"""
IELTS Master — Twitter/X + Reddit + YouTube Agent
- Twitter: monitors mentions, auto-replies, scheduled posts
- Reddit: monitors keyword mentions, drafts replies (human-approved)
- YouTube: replies to new comments
"""

import os
import logging
import requests
import tweepy
import praw
from apscheduler.schedulers.background import BackgroundScheduler
from agent_brain import get_reply, generate_post

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("social_agent")

# ── Twitter / X ───────────────────────────────────────────────────────────────

tw_client = tweepy.Client(
    bearer_token=os.environ.get("TWITTER_BEARER_TOKEN"),
    consumer_key=os.environ.get("TWITTER_API_KEY"),
    consumer_secret=os.environ.get("TWITTER_API_SECRET"),
    access_token=os.environ.get("TWITTER_ACCESS_TOKEN"),
    access_token_secret=os.environ.get("TWITTER_ACCESS_SECRET"),
    wait_on_rate_limit=True
)

TWITTER_USER_ID = os.environ.get("TWITTER_USER_ID")
_replied_tweet_ids = set()  # in-memory dedup (use Redis/DB in production)

def check_twitter_mentions():
    """Poll for new mentions every 15 min and reply."""
    try:
        mentions = tw_client.get_users_mentions(
            id=TWITTER_USER_ID,
            max_results=10,
            tweet_fields=["text", "author_id"]
        )
        if not mentions.data:
            return
        for tweet in mentions.data:
            if tweet.id in _replied_tweet_ids:
                continue
            log.info(f"Twitter mention: {tweet.text[:60]}")
            result = get_reply("twitter", tweet.text)
            if result["reply"]:
                tw_client.create_tweet(
                    text=result["reply"],
                    in_reply_to_tweet_id=tweet.id
                )
                _replied_tweet_ids.add(tweet.id)
                log.info(f"Twitter replied to {tweet.id}")
    except Exception as e:
        log.error(f"Twitter mentions check failed: {e}")

def post_tweet(text: str):
    """Post a tweet."""
    try:
        r = tw_client.create_tweet(text=text[:280])
        log.info(f"Tweet posted: {r.data['id']}")
        return r.data["id"]
    except Exception as e:
        log.error(f"Tweet failed: {e}")
        return None

def scheduled_twitter_post():
    """Daily Twitter tip."""
    result = generate_post("twitter", "tip")
    if result.get("post"):
        post_tweet(result["post"])

# ── Reddit ────────────────────────────────────────────────────────────────────

reddit = praw.Reddit(
    client_id=os.environ.get("REDDIT_CLIENT_ID"),
    client_secret=os.environ.get("REDDIT_CLIENT_SECRET"),
    username=os.environ.get("REDDIT_USERNAME"),
    password=os.environ.get("REDDIT_PASSWORD"),
    user_agent="IELTSMasterBot/1.0 by /u/ieltsmaster"
)

REDDIT_MONITOR_SUBS = ["learnEnglish", "IELTS", "Mongolia", "Kazakhstan", "Uzbekistan", "studyAbroad"]
REDDIT_KEYWORDS     = ["ielts writing", "band score", "task 2", "ielts prep", "ielts tool", "ielts ai"]
_replied_reddit_ids = set()

# IMPORTANT: Reddit is human-in-the-loop only.
# Bot auto-replies get accounts banned. This code LOGS draft replies.
# You approve them manually from the draft log.

REDDIT_DRAFT_LOG = "/tmp/reddit_drafts.jsonl"

def check_reddit_mentions():
    """Monitor Reddit for keyword mentions, save draft replies."""
    import json, time
    try:
        for sub_name in REDDIT_MONITOR_SUBS:
            sub = reddit.subreddit(sub_name)
            for comment in sub.comments(limit=25):
                if comment.id in _replied_reddit_ids:
                    continue
                text_lower = comment.body.lower()
                if any(kw in text_lower for kw in REDDIT_KEYWORDS):
                    _replied_reddit_ids.add(comment.id)
                    log.info(f"Reddit mention in r/{sub_name}: {comment.body[:80]}")
                    result = get_reply("reddit", comment.body)
                    if result["reply"]:
                        draft = {
                            "id": comment.id,
                            "subreddit": sub_name,
                            "original": comment.body[:200],
                            "draft_reply": result["reply"],
                            "url": f"https://reddit.com{comment.permalink}"
                        }
                        with open(REDDIT_DRAFT_LOG, "a") as f:
                            f.write(json.dumps(draft) + "\n")
                        log.info(f"Reddit draft saved for r/{sub_name}")
            time.sleep(2)  # rate limit
    except Exception as e:
        log.error(f"Reddit check failed: {e}")

def post_reddit_value(subreddit: str, title: str, text: str):
    """Post a value post to Reddit (manual approval recommended first)."""
    try:
        sub = reddit.subreddit(subreddit)
        post = sub.submit(title=title, selftext=text)
        log.info(f"Reddit post submitted: {post.url}")
        return post.url
    except Exception as e:
        log.error(f"Reddit post failed: {e}")
        return None

# ── YouTube ───────────────────────────────────────────────────────────────────

YT_API_KEY = os.environ.get("YOUTUBE_API_KEY")
YT_CHANNEL_ID = os.environ.get("YOUTUBE_CHANNEL_ID")
_replied_yt_ids = set()

def check_youtube_comments():
    """Poll for new YouTube comments and reply."""
    if not YT_API_KEY:
        return
    try:
        # Get latest video
        search_url = "https://www.googleapis.com/youtube/v3/search"
        r = requests.get(search_url, params={
            "part": "id",
            "channelId": YT_CHANNEL_ID,
            "order": "date",
            "maxResults": 3,
            "type": "video",
            "key": YT_API_KEY
        })
        if not r.ok:
            return
        videos = [item["id"]["videoId"] for item in r.json().get("items", [])]

        for video_id in videos:
            comments_url = "https://www.googleapis.com/youtube/v3/commentThreads"
            cr = requests.get(comments_url, params={
                "part": "snippet",
                "videoId": video_id,
                "maxResults": 20,
                "key": YT_API_KEY
            })
            if not cr.ok:
                continue
            for item in cr.json().get("items", []):
                comment_id = item["id"]
                if comment_id in _replied_yt_ids:
                    continue
                text = item["snippet"]["topLevelComment"]["snippet"]["textDisplay"]
                log.info(f"YouTube comment on {video_id}: {text[:60]}")
                result = get_reply("youtube", text)
                if result["reply"]:
                    _post_youtube_reply(comment_id, result["reply"])
                    _replied_yt_ids.add(comment_id)
    except Exception as e:
        log.error(f"YouTube check failed: {e}")

def _post_youtube_reply(parent_id: str, text: str):
    """Post YouTube comment reply (requires OAuth — see setup docs)."""
    # YouTube requires OAuth 2.0 for writing.
    # Setup: google-auth-oauthlib, get refresh token once, store as env var.
    log.info(f"YouTube reply (needs OAuth setup): {text[:60]}")

# ── Scheduler ─────────────────────────────────────────────────────────────────

scheduler = BackgroundScheduler(timezone="Asia/Ulaanbaatar")

# Twitter mentions — every 15 min
scheduler.add_job(check_twitter_mentions, "interval", minutes=15)

# Daily Twitter post — 8am
scheduler.add_job(scheduled_twitter_post, "cron", hour=8, minute=0)

# Reddit monitoring — every 30 min
scheduler.add_job(check_reddit_mentions, "interval", minutes=30)

# YouTube comments — every 20 min
scheduler.add_job(check_youtube_comments, "interval", minutes=20)

def start():
    scheduler.start()
    log.info("Social agent started: Twitter + Reddit + YouTube monitoring active")
    # Keep alive
    import time
    while True:
        time.sleep(60)

if __name__ == "__main__":
    start()
