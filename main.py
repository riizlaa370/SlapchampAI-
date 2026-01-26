import os
import sys

print("=== ENV DEBUG START ===", file=sys.stderr)
keys_we_care_about = [
    "TWITTER_API_KEY",
    "TWITTER_API_SECRET",
    "TWITTER_CONSUMER_KEY",
    "TWITTER_CONSUMER_SECRET",
    "TWITTER_ACCESS_TOKEN",
    "TWITTER_ACCESS_TOKEN_SECRET",
    "TWITTER_BEARER_TOKEN",
    "API_KEY", "CONSUMER_KEY", "ACCESS_TOKEN"  # common alternatives
]

for key in keys_we_care_about:
    value = os.getenv(key)
    if value:
        print(f"{key}: present (starts with {value[:6]}...)", file=sys.stderr)
    else:
        print(f"{key}: MISSING / None", file=sys.stderr)

print("Full TWITTER* vars:", file=sys.stderr)
for k, v in os.environ.items():
    if k.upper().startswith("TWITTER") or "OAUTH" in k.upper():
        print(f"  {k} = {v[:10]}...", file=sys.stderr)

print("=== ENV DEBUG END ===", file=sys.stderr)

# ← rest of your code continues here
import os
import tweepy
import random
import time
import json
import requests
from datetime import datetime, timezone, timedelta

# ── CONFIG ──────────────────────────────────────────────────────────────
BOT_USERNAME = "slapchampai"           # lowercase, no @
COOLDOWN_SECONDS = 300                 # 5 min per attacker-target pair

# Tenor slap GIFs (10 safe, high-quality)
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

COOLDOWN_FILE = "cooldowns.json"

def load_cooldowns():
    if os.path.exists(COOLDOWN_FILE):
        with open(COOLDOWN_FILE, "r") as f:
            return json.load(f)
    return {}

def save_cooldowns(cooldowns):
    with open(COOLDOWN_FILE, "w") as f:
        json.dump(cooldowns, f)

cooldowns = load_cooldowns()

# ── X API SETUP ─────────────────────────────────────────────────────────
client = tweepy.Client(
    bearer_token=os.getenv('BEARER_TOKEN'),
    consumer_key=os.getenv("TWITTER_API_KEY"),
    consumer_secret=os.getenv("TWITTER_API_SECRET"),
    access_token=os.getenv('ACCESS_TOKEN'),
    access_token_secret=os.getenv('ACCESS_TOKEN_SECRET'),
    wait_on_rate_limit=True,
     # Forces OAuth 1.0a User Context instead of App-Only
)

me = client.get_me().data
print(f"Connected as @{me.username} — SlapchampAI LIVE 🔥")

# ── GROK ROAST GENERATOR ────────────────────────────────────────────────
def generate_nuclear_roast(target_username, attacker_username, bio_snippet="", pfp_desc=""):
    url = "https://api.x.ai/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {os.getenv('GROK_API_KEY')}",
        "Content-Type": "application/json"
    }

    prompt = f"""
    You are Grok — nuclear destruction roast mode. Be brutally savage, hilarious, chaotic.
    NO slurs, threats, racism, or ban-worthy content.
    Target: @{target_username}
    Bio snippet: {bio_snippet or 'none'}
    PFP description: {pfp_desc or 'unknown'}
    Attacker: @{attacker_username}
    ONE short, direct, devastating sentence only.
    End with 1-2 savage emojis.
    """

    payload = {
        "model": "grok-4",
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 1.0,
        "max_tokens": 60
    }

    try:
        r = requests.post(url, headers=headers, json=payload, timeout=10)
        r.raise_for_status()
        return r.json()['choices'][0]['message']['content'].strip()
    except Exception as e:
        print("Grok API error:", e)
        return f"@{target_username} just got obliterated into next week 💀🔥"

# ── MAIN LOOP ────────────────────────────────────────────────────────────
print("SlapchampAI polling mentions with 'slap' intent...")

while True:
    try:
        tweets = client.search_recent_tweets(
            query=f"@{BOT_USERNAME} slap -is:retweet lang:en",
            max_results=20,
            tweet_fields=["author_id", "entities", "created_at"],
            expansions=["author_id"],
            user_fields=["username", "description", "profile_image_url"]
        )

        if not tweets.data:
            print("No new slaps – sleep 60s")
            time.sleep(60)
            continue

        for tweet in tweets.data:
            author_id = tweet.author_id
            if author_id == me.id:
                continue

            text = tweet.text.lower()
            if "slap" not in text:
                continue

            # Get mentions — bot is first, target is second (or more)
            mentions_entities = tweet.entities.get("mentions", [])
            if len(mentions_entities) < 2:
                continue  # Need at least bot + one target

            # Target is the second mention (first is bot)
            target_username = mentions_entities[1]["username"]

            # Cooldown check
            now = datetime.now(timezone.utc)
            cooldown_key = f"{author_id}_{target_username}"
            last_use_str = cooldowns.get(cooldown_key)
            if last_use_str:
                last_use = datetime.fromisoformat(last_use_str)
                if now - last_use < timedelta(seconds=COOLDOWN_SECONDS):
                    print(f"Cooldown active for {target_username}")
                    continue

            # Update cooldown
            cooldowns[cooldown_key] = now.isoformat()
            save_cooldowns(cooldowns)

            # Get target info
            target_user = client.get_user(username=target_username, user_fields=["description", "profile_image_url"]).data
            bio_snippet = target_user.description[:60] if target_user.description else ""
            pfp_desc = "unknown"

            # Generate roast
            roast = generate_nuclear_roast(target_username, tweet.author.username, bio_snippet, pfp_desc)

            gif = random.choice(SLAP_GIFS)

            # Reply with short "Powered by Grok" branding
            reply_text = f"@{target_username} {roast}\n\n{gif}\n" \
                         f"Slapped by @{tweet.author.username} — Powered by Grok 🔥"

            client.create_tweet(
                in_reply_to_tweet_id=tweet.id,
                text=reply_text
            )

            print(f"Nuked @{target_username} by @{tweet.author.username}")

        time.sleep(60)

    except Exception as e:
        print("Loop error:", e)
        time.sleep(60)
