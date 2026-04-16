"""
IELTS Master — Claude Brain
Central AI for all platform replies and post generation.
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
- Lifetime: $149 once — only 150 units total
- 60-day money back on Lifetime
- Checkout: https://ieltsmaster-org.lemonsqueezy.com/checkout/buy/138f5144-e21e-4692-8631-feeee456bbbf

TONE: Direct, warm, founder energy. No corporate filler. Specific outcomes only.
OUTPUT: Reply text ONLY. No labels, no preamble."""

INTENTS = ["PRICING","HOW_TO_START","OBJECTION","COMPLIMENT","HATE","SUPPORT","QUESTION","SPAM"]

INTENT_RULES = {
    "PRICING": "Explain: Free (3/day), Starter $19/mo, Pro $29/mo, Lifetime $149. Push Lifetime. Include checkout link.",
    "HOW_TO_START": "Tell them: ieltsmaster.org, free, no card, 10 min first session. Mention 21-Day Challenge.",
    "OBJECTION": "Acknowledge. Counter with specific outcome: 'Band 5.5 to 7.0 in 21 days.' Mention 60-day money back.",
    "COMPLIMENT": "Thank warmly. Ask to share — friend gets 3 bonus sessions.",
    "HATE": "Calm. Max 2 sentences. Leave door open.",
    "SUPPORT": "Empathize. Tell them: support@ieltsmaster.org. Answer basic questions directly.",
    "QUESTION": "Answer directly. Mention product only if relevant.",
    "SPAM": "",
}

PLATFORM_RULES = {
    "telegram": "Telegram DM/group. Casual, warm. No hashtags. Under 150 words. Reply in SAME language as user (Mongolian/Russian/Uzbek/English).",
    "facebook": "Facebook Page. Warm community tone. No hashtags. Under 120 words. Match user language.",
    "instagram": "Instagram DM/comment. Friendly. Under 100 words. 1-2 hashtags if comment reply. Match language.",
    "twitter": "Twitter/X. MAX 2 sentences. Punchy. English.",
    "reddit": "Reddit. DO NOT sound like an ad. Helpful first. Product only if 100% natural. Under 100 words.",
    "youtube": "YouTube comment. Friendly. Under 80 words. English.",
}

POST_PLATFORM_RULES = {
    "telegram_mn": "Mongolian (Cyrillic). Casual, warm. No hashtags. Max 200 words. End with question.",
    "telegram_kz": "Russian (Kazakh students). Friendly. No hashtags. Max 200 words.",
    "telegram_uz": "Uzbek. Warm. No hashtags. Max 200 words.",
    "instagram": "English. Hook first line. 150-200 words. 6-8 hashtags at end: #IELTS #IELTSprep #IELTSwriting #bandscore #studyabroad #englishlearning + 2 niche. CTA: link in bio.",
    "facebook": "English or native. Warm. 100-150 words. No hashtags. Soft CTA.",
    "twitter": "English. Max 240 chars. Hook + CTA.",
    "reddit": "English. Value-first. 200-300 words. Product mention only if natural at end.",
}

POST_TYPE_RULES = {
    "tip": "ONE specific actionable IELTS Writing Task 2 tip with before/after example. No product pitch.",
    "demo": "Describe AI 3-color annotation in action. Visual, exciting. Mention ieltsmaster.org naturally.",
    "founder": "Solo Mongolian dev, Govi-Altai, broken wrist, building IELTS AI for Central Asia. Authentic.",
    "flash_sale": "Lifetime deal $99 for 72hrs (normal $149). Urgency not desperation. Link: https://ieltsmaster-org.lemonsqueezy.com/checkout/buy/138f5144-e21e-4692-8631-feeee456bbbf",
    "challenge": "Invite to free 21-Day IELTS Challenge at ieltsmaster.org. 10 min/day. No card. First result in 24hrs.",
    "testimonial": "Realistic testimonial: Central Asian student, Band 5.5→7.0, 21 days, specific details.",
    "exam_urgency": "Exam season. Running out of prep time. Urgency around starting NOW.",
}

def detect_intent(text: str) -> str:
    try:
        r = client().messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=15,
            messages=[{"role":"user","content":f"Classify into exactly one: {', '.join(INTENTS)}\nReply ONE word only.\n\nMessage: {text[:300]}"}]
        )
        intent = r.content[0].text.strip().upper()
        return intent if intent in INTENTS else "QUESTION"
    except Exception as e:
        log.error(f"Intent error: {e}")
        return "QUESTION"

def get_reply(platform: str, message: str) -> dict:
    intent = detect_intent(message)
    if intent == "SPAM":
        return {"reply": "", "intent": "SPAM", "skip": True}
    prompt = (
        f"{PLATFORM_RULES.get(platform, PLATFORM_RULES['telegram'])}\n\n"
        f"Instruction: {INTENT_RULES.get(intent, INTENT_RULES['QUESTION'])}\n\n"
        f"Message: \"{message[:500]}\"\n\nWrite the reply now."
    )
    try:
        r = client().messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=350,
            system=SYSTEM,
            messages=[{"role":"user","content":prompt}]
        )
        reply = r.content[0].text.strip()
        log.info(f"[{platform}] intent={intent} len={len(reply)}")
        return {"reply": reply, "intent": intent, "skip": False}
    except Exception as e:
        log.error(f"Reply failed: {e}")
        return {"reply": "Thanks! Visit ieltsmaster.org to get started free.", "intent": "ERROR", "skip": False}

def generate_post(platform: str, post_type: str, extra: str = "") -> dict:
    prompt = (
        f"Platform: {POST_PLATFORM_RULES.get(platform, POST_PLATFORM_RULES['instagram'])}\n\n"
        f"Content: {POST_TYPE_RULES.get(post_type, POST_TYPE_RULES['tip'])}\n"
        f"{'Extra context: ' + extra if extra else ''}\n\n"
        f"Write the post now. Output ONLY the post text."
    )
    try:
        r = client().messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=500,
            system=SYSTEM,
            messages=[{"role":"user","content":prompt}]
        )
        post = r.content[0].text.strip()
        log.info(f"Post: {platform}/{post_type} ({len(post)} chars)")
        return {"post": post, "platform": platform, "type": post_type}
    except Exception as e:
        log.error(f"Post failed: {e}")
        return {"post": "", "error": str(e)}

def jarvis_command(command: str, context: str = "") -> str:
    """
    Natural language command handler for Jarvis voice control.
    Bat speaks to the bot in any language, Jarvis executes.
    """
    prompt = f"""You are Jarvis, Bat's personal AI assistant for IELTS Master.
Bat is the founder — solo developer from Mongolia.
When Bat gives you a command, execute it and respond clearly.

Commands you can handle:
- Write a post for [platform] about [topic] → return the post text
- Reply to this DM: [message] → return the reply
- Run flash sale → return flash sale post for all platforms
- Post daily tip to Telegram → return the tip
- What should I do today? → return today's priority action
- How's revenue? / How's the bot? → status update
- Write [content type] for [platform] → generate content

Context about Bat's situation:
- IELTS Master: ieltsmaster.org
- Target: $80K by July 10
- Platforms: Telegram (MN/KZ/UZ), Instagram, Facebook, Twitter, Reddit
- Bot is live on Railway
- Lifetime deal: $149

{f'Additional context: {context}' if context else ''}

Command from Bat: "{command}"

Respond directly and helpfully. If it's a content generation request, output the content ready to use."""

    try:
        r = client().messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=800,
            messages=[{"role":"user","content":prompt}]
        )
        return r.content[0].text.strip()
    except Exception as e:
        log.error(f"Jarvis command failed: {e}")
        return f"Error processing command: {e}"
