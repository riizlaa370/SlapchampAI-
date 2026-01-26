import os
import tweepy
import random
import time
import json
import requests
from datetime import datetime, timezone, timedelta

# ── CONFIG ──────────────────────────────────────────────────────────────
BOT_USERNAME = "slapchampai"           # lowercase!
COOLDOWN_SECONDS = 300

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

# ── X API ───────────────────────────────────────────────────────────────
client = tweepy.Client(
    bearer_token=os.getenv('BEARER_TOKEN'),
    consumer_key=os.getenv('CONSUMER_KEY'),
    consumer_secret=os.getenv('CONSUMER_SECRET'),
    access_token=os.getenv('ACCESS_TOKEN'),
    access_token_secret=os.getenv('ACCESS_TOKEN_SECRET'),
    wait_on_rate_limit=True
)

me = client.get_me().data
print(f"Connected as @{me.username} — SlapchampAI LIVE 🔥")

# ── GROK ROAST ──────────────────────────────────────────────────────────
def generate_nuclear_roast(target_username, attacker_username, bio_snippet="", pfp_desc=""):
    url = "https://api.x.ai/v1/chat/completions"
    headers = {"Authorization": f"Bearer {os.getenv('GROK_API_KEY')}",
               "Content-Type": "application/json"}

    prompt = f"""
    You are Grok — nuclear roast mode. Brutally savage, hilarious, chaotic.
    NO slurs, threats, racism, or ban-worthy content.
    Target: @{target_username}
    Bio snippet: {bio_snippet or 'none'}
    PFP: {pfp_desc or 'unknown'}
    Attacker: @{attacker_username}
    ONE short devastating sentence only.
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
        print("Grok error:", e)
        return f"@{target_username} just got erased from existence 💀🔥"

# ── LOOP ────────────────────────────────────────────────────────────────
print("SlapchampAI polling pure @user slap...")

while True:
    try:
        tweets = client.search_recent_tweets(
            query='"@* slap" -is:retweet lang:en',
            max_results=20,
            tweet_fields=["author_id", "entities", "created_at"],
            expansions=["author_id"],
            user_fields=["username", "description", "profile_image_url"]
        )

        if not tweets.data:
            print("No slaps – sleep 60s")
            time.sleep(60)
            continue

        for tweet in tweets.data:
            author_id = tweet.author_id
            if author_id == me.id: continue

            text = tweet.text.lower()
            if "slap" not in text: continue

            mentions = tweet.entities.get("mentions", [])
            if not mentions: continue

            target = mentions[0]["username"]
            if target.lower() == BOT_USERNAME: continue

            now = datetime.now(timezone.utc)
            key = f"{author_id}_{target}"
            last = cooldowns.get(key)
            if last:
                last_dt = datetime.fromisoformat(last)
                if now - last_dt < timedelta(seconds=COOLDOWN_SECONDS):
                    print(f"Cooldown for {target}")
                    continue

            cooldowns[key] = now.isoformat()
            save_cooldowns(cooldowns)

            user = client.get_user(username=target, user_fields=["description", "profile_image_url"]).data
            bio = user.description[:60] if user.description else ""
            pfp = "unknown"

            roast = generate_nuclear_roast(target, tweet.author.username, bio, pfp)
            gif = random.choice(SLAP_GIFS)

            reply = f"@{target} {roast}\n\n{gif}\nSlapped by @{tweet.author.username} — Powered by @slapchampai 🔥"

            client.create_tweet(in_reply_to_tweet_id=tweet.id, text=reply)
            print(f"Nuked @{target}")

        time.sleep(60)

    except Exception as e:
        print("Error:", e)
        time.sleep(60)
