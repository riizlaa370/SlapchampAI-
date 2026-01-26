import os
import sys
import tweepy
import random
import time
import json
import requests
from datetime import datetime, timezone, timedelta

# ────────────────────────────────────────────────
#  Debug: Show which environment variables we see
# ────────────────────────────────────────────────
print("=== ENV DEBUG START ===", file=sys.stderr)

keys_we_care_about = [
    "TWITTER_API_KEY",
    "TWITTER_API_SECRET",
    "TWITTER_ACCESS_TOKEN",
    "TWITTER_ACCESS_TOKEN_SECRET",
    "TWITTER_BEARER_TOKEN",
    "TWITTER_CONSUMER_KEY",
    "TWITTER_CONSUMER_SECRET",
    "GROK_API_KEY",          # for xAI Grok API
]

for key in keys_we_care_about:
    value = os.getenv(key)
    if value:
        print(f"{key}: present (starts with {value[:6]}...)", file=sys.stderr)
    else:
        print(f"{key}: MISSING / None", file=sys.stderr)

print("\nFull TWITTER* & GROK* vars:", file=sys.stderr)
for k, v in sorted(os.environ.items()):
    if k.upper().startswith("TWITTER") or k.upper().startswith("GROK") or "OAUTH" in k.upper():
        print(f"  {k} = {v[:10]}...", file=sys.stderr)

print("=== ENV DEBUG END ===", file=sys.stderr)

# ────────────────────────────────────────────────
#  CONFIG
# ────────────────────────────────────────────────
BOT_USERNAME = "slapchampai"           # lowercase, no @
COOLDOWN_SECONDS = 300                 # 5 minutes per attacker-target pair
COOLDOWN_FILE = "cooldowns.json"

# Tenor slap GIFs (safe & funny)
SLAP_GIFS = [
    "https://tenor.com/view/slap-hard-slap-gif-22345678",
    "https://tenor.com/view/will-smith-slap-chris-rock-gif-25141873",
    "https://tenor.com/view/cat-slap-gif-9876543",
    "https://tenor.com/view/batman-slap-robin-gif-123456",
    "https://tenor.com/view/anime-slap-gif-14567890",
    "https://tenor.com/view/pow-slap-gif-17894561",
    "https://tenor.com/view/virtual-slap-gif-20899495",
    "https://tenor.com/view/slap-fight-gif-16274592",
    "https://tenor.com/view/nuclear-slap-gif-98765432",
    "https://tenor.com/view/destroyed-slap-gif-11223344"
]

# ────────────────────────────────────────────────
#  Cooldown helpers
# ────────────────────────────────────────────────
def load_cooldowns():
    if os.path.exists(COOLDOWN_FILE):
        try:
            with open(COOLDOWN_FILE, "r") as f:
                return json.load(f)
        except:
            return {}
    return {}

def save_cooldowns(cooldowns):
    try:
        with open(COOLDOWN_FILE, "w") as f:
            json.dump(cooldowns, f, indent=2)
    except Exception as e:
        print(f"Failed to save cooldowns: {e}", file=sys.stderr)

cooldowns = load_cooldowns()

# ────────────────────────────────────────────────
# Twitter/X Client – OAuth 1.0a USER CONTEXT ONLY
# ────────────────────────────────────────────────
consumer_key    = os.getenv("TWITTER_API_KEY") or os.getenv("TWITTER_CONSUMER_KEY")
consumer_secret = os.getenv("TWITTER_API_SECRET") or os.getenv("TWITTER_CONSUMER_SECRET")
access_token    = os.getenv("TWITTER_ACCESS_TOKEN")
access_token_secret = os.getenv("TWITTER_ACCESS_TOKEN_SECRET")

missing = []
if not consumer_key:    missing.append("TWITTER_API_KEY / CONSUMER_KEY")
if not consumer_secret: missing.append("TWITTER_API_SECRET / CONSUMER_SECRET")
if not access_token:    missing.append("TWITTER_ACCESS_TOKEN")
if not access_token_secret: missing.append("TWITTER_ACCESS_TOKEN_SECRET")

if missing:
    print("CRITICAL: Missing Twitter credentials:", ", ".join(missing), file=sys.stderr)
    sys.exit(1)

client = tweepy.Client(
    consumer_key=consumer_key,
    consumer_secret=consumer_secret,
    access_token=access_token,
    access_token_secret=access_token_secret,
    wait_on_rate_limit=True
    # IMPORTANT: Do NOT add bearer_token=... here — it breaks user context
)

# Verify connection with explicit user auth
try:
    me = client.get_me(user_auth=True).data
    print(f"Connected as @{me.username} — SlapchampAI LIVE 🔥", file=sys.stderr)
except tweepy.TweepyException as e:
    print(f"Connection failed: {e}", file=sys.stderr)
    if hasattr(e, 'response') and e.response:
        print(f"Status: {e.response.status_code}", file=sys.stderr)
        print(f"Body: {e.response.text[:400]}...", file=sys.stderr)
    sys.exit(1)
except Exception as e:
    print(f"Unexpected error during auth: {e}", file=sys.stderr)
    sys.exit(1)

# ────────────────────────────────────────────────
#  Grok Roast Generator (xAI API)
# ────────────────────────────────────────────────
def generate_nuclear_roast(target_username, attacker_username, bio_snippet="", pfp_desc=""):
    grok_key = os.getenv("GROK_API_KEY")
    if not grok_key:
        print("WARNING: GROK_API_KEY missing → using fallback roast", file=sys.stderr)
        return f"@{target_username} just got atomized into another dimension 💀☢️"

    url = "https://api.x.ai/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {grok_key}",
        "Content-Type": "application/json"
    }

    prompt = f"""
You are Grok — nuclear roast mode. Be brutally savage, hilarious, chaotic.
Rules: NO slurs, NO threats, NO racism, NO ban-worthy content.
Target: @{target_username}
Bio snippet: {bio_snippet or 'none'}
PFP description: {pfp_desc or 'unknown'}
Attacker: @{attacker_username}
Output: ONE short, devastating sentence only.
End with 1-2 savage emojis.
"""

    payload = {
        "model": "grok-beta",           # or "grok-4" if available in 2026
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 1.0,
        "max_tokens": 80
    }

    try:
        r = requests.post(url, headers=headers, json=payload, timeout=12)
        r.raise_for_status()
        return r.json()['choices'][0]['message']['content'].strip()
    except Exception as e:
        print(f"Grok API error: {e}", file=sys.stderr)
        return f"@{target_username} got deleted from existence 💥😈"

# ────────────────────────────────────────────────
#  Main Loop – Poll mentions
# ────────────────────────────────────────────────
print("SlapchampAI is now polling mentions...", file=sys.stderr)

while True:
    try:
        # Search for recent mentions with "slap"
        tweets = client.search_recent_tweets(
            query=f"@{BOT_USERNAME} slap -is:retweet lang:en",
            max_results=10,                     # small batch to stay safe
            tweet_fields=["author_id", "entities", "created_at", "id"],
            expansions=["author_id"],
            user_fields=["username", "description", "profile_image_url"]
        )

        if not tweets.data:
            print("No new slaps — sleeping 60s", file=sys.stderr)
            time.sleep(60)
            continue

        for tweet in tweets.data:
            author_id = tweet.author_id
            if author_id == me.id:
                continue  # skip self-replies

            text = tweet.text.lower()
            if "slap" not in text:
                continue

            # Extract mentions (first should be bot, second = target)
            mentions = tweet.entities.get("mentions", [])
            if len(mentions) < 2:
                continue

            target_username = mentions[1]["username"]

            # Cooldown check
            now = datetime.now(timezone.utc)
            key = f"{author_id}_{target_username}"
            last = cooldowns.get(key)
            if last:
                last_time = datetime.fromisoformat(last)
                if now - last_time < timedelta(seconds=COOLDOWN_SECONDS):
                    print(f"Cooldown active for {target_username}", file=sys.stderr)
                    continue

            # Update cooldown
            cooldowns[key] = now.isoformat()
            save_cooldowns(cooldowns)

            # Get target user info
            target = client.get_user(username=target_username,
                                    user_fields=["description", "profile_image_url"]).data

            bio_snippet = target.description[:80] if target and target.description else ""
            pfp_desc = "unknown"

            # Generate roast
            roast = generate_nuclear_roast(
                target_username,
                tweet.author.username if tweets.includes and 'users' in tweets.includes else "someone",
                bio_snippet,
                pfp_desc
            )

            gif = random.choice(SLAP_GIFS)

            # Build reply
            reply_text = (
                f"@{target_username} {roast}\n\n"
                f"{gif}\n"
                f"Slapped by @{tweet.author.username} — Powered by Grok 🔥"
            )
            print("Attempting to post reply with user auth...", file=sys.stderr)
            # Post reply
            client.create_tweet(
                text=reply_text,
                in_reply_to_tweet_id=tweet.id
            )

            print(f"Slapped @{target_username} by @{tweet.author.username}", file=sys.stderr)

        time.sleep(60)

    except tweepy.TweepyException as te:
        print(f"Tweepy error: {te}", file=sys.stderr)
        if hasattr(te, 'response') and te.response:
            print(f"Status: {te.response.status_code}", file=sys.stderr)
            print(f"Body: {te.response.text[:400]}...", file=sys.stderr)
        time.sleep(60)

    except Exception as e:
        print(f"Unexpected loop error: {e}", file=sys.stderr)
        time.sleep(60)
