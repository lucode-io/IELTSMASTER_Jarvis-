# Environment Variables — Add ALL to Railway → Variables tab

## Required (bot dies without these)

| Variable | Example value | Where to get it |
|---|---|---|
| ANTHROPIC_API_KEY | sk-ant-api03-... | console.anthropic.com → API Keys |
| TELEGRAM_BOT_TOKEN | 8714297888:AAELlm... | @BotFather → /mybots → API Token |
| RAILWAY_PUBLIC_DOMAIN | web-production-f3282.up.railway.app | Railway → your service → Settings → Networking → Domain |

## Telegram channels (add when you have the IDs)

| Variable | Example value | Where to get it |
|---|---|---|
| TELEGRAM_CHANNEL_MN | -5049906475 | From your URL: web.telegram.org/k/#-XXXXXXXXXX |
| TELEGRAM_CHANNEL_KZ | -1009876543210 | Same method for KZ group |
| TELEGRAM_CHANNEL_UZ | -1009876543211 | Same method for UZ group |

## Facebook + Instagram (add after Meta app approval)

| Variable | Example value | Where to get it |
|---|---|---|
| META_PAGE_ACCESS_TOKEN | EAABwzLix... | developers.facebook.com → Graph API Explorer → Get Page Token |
| META_PAGE_ID | 123456789012345 | Graph API Explorer → /me/accounts → id field |
| META_IG_USER_ID | 17841234567890123 | Graph API Explorer → me?fields=instagram_business_account |
| META_WEBHOOK_VERIFY_TOKEN | ieltsmaster2026 | Make up any secret word |

## Twitter / X (add after developer approval)

| Variable | Where to get it |
|---|---|
| TWITTER_BEARER_TOKEN | developer.twitter.com → your app → Keys and Tokens |
| TWITTER_API_KEY | Same |
| TWITTER_API_SECRET | Same |
| TWITTER_ACCESS_TOKEN | Same → Generate |
| TWITTER_ACCESS_SECRET | Same → Generate |
| TWITTER_USER_ID | api.twitter.com/2/users/by?usernames=YOUR_USERNAME |

## Reddit (add after app creation)

| Variable | Where to get it |
|---|---|
| REDDIT_CLIENT_ID | reddit.com/prefs/apps → your app → short string under name |
| REDDIT_CLIENT_SECRET | Same → secret |
| REDDIT_USERNAME | Your dedicated Reddit bot account username |
| REDDIT_PASSWORD | Your dedicated Reddit bot account password |

---

## After adding variables — set Telegram webhook once

Paste this URL in your browser (replace YOUR_TOKEN and YOUR_RAILWAY_URL):

```
https://api.telegram.org/botYOUR_TOKEN/setWebhook?url=https://YOUR_RAILWAY_URL/webhook/telegram
```

Example with your real values:
```
https://api.telegram.org/bot8714297888:AAELlmLhmK_J1hF9INMjab4iOiRd9gkTb9A/setWebhook?url=https://web-production-f3282.up.railway.app/webhook/telegram
```

Expected response: {"ok":true,"result":true,"description":"Webhook was set"}

---

## After adding Facebook/Instagram variables — set webhooks in Meta

1. developers.facebook.com → your app → Webhooks
2. Add Page subscription:
   - Callback URL: https://YOUR_RAILWAY_URL/webhook/facebook
   - Verify token: ieltsmaster2026 (whatever you set as META_WEBHOOK_VERIFY_TOKEN)
   - Subscribe to: feed, messages
3. Add Instagram subscription:
   - Callback URL: https://YOUR_RAILWAY_URL/webhook/instagram
   - Verify token: same
   - Subscribe to: comments, messages

---

## How to post a Reel manually (one command)

After uploading your Higgsfield video to Cloudinary, call this from Terminal or Postman:

```bash
curl -X POST https://YOUR_RAILWAY_URL/post/reel \
  -H "Content-Type: application/json" \
  -d '{"video_url": "https://res.cloudinary.com/your_cloud/video/upload/reel.mp4", "caption": ""}'
```

Leave caption empty — Claude generates it automatically.
