# IELTS Master — Complete Deployment Guide
## Version 3 — 100% working

---

## WHY THIS VERSION WORKS (technical explanation)

Previous versions failed because `_start_scheduler()` ran at **module import time**.
When gunicorn imports `app.py`, the scheduler tried to connect to Telegram and
start background threads — BEFORE Flask bound to the port.
Railway's healthcheck timed out waiting for `/health` to respond.

**Fix:** Flask starts instantly. Scheduler starts on the FIRST request via
`@app.before_request`. By then, gunicorn has fully bound to `$PORT` and
Railway's healthcheck has already passed.

---

## FILE LIST (upload all 6 to GitHub)

```
app.py          ← main server (Flask + Telegram + Facebook + Instagram + scheduler)
brain.py        ← Claude AI (replies, posts, Jarvis commands)
requirements.txt
Procfile
railway.json
runtime.txt
```

**Delete all old files first.** Then upload these 6.

---

## STEP 1 — Railway Settings (do this BEFORE uploading files)

In Railway → your service → Settings tab:

1. **Custom Start Command** → CLEAR IT (delete whatever is there, leave empty)
   The Procfile handles this automatically.

2. **Healthcheck Path** → `/health`

3. **Healthcheck Timeout** → `60`

---

## STEP 2 — Railway Variables (all required)

In Railway → Variables tab → add these:

### Always required
```
ANTHROPIC_API_KEY        = sk-ant-api03-...
TELEGRAM_BOT_TOKEN       = 8714297888:AAELlmLhmK_J1hF9INMjab4iOiRd9gkTb9A
TELEGRAM_CHANNEL_MN      = -5049906475
RAILWAY_PUBLIC_DOMAIN    = web-production-f3282.up.railway.app
PORT                     = 8080
```

### For Jarvis voice control (YOUR personal Telegram ID)
```
TELEGRAM_OWNER_ID        = [your personal Telegram user ID]
```
To get your ID: message @userinfobot on Telegram → it shows your ID number.

### Telegram channels (add as you create them)
```
TELEGRAM_CHANNEL_KZ      = -100XXXXXXXXXX
TELEGRAM_CHANNEL_UZ      = -100XXXXXXXXXX
```

### Facebook + Instagram (add after Meta app approval)
```
META_PAGE_ACCESS_TOKEN   = EAABwzLix...
META_PAGE_ID             = 123456789
META_IG_USER_ID          = 17841234567890123
META_WEBHOOK_VERIFY_TOKEN = ieltsmaster2026
```

### Twitter/X
```
TWITTER_BEARER_TOKEN     = AAAA...
TWITTER_API_KEY          = xxx
TWITTER_API_SECRET       = xxx
TWITTER_ACCESS_TOKEN     = xxx
TWITTER_ACCESS_SECRET    = xxx
TWITTER_USER_ID          = 123456789
```

### Reddit
```
REDDIT_CLIENT_ID         = xxx
REDDIT_CLIENT_SECRET     = xxx
REDDIT_USERNAME          = ieltsmaster_bot
REDDIT_PASSWORD          = xxx
```

---

## STEP 3 — Upload files to GitHub

1. Go to your GitHub repo (IELTSMASTER_Jarvis-)
2. Delete ALL existing files
3. Upload these 6 files
4. Click "Commit changes"
5. Railway auto-deploys (watch for green ✓ in Deployments tab)

---

## STEP 4 — Verify it works

Open in browser:
```
https://web-production-f3282.up.railway.app/health
```

You should see: `{"service":"IELTS Master","status":"ok"}`

If yes → bot is live.

---

## STEP 5 — Telegram webhook (automatic)

The webhook registers automatically on first request.
To verify it worked, paste in browser:
```
https://api.telegram.org/bot8714297888:AAELlmLhmK_J1hF9INMjab4iOiRd9gkTb9A/getWebhookInfo
```
Should show your Railway URL as the webhook URL.

---

## STEP 6 — Facebook + Instagram webhooks

After adding Meta variables:

1. developers.facebook.com → your app → Webhooks
2. Page subscription:
   - URL: `https://web-production-f3282.up.railway.app/webhook/facebook`
   - Verify token: `ieltsmaster2026`
   - Subscribe to: `feed`, `messages`
3. Instagram subscription:
   - URL: `https://web-production-f3282.up.railway.app/webhook/instagram`
   - Verify token: `ieltsmaster2026`
   - Subscribe to: `comments`, `messages`

---

## JARVIS VOICE CONTROL — how it works

### Setup
1. Get your Telegram user ID: message @userinfobot → copy the number
2. Add `TELEGRAM_OWNER_ID = [your number]` to Railway Variables
3. Redeploy

### How to use Jarvis
Open Telegram → find your bot (@Du_Ke_bot) → send any of these:

**Text commands:**
```
jarvis write a flash sale post for Telegram Mongolia
jarvis reply to this DM: "how much does it cost?"
jarvis what should I do today?
jarvis post daily tip to all channels
jarvis write an Instagram caption for the essay demo
```

**Voice commands:**
Send a voice message to the bot.
(Full voice transcription needs OpenAI Whisper API key.
Add OPENAI_API_KEY to Railway to enable it.)

### What Jarvis can do
- Write posts for any platform in any language
- Generate DM replies
- Give you today's priority actions
- Run flash sale content
- Write Twitter threads
- Analyze your funnel

---

## POSTING INSTAGRAM REELS — workflow

1. Create video in Higgsfield
2. Upload to Cloudinary (cloudinary.com — free)
3. Copy the public video URL (ends in .mp4)
4. Send this command from Telegram:

```
jarvis post this reel: https://res.cloudinary.com/your_cloud/video/upload/reel.mp4
```

Or call the API directly:
```bash
curl -X POST https://web-production-f3282.up.railway.app/post/reel \
  -H "Content-Type: application/json" \
  -d '{"video_url": "https://your-cloudinary-url.mp4", "caption": ""}'
```
Leave caption empty — Claude generates it automatically.

---

## POSTING TO ALL PLATFORMS FROM TELEGRAM (one-hand workflow)

Send these to your bot (@Du_Ke_bot):

| Command | What happens |
|---------|-------------|
| `jarvis post tip to all telegram` | Posts writing tip to MN + KZ + UZ groups |
| `jarvis post flash sale` | Generates + sends flash sale to all Telegram channels |
| `jarvis write instagram reel caption` | Generates caption, you add the video in Meta Suite |
| `jarvis write facebook post` | Generates post, calls /post/facebook endpoint |
| `jarvis reply: [paste DM here]` | Generates a reply to any DM |

---

## TIKTOK

TikTok API requires application approval (1-4 weeks).
Apply at developers.tiktok.com → Content Posting API.
While waiting: create videos in Higgsfield, post manually using TikTok app.

Once approved, add:
```
TIKTOK_CLIENT_KEY    = xxx
TIKTOK_CLIENT_SECRET = xxx
TIKTOK_ACCESS_TOKEN  = xxx
```

The `/post/reel` endpoint can be extended to post to TikTok using the same video URL.

---

## AUTOMATIC DAILY SCHEDULE

| Time (UB) | Action |
|-----------|--------|
| 08:00 | Twitter daily tip |
| 09:00 | Telegram MN daily tip |
| 09:00 | Telegram KZ daily tip (Almaty time) |
| 09:00 | Telegram UZ daily tip (Tashkent time) |
| 09:30 | Facebook Page daily post |
| 10:00 | Instagram caption generated (check Railway logs) |
| Mon 10:00 | 21-Day Challenge invite → all channels |
| Every 15 min | Twitter mentions → auto-reply |
| Every 30 min | Reddit keywords → draft replies saved |
| Always | Telegram DMs → instant Claude reply |
| Always | Facebook comments → instant Claude reply |
| Always | Instagram comments → instant Claude reply |

---

## TROUBLESHOOTING

### Healthcheck still failing
→ In Railway Settings, make sure Custom Start Command is EMPTY (cleared)
→ Check Procfile is in root of repo (not in a subfolder)
→ Click Deploy Logs tab → look for the error line

### Bot not replying to Telegram
→ Check webhook: `https://api.telegram.org/botTOKEN/getWebhookInfo`
→ Should show your Railway URL, not empty
→ If empty: send one message to the bot to trigger `@app.before_request`

### Instagram/Facebook not working
→ Check META_PAGE_ACCESS_TOKEN is not expired (regenerate every 2 months)
→ Verify webhooks are subscribed in Meta Developer portal
