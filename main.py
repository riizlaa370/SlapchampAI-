import os
import time
import random
from datetime import datetime, timedelta
import json
import requests
import tweepy

# ── Environment variables ───────────────────────────────────────────────────
CONSUMER_KEY = os.environ.get('TWITTER_CONSUMER_KEY')
CONSUMER_SECRET = os.environ.get('TWITTER_CONSUMER_SECRET')
ACCESS_TOKEN = os.environ.get('TWITTER_ACCESS_TOKEN')
ACCESS_TOKEN_SECRET = os.environ.get('TWITTER_ACCESS_TOKEN_SECRET')
GROK_API_KEY = os.environ.get('GROK_API_KEY')
GIPHY_API_KEY = os.environ.get('GIPHY_API_KEY')

# Debug loading status
print(f"Loaded Twitter keys: Consumer {CONSUMER_KEY[:5] if CONSUMER_KEY else 'MISSING'}..., "
      f"Access Token {ACCESS_TOKEN[:5] if ACCESS_TOKEN else 'MISSING'}...")
print(f"GIPHY key present: {'YES' if GIPHY_API_KEY else 'MISSING'}")
print(f"Grok key present: {'YES' if GROK_API_KEY else 'MISSING'}")

if not all([CONSUMER_KEY, CONSUMER_SECRET, ACCESS_TOKEN, ACCESS_TOKEN_SECRET]):
    raise ValueError("Missing Twitter OAuth 1.0a credentials!")

# ── Cooldown persistence ────────────────────────────────────────────────────
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
COOLDOWN_PERIOD = timedelta(hours=4)          # Safe for long-term

# ── Tweepy client ───────────────────────────────────────────────────────────
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
    print(f"Bot authenticated successfully. User ID: {bot_id}")
except Exception as e:
    print(f"Auth failed: {e}")
    raise

# ── Grok roast generator (short & punchy) ──────────────────────────────────
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
        # Force shortness
        if len(roast) > 120:
            roast = roast[:117] + "..."
        return roast
    except Exception as e:
        print(f"Grok error: {e}")
        return f"@{target_username} just got slapped back to the stone age! 💥"

# ── GIPHY GIF fetch ─────────────────────────────────────────────────────────
def get_slap_gif():
    if not GIPHY_API_KEY:
        print("GIPHY_API_KEY is missing!")
        return "https://giphy.com/gifs/slap-classic-cartoon-3o6Zt6KHxJTbXCnSvu"

    url = (
        f"https://api.giphy.com/v1/gifs/search"
        f"?api_key={GIPHY_API_KEY}"
        f"&q=slap"
        f"&limit=10"
        f"&rating=pg"
    )

    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        data = response.json().get('data', [])
        if data:
            gif_url = random.choice(data)['images']['original']['url']
            print(f"GIPHY success: {gif_url[:60]}...")
            return gif_url
        print("GIPHY: No results found")
        return "https://giphy.com/gifs/fallback-slap-classic-3o6Zt6KHxJTbXCnSvu"
    except Exception as e:
        print(f"GIPHY error: {e} - URL: {url}")
        return "https://giphy.com/gifs/fallback-slap-classic-3o6Zt6KHxJTbXCnSvu"

# ── Main polling loop ──────────────────────────────────────────────────────
last_mention_id = None
MAX_REPLIES_PER_POLL = 3
POLL_INTERVAL_SEC = 60                  # 1 minute – safe & sustainable

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
                    print("Max replies this poll reached — skipping rest")
                    break

                text_lower = mention.text.lower()
                if 'slap' not in text_lower or mention.author_id == bot_id:
                    continue

                # Basic anti-spam filter
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

                try:
                    client.create_tweet(text=reply_text, in_reply_to_tweet_id=mention.id)
                    cooldowns[uid] = now.isoformat()
                    save_cooldowns(cooldowns)
                    print(f"Replied to {mention.id} → @{author.username}")
                    reply_count += 1
                    time.sleep(random.uniform(12, 28))  # Anti-spam delay
                except Exception as reply_err:
                    print(f"Reply failed for {mention.id}: {reply_err}")

                last_mention_id = max(last_mention_id or 0, mention.id)

    except Exception as e:
        print(f"Polling error: {e}")
        time.sleep(120)  # Backoff on error

    time.sleep(POLL_INTERVAL_SEC)
