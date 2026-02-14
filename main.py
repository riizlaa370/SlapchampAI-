import os
import time
import random
from datetime import datetime, timedelta
import json
import requests
import tweepy

# ── Env vars ────────────────────────────────────────────────────────────────
CONSUMER_KEY = os.environ.get('TWITTER_CONSUMER_KEY')
CONSUMER_SECRET = os.environ.get('TWITTER_CONSUMER_SECRET')
ACCESS_TOKEN = os.environ.get('TWITTER_ACCESS_TOKEN')
ACCESS_TOKEN_SECRET = os.environ.get('TWITTER_ACCESS_TOKEN_SECRET')
GROK_API_KEY = os.environ.get('GROK_API_KEY')
TENOR_API_KEY = os.environ.get('TENOR_API_KEY')

if not all([CONSUMER_KEY, CONSUMER_SECRET, ACCESS_TOKEN, ACCESS_TOKEN_SECRET]):
    raise ValueError("Missing Twitter OAuth 1.0a credentials!")

print(f"Tenor key present: {'YES' if TENOR_API_KEY and TENOR_API_KEY != 'None' else 'MISSING'}")

# ── Persistence ─────────────────────────────────────────────────────────────
DATA_DIR = '/app/data'
COOLDOWNS_FILE = os.path.join(DATA_DIR, 'cooldowns.json')
os.makedirs(DATA_DIR, exist_ok=True)

def load_cooldowns():
    if os.path.exists(COOLDOWNS_FILE):
        with open(COOLDOWNS_FILE, 'r') as f:
            return json.load(f)
    return {}

def save_cooldowns(cooldowns):
    with open(COOLDOWNS_FILE, 'w') as f:
        json.dump(cooldowns, f)

cooldowns = load_cooldowns()
COOLDOWN_PERIOD = timedelta(hours=4)         # ← increased for long-term safety

# ── Tweepy Client ───────────────────────────────────────────────────────────
client = tweepy.Client(
    consumer_key=CONSUMER_KEY,
    consumer_secret=CONSUMER_SECRET,
    access_token=ACCESS_TOKEN,
    access_token_secret=ACCESS_TOKEN_SECRET,
    wait_on_rate_limit=True
)

try:
    bot_user = client.get_me(user_auth=True)
    bot_id = bot_user.data.id
    print(f"Bot authenticated. ID: {bot_id}")
except Exception as e:
    print(f"Auth failed: {e}")
    raise

# ── Grok roast (short & punchy) ────────────────────────────────────────────
def get_grok_roast(target_username):
    url = "https://api.x.ai/v1/chat/completions"
    headers = {"Authorization": f"Bearer {GROK_API_KEY}", "Content-Type": "application/json"}
    payload = {
        "model": "grok-3-mini",
        "messages": [{
            "role": "user",
            "content": f"Short, funny, light-hearted one-sentence roast for @{target_username} involving a slap. Max 20 words."
        }]
    }
    try:
        resp = requests.post(url, headers=headers, json=payload, timeout=12)
        resp.raise_for_status()
        roast = resp.json()['choices'][0]['message']['content'].strip()
        # Enforce shortness
        if len(roast) > 120:
            roast = roast[:117] + "..."
        return roast
    except Exception as e:
        print(f"Grok error: {e}")
        return "deserves a classic cartoon slap! 💥"

# ── Tenor GIF ───────────────────────────────────────────────────────────────
def get_slap_gif():
    if not TENOR_API_KEY or TENOR_API_KEY == 'None':
        print("Tenor key missing!")
        return "https://tenor.com/view/slap-classic-cartoon-gif"
    url = f"https://tenor.googleapis.com/v2/search?q=slap&key={TENOR_API_KEY}&limit=8&client_key=slapchampai"
    try:
        r = requests.get(url, timeout=8)
        r.raise_for_status()
        gifs = r.json().get('results', [])
        return random.choice(gifs)['media_formats']['gif']['url'] if gifs else "https://tenor.com/view/fallback-slap"
    except Exception as e:
        print(f"Tenor failed: {e}")
        return "https://tenor.com/view/fallback-slap"

# ── Main loop ───────────────────────────────────────────────────────────────
last_mention_id = None
MAX_REPLIES_PER_POLL = 3          # ← strict anti-spam cap
POLL_INTERVAL_SEC = 60            # ← increased from 15s

while True:
    try:
        mentions = client.get_users_mentions(
            id=bot_id,
            since_id=last_mention_id,
            expansions=['author_id'],
            tweet_fields=['text'],
            max_results=50,
            user_auth=True
        )

        count = len(mentions.data or [])
        print(f"Poll OK — {count} new mentions")

        if mentions.data:
            reply_count = 0
            for mention in mentions.data:
                if reply_count >= MAX_REPLIES_PER_POLL:
                    print("Max replies this poll — skipping rest")
                    break

                text_lower = mention.text.lower()
                if 'slap' not in text_lower or mention.author_id == bot_id:
                    continue

                # Very basic spam filter (short/repetitive mentions)
                if len(text_lower.strip()) < 8 or text_lower.count('slap') > 3:
                    print(f"Skipping suspicious mention {mention.id}")
                    continue

                uid = mention.author_id
                now = datetime.now()
                if uid in cooldowns and now - datetime.fromisoformat(cooldowns[uid]) < COOLDOWN_PERIOD:
                    print(f"Cooldown skip: {uid}")
                    continue

                author = next((u for u in mentions.includes.get('users', []) if u.id == uid), None)
                if not author:
                    continue

                roast = get_grok_roast(author.username)
                gif = get_slap_gif()
                reply_text = f"@{author.username} {roast} 💥\n{gif}"

                client.create_tweet(text=reply_text, in_reply_to_tweet_id=mention.id)
                cooldowns[uid] = now.isoformat()
                save_cooldowns(cooldowns)
                print(f"Replied to {mention.id} → @{author.username}")

                reply_count += 1
                time.sleep(random.uniform(12, 28))  # random delay between replies

            last_mention_id = max(last_mention_id or 0, mention.id)

    except Exception as e:
        print(f"Poll error: {e}")
        time.sleep(120)  # longer backoff on error

    time.sleep(POLL_INTERVAL_SEC)
