"""
IELTS Master — Claude Agent Brain
Central intelligence used by ALL platform integrations.
Import this module, call get_reply(platform, context, message).
"""

import os
import anthropic
import json
import logging
from datetime import datetime
from enum import Enum

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("agent_brain")

client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

# ── Detect intent from incoming message ───────────────────────────────────────

INTENT_PROMPT = """Classify this social media message into exactly one category.
Categories: PRICING, HOW_TO_START, OBJECTION, COMPLIMENT, HATE, SUPPORT, GENERAL_QUESTION, SPAM
Reply with ONLY the category word, nothing else."""

def detect_intent(message: str) -> str:
    try:
        r = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=10,
            messages=[{"role": "user", "content": f"{INTENT_PROMPT}\n\nMessage: {message}"}]
        )
        return r.content[0].text.strip()
    except Exception as e:
        log.error(f"Intent detection failed: {e}")
        return "GENERAL_QUESTION"

# ── Platform-specific tone rules ──────────────────────────────────────────────

PLATFORM_RULES = {
    "telegram": "Telegram DM or group. Conversational, warm. No hashtags. Under 150 words. Reply in the same language the user wrote in (Mongolian, Russian, Uzbek, or English).",
    "facebook": "Facebook page comment or DM. Warm community tone. No hashtags. Under 120 words. Reply in same language as user.",
    "instagram": "Instagram DM or comment. Friendly. Under 100 words. 1-2 hashtags max if it's a comment. Reply in same language as user.",
    "twitter": "Twitter/X reply. MAXIMUM 2 sentences. Punchy. No hashtags unless viral opportunity.",
    "reddit": "Reddit comment. Do NOT sound like an ad. Be genuinely helpful. Mention product only if 100% natural. Under 100 words.",
    "youtube": "YouTube comment reply. Friendly, encouraging. Under 80 words. No hashtags.",
    "tiktok": "TikTok comment reply. Very short, energetic. Under 50 words. Can use 1-2 emojis."
}

# ── Intent-specific instructions ──────────────────────────────────────────────

INTENT_RULES = {
    "PRICING": "User is asking about price. Mention: Free plan (3 sessions/day), Starter $19/mo, Pro $29/mo, Lifetime $149 once (only 150 units, some already claimed). Push Lifetime as best value. Include checkout link naturally.",
    "HOW_TO_START": "User wants to know how to start. Tell them: go to ieltsmaster.org, it's free to start, no credit card. First session takes 10 minutes. Mention the 21-Day Challenge.",
    "OBJECTION": "User has doubts (price, effectiveness, comparing to others). Acknowledge their concern genuinely. Counter with specific outcome: 'Band 5.5 to 7.0 in 21 days.' Mention 60-day money back on Lifetime. Use founder story briefly if helpful.",
    "COMPLIMENT": "User said something positive. Thank them warmly (brief). Ask them to share with friends or leave a review. Mention referral: friend gets 3 bonus sessions.",
    "HATE": "User is hostile or negative. Stay completely calm. Under 2 sentences. Do not argue. Leave door open. Example: 'Fair enough — if you ever want to try it, it's free to start.'",
    "SUPPORT": "User has a technical issue. Empathize briefly. Tell them to email support@ieltsmaster.org for fastest help. Offer to help with basic questions.",
    "GENERAL_QUESTION": "Answer their question directly and helpfully. Mention the product only if it genuinely helps answer the question.",
    "SPAM": "Do not reply to spam. Return empty string."
}

# ── Master system prompt ───────────────────────────────────────────────────────

def build_system_prompt(extra_context: str = "") -> str:
    today = datetime.now().strftime("%A, %B %d, %Y")
    return f"""You are the official social media agent for IELTS Master. You respond on behalf of Bat, the solo Mongolian founder.

TODAY: {today}

PRODUCT FACTS:
- ieltsmaster.org — AI-powered IELTS writing tutor
- 3-color essay annotation: green (good), yellow (improve), red (fix)
- 21-Day Challenge: daily practice, free, no credit card needed
- Band score tracking, streaks, motivational system
- Supports Mongolian, Kazakh (Russian), Uzbek — only IELTS AI that does
- Built solo by Mongolian developer from Govi-Altai with a broken wrist

PRICING:
- Free: 3 sessions/day
- Starter: $19/month
- Pro: $29/month
- Lifetime: $149 once (only 150 units total — X already claimed, hurry)
- 60-day money back guarantee on Lifetime
- Checkout: https://ieltsmaster-org.lemonsqueezy.com/checkout/buy/138f5144-e21e-4692-8631-feeee456bbbf

TONE RULES:
- Never say "AI-powered" — say what it specifically does
- Never say "I'd be happy to" or corporate filler
- Be direct, warm, founder-energy
- Specific outcomes beat generic claims ("Band 6.5 to 7.0" not "improve your score")
- Never make up band score statistics you don't have evidence for

{f'ADDITIONAL CONTEXT: {extra_context}' if extra_context else ''}

OUTPUT: Reply text ONLY. No labels, no preamble. Just the reply."""

# ── Main reply function ───────────────────────────────────────────────────────

def get_reply(
    platform: str,
    message: str,
    extra_context: str = "",
    force_intent: str = None
) -> dict:
    """
    Generate a Claude reply for any platform.
    Returns dict: {reply, intent, platform, tokens_used}
    """
    platform = platform.lower()

    # Detect intent
    intent = force_intent or detect_intent(message)
    log.info(f"[{platform}] Intent: {intent} | Message: {message[:60]}...")

    # Spam filter
    if intent == "SPAM":
        log.info("Spam detected — skipping reply")
        return {"reply": "", "intent": "SPAM", "platform": platform, "tokens_used": 0}

    platform_rule = PLATFORM_RULES.get(platform, PLATFORM_RULES["telegram"])
    intent_rule = INTENT_RULES.get(intent, INTENT_RULES["GENERAL_QUESTION"])

    user_prompt = f"""PLATFORM: {platform_rule}

INTENT: {intent_rule}

INCOMING MESSAGE: "{message}"

Write the reply now."""

    try:
        r = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=400,
            system=build_system_prompt(extra_context),
            messages=[{"role": "user", "content": user_prompt}]
        )
        reply = r.content[0].text.strip()
        tokens = r.usage.input_tokens + r.usage.output_tokens
        log.info(f"[{platform}] Reply generated ({tokens} tokens)")
        return {
            "reply": reply,
            "intent": intent,
            "platform": platform,
            "tokens_used": tokens
        }
    except Exception as e:
        log.error(f"Reply generation failed: {e}")
        return {
            "reply": "Thanks for your message! We'll get back to you shortly.",
            "intent": "ERROR",
            "platform": platform,
            "tokens_used": 0
        }

# ── Post content generator ────────────────────────────────────────────────────

POST_PLATFORM_RULES = {
    "telegram_mn": "Write in Mongolian (Cyrillic). Warm, casual. No hashtags. Max 200 words. End with a question or soft invite.",
    "telegram_kz": "Write in Russian (Kazakh IELTS groups). Friendly. No hashtags. Max 200 words.",
    "telegram_uz": "Write in Uzbek. Warm. No hashtags. Max 200 words.",
    "instagram": "English. Hook first line (no emoji). 150-200 words. 6-8 hashtags at end: #IELTS #IELTSprep #IELTSwriting #studyabroad #bandscore #englishlearning + 2 niche. CTA: link in bio.",
    "facebook": "English or native language. Warm community tone. 100-150 words. No hashtags. CTA at end.",
    "twitter": "English. Max 240 chars. Hook + CTA. Punchy.",
    "reddit": "English. Value-first. 200-300 words. Genuinely helpful. Mention product ONLY if natural at the end.",
    "youtube_short": "English video description + title. Title: max 60 chars, hook. Description: 100 words, 3 hashtags."
}

POST_TYPE_RULES = {
    "tip": "Share ONE specific, actionable IELTS Writing Task 2 tip. Include a before/after example. Pure value — no product pitch.",
    "demo": "Describe what AI 3-color essay annotation looks like in action. Make it visual and exciting. Mention ieltsmaster.org naturally.",
    "founder": "Tell the story: solo Mongolian dev, Govi-Altai, broken wrist, building IELTS AI for Central Asian students ignored by Western tools. Authentic.",
    "flash_sale": f"Lifetime deal: $99 for 72 hours (normal $149). Limited units remaining. Urgency without desperation. Link: https://ieltsmaster-org.lemonsqueezy.com/checkout/buy/138f5144-e21e-4692-8631-feeee456bbbf",
    "challenge": "Invite to free 21-Day IELTS Challenge at ieltsmaster.org. 10 min/day. No card. First result in 24 hours.",
    "testimonial": "Write a realistic-sounding testimonial from a Central Asian student: Band 5.5 → 7.0, 21 days, specific details.",
    "exam_urgency": "Exam season is here. Students with June/September exams are running out of prep time. Create urgency around starting now.",
    "weekly_tip_mn": "Monday Mongolian writing tip for the group. One specific tip, Mongolian script, friendly tone.",
    "weekly_tip_kz": "Monday writing tip in Russian for Kazakh IELTS students. Specific, actionable.",
}

def generate_post(
    platform: str,
    post_type: str,
    extra_context: str = ""
) -> dict:
    """Generate a social media post for any platform."""
    platform_rule = POST_PLATFORM_RULES.get(platform, POST_PLATFORM_RULES["instagram"])
    type_rule = POST_TYPE_RULES.get(post_type, POST_TYPE_RULES["tip"])

    prompt = f"""Platform: {platform_rule}
Content type: {type_rule}
{f'Extra context: {extra_context}' if extra_context else ''}

Write the post now. Output ONLY the post text."""

    try:
        r = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=500,
            system=build_system_prompt(),
            messages=[{"role": "user", "content": prompt}]
        )
        post = r.content[0].text.strip()
        tokens = r.usage.input_tokens + r.usage.output_tokens
        log.info(f"Post generated for {platform}/{post_type} ({tokens} tokens)")
        return {"post": post, "platform": platform, "type": post_type, "tokens_used": tokens}
    except Exception as e:
        log.error(f"Post generation failed: {e}")
        return {"post": "", "error": str(e)}
