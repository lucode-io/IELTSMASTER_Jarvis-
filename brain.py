"""
IELTS Master — Claude Brain
Single source of truth for all AI calls.
Used by every platform handler.
"""

import os
import logging
import anthropic

log = logging.getLogger("brain")
_client = None

def client():
    global _client
    if _client is None:
        _client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    return _client

# ── System prompt ─────────────────────────────────────────────────────────────

SYSTEM = """You are the official AI agent for IELTS Master (ieltsmaster.org).
You respond on behalf of Bat, solo Mongolian founder from Govi-Altai.

PRODUCT:
- AI IELTS writing coach with 3-color essay annotation (green=good, yellow=improve, red=fix)
- 21-Day Challenge: daily free practice, no card needed
- Band score tracking, streak system
- Speaks Mongolian, Kazakh (Russian), Uzbek, English — the only IELTS AI that does
- Built solo with a broken wrist on the Mongolian steppe

PRICING:
- Free: 3 sessions/day (no card)
- Starter: $19/month
- Pro: $29/month
- Lifetime: $149 once — only 150 units total, running out fast
- 60-day money back on Lifetime
- Checkout: https://ieltsmaster-org.lemonsqueezy.com/checkout/buy/138f5144-e21e-4692-8631-feeee456bbbf

TONE RULES:
- Never say "AI-powered" — say what it specifically does
- Never say "I'd be happy to" or any corporate filler
- Specific outcomes only: "Band 5.5 to 7.0 in 21 days" not "improve your score"
- Warm, direct, founder energy
- Never make up statistics

OUTPUT: Reply text ONLY. No labels, no preamble, no quotation marks around it."""

# ── Intent classifier ─────────────────────────────────────────────────────────

INTENT_LABELS = [
    "PRICING",       # asking about cost
    "HOW_TO_START",  # how to begin, sign up
    "OBJECTION",     # doubts, "does it work", "too expensive"
    "COMPLIMENT",    # positive feedback
    "HATE",          # hostile, rude, negative attack
    "SUPPORT",       # technical problem
    "QUESTION",      # general question about IELTS or product
    "SPAM",          # irrelevant, bot, spam
]

def detect_intent(text: str) -> str:
    try:
        r = client().messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=15,
            messages=[{
                "role": "user",
                "content": (
                    f"Classify this message into exactly one category.\n"
                    f"Categories: {', '.join(INTENT_LABELS)}\n"
                    f"Reply with ONLY the category word.\n\n"
                    f"Message: {text[:300]}"
                )
            }]
        )
        intent = r.content[0].text.strip().upper()
        return intent if intent in INTENT_LABELS else "QUESTION"
    except Exception as e:
        log.error(f"Intent detection error: {e}")
        return "QUESTION"

# ── Intent instructions ───────────────────────────────────────────────────────

INTENT_INSTRUCTIONS = {
    "PRICING": (
        "User is asking about price. Explain clearly: Free (3 sessions/day), "
        "Starter $19/mo, Pro $29/mo, Lifetime $149 once. "
        "Recommend Lifetime as best value — only 150 units, running out. "
        "Include checkout link naturally at end."
    ),
    "HOW_TO_START": (
        "User wants to start. Tell them: go to ieltsmaster.org, free to start, "
        "no credit card needed, first session takes 10 minutes. "
        "Mention the 21-Day Challenge as the best way to begin."
    ),
    "OBJECTION": (
        "User has a doubt (price, effectiveness, already tried something else). "
        "Acknowledge genuinely first. Then counter with one specific outcome: "
        "'Band 5.5 to 7.0 in 21 days.' Mention 60-day money back on Lifetime. "
        "Use founder story if relevant. Don't be defensive."
    ),
    "COMPLIMENT": (
        "Thank them warmly but briefly. Ask them to share with one friend "
        "or post about it — friend gets 3 bonus sessions with their referral code."
    ),
    "HATE": (
        "Stay completely calm. Maximum 2 sentences. Don't argue. "
        "Leave the door open. Example: 'Fair enough. "
        "It's free to try if you ever want to test it yourself.'"
    ),
    "SUPPORT": (
        "Empathize briefly. Tell them to email support@ieltsmaster.org for fastest help. "
        "If it's a basic question, answer it directly."
    ),
    "QUESTION": (
        "Answer their question directly and helpfully. "
        "Mention the product only if it genuinely helps answer the question."
    ),
    "SPAM": "",
}

# ── Platform rules ────────────────────────────────────────────────────────────

PLATFORM_RULES = {
    "telegram": (
        "Platform: Telegram DM or group message. "
        "Conversational, warm. No hashtags. Under 150 words. "
        "Detect language of message and reply in SAME language "
        "(Mongolian Cyrillic, Russian, Uzbek, or English)."
    ),
    "facebook": (
        "Platform: Facebook Page comment or DM. "
        "Warm community tone. No hashtags. Under 120 words. "
        "Reply in same language as the user wrote in."
    ),
    "instagram": (
        "Platform: Instagram DM or comment. "
        "Friendly, concise. Under 100 words. "
        "1-2 hashtags only if it's a comment reply. "
        "Reply in same language as user."
    ),
    "twitter": (
        "Platform: Twitter/X reply. "
        "MAXIMUM 2 sentences. Punchy. No hashtags unless viral opportunity. "
        "Always English."
    ),
    "reddit": (
        "Platform: Reddit comment reply. "
        "Do NOT sound like an ad — this will get banned. "
        "Be genuinely helpful first. "
        "Only mention the product if it 100% naturally fits. "
        "Under 100 words. English."
    ),
    "youtube": (
        "Platform: YouTube comment reply. "
        "Friendly, encouraging. Under 80 words. No hashtags. English."
    ),
}

# ── DM reply generator ────────────────────────────────────────────────────────

def get_reply(platform: str, message: str) -> dict:
    """
    Generate Claude reply for any incoming DM/comment.
    Returns {"reply": str, "intent": str, "skip": bool}
    """
    intent = detect_intent(message)

    if intent == "SPAM":
        return {"reply": "", "intent": "SPAM", "skip": True}

    platform_rule = PLATFORM_RULES.get(platform, PLATFORM_RULES["telegram"])
    intent_rule   = INTENT_INSTRUCTIONS.get(intent, INTENT_INSTRUCTIONS["QUESTION"])

    prompt = (
        f"{platform_rule}\n\n"
        f"Instruction: {intent_rule}\n\n"
        f"Incoming message: \"{message[:500]}\"\n\n"
        f"Write the reply now."
    )

    try:
        r = client().messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=350,
            system=SYSTEM,
            messages=[{"role": "user", "content": prompt}]
        )
        reply = r.content[0].text.strip()
        log.info(f"[{platform}] intent={intent} reply_len={len(reply)}")
        return {"reply": reply, "intent": intent, "skip": False}
    except Exception as e:
        log.error(f"Reply generation failed: {e}")
        return {
            "reply": "Thanks for your message! Check ieltsmaster.org to get started free.",
            "intent": "ERROR",
            "skip": False
        }

# ── Post content generator ────────────────────────────────────────────────────

POST_PLATFORM_RULES = {
    "telegram_mn": (
        "Write in Mongolian (Cyrillic script). Casual, warm. "
        "No hashtags. Max 200 words. End with a question or soft invite to reply."
    ),
    "telegram_kz": (
        "Write in Russian (for Kazakh IELTS students). "
        "Friendly. No hashtags. Max 200 words."
    ),
    "telegram_uz": (
        "Write in Uzbek. Warm, encouraging. "
        "No hashtags. Max 200 words."
    ),
    "instagram": (
        "English. Strong hook in first line (no emoji at start). "
        "150-200 words. 6-8 hashtags at the very end: "
        "#IELTS #IELTSprep #IELTSwriting #bandscore #studyabroad #englishlearning "
        "plus 2 niche tags. End with CTA: 'Link in bio → ieltsmaster.org'"
    ),
    "facebook": (
        "English or native language. Warm community tone. "
        "100-150 words. No hashtags. "
        "End with a soft CTA or open question."
    ),
    "twitter": (
        "English. Maximum 240 characters total. "
        "Punchy hook + one CTA. No filler."
    ),
    "reddit": (
        "English. Value-first. 200-300 words. "
        "Genuinely helpful content. "
        "Mention product ONLY at the very end if it fits naturally, "
        "and only as a soft mention."
    ),
    "youtube_desc": (
        "Write a YouTube Short description + title. "
        "Title: max 60 chars, curiosity hook. "
        "Description: 100 words, 3 hashtags at end."
    ),
}

POST_TYPE_INSTRUCTIONS = {
    "tip": (
        "Share ONE specific actionable IELTS Writing Task 2 tip. "
        "Include a before/after example sentence. "
        "Pure value — zero product mention."
    ),
    "demo": (
        "Describe what AI 3-color essay annotation looks like in action "
        "(green = good sentences, yellow = needs work, red = fix now). "
        "Make it feel exciting and visual. "
        "Mention ieltsmaster.org naturally once."
    ),
    "founder": (
        "Tell the founder story: solo Mongolian developer, Govi-Altai, broken wrist, "
        "building IELTS AI because Central Asian students are ignored by Western tools. "
        "Authentic, not salesy. No fake humility."
    ),
    "flash_sale": (
        "Announce a 72-hour lifetime deal at $99 (normally $149). "
        "X of 150 units remaining. "
        "Urgency without desperation. "
        "End with checkout link: "
        "https://ieltsmaster-org.lemonsqueezy.com/checkout/buy/138f5144-e21e-4692-8631-feeee456bbbf"
    ),
    "challenge": (
        "Invite people to the free 21-Day IELTS Challenge at ieltsmaster.org. "
        "Takes 10 minutes/day. No credit card. "
        "First result visible after Day 1."
    ),
    "testimonial": (
        "Write a realistic-sounding testimonial from a Central Asian student "
        "who went from Band 5.5 to 7.0 in 21 days. "
        "Make it specific: mention the city, the university they applied to, "
        "the exact writing task type they struggled with."
    ),
    "exam_urgency": (
        "June/September exam season is here. "
        "Students with upcoming exams are running out of prep time. "
        "Create urgency around starting preparation NOW. "
        "Reference real exam dates if known."
    ),
}

def generate_post(platform: str, post_type: str, extra: str = "") -> dict:
    """
    Generate a social media post for any platform.
    Returns {"post": str, "platform": str, "type": str}
    """
    platform_rule = POST_PLATFORM_RULES.get(platform, POST_PLATFORM_RULES["instagram"])
    type_rule     = POST_TYPE_INSTRUCTIONS.get(post_type, POST_TYPE_INSTRUCTIONS["tip"])

    prompt = (
        f"Platform instructions: {platform_rule}\n\n"
        f"Content type: {type_rule}\n"
        f"{f'Additional context: {extra}' if extra else ''}\n\n"
        f"Write the post now. Output ONLY the post text, nothing else."
    )

    try:
        r = client().messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=500,
            system=SYSTEM,
            messages=[{"role": "user", "content": prompt}]
        )
        post = r.content[0].text.strip()
        log.info(f"Post generated: {platform}/{post_type} ({len(post)} chars)")
        return {"post": post, "platform": platform, "type": post_type}
    except Exception as e:
        log.error(f"Post generation failed: {e}")
        return {"post": "", "error": str(e)}
