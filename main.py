import os
import time
import random
import re
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
GIPHY_API_KEY = os.environ.get('GIPHY_API_KEY')

print(f"Loaded: Twitter OK | GIPHY {'YES' if GIPHY_API_KEY else 'MISSING'} | Grok {'YES' if GROK_API_KEY else 'MISSING'}")

if not all([CONSUMER_KEY, CONSUMER_SECRET, ACCESS_TOKEN, ACCESS_TOKEN_SECRET]):
    raise ValueError("Missing Twitter OAuth vars!")

# ── Persistence (volume) ────────────────────────────────────────────────────
DATA_DIR = '/app/data'
COOLDOWNS_FILE = os.path.join(DATA_DIR, 'cooldowns.json')
LAST_MENTION_FILE = os.path.join(DATA_DIR, 'last_mention_id.json')
os.makedirs(DATA_DIR, exist_ok=True)

def load_cooldowns():
    if os.path.exists(COOLDOWNS_FILE):
        with open(COOLDOWNS_FILE, 'r') as f:
            return json.load(f)
    return {}

def save_cooldowns(cooldowns):
    with open(COOLDOWNS_FILE, 'w') as f:
        json.dump(cooldowns, f)

def load_last_mention_id():
    if os.path.exists(LAST_MENTION_FILE):
        with open(LAST_MENTION_FILE, 'r') as f:
            data = json.load(f)
            return data.get('last_id')
    return None

def save_last_mention_id(last_id):
    with open(LAST_MENTION_FILE, 'w') as f:
        json.dump({'last_id': last_id}, f)

cooldowns = load_cooldowns()
last_mention_id = load_last_mention_id() or None
print(f"Loaded last_mention_id: {last_mention_id}")

COOLDOWN_PERIOD = timedelta(hours=4)

# ── Tweepy ──────────────────────────────────────────────────────────────────
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
    print(f"Authenticated. Bot ID: {bot_id}")
except Exception as e:
    print(f"Auth fail: {e}")
    raise

# ── Extract targets ─────────────────────────────────────────────────────────
def extract_targets(text, bot_username):
    mentions = re.findall(r'@(\w+)', text)
    targets = [u for u in mentions if u.lower() != bot_username.lower()]
    return list(set(targets))  # unique

# ── Get bio ─────────────────────────────────────────────────────────────────
def get_user_bio(username):
    try:
        user = client.get_user(username=username, user_fields=['description'])
        return user.data.description.strip()[:200] if user.data and user.data.description else "No bio"
    except Exception as e:
        print(f"Bio fetch fail @{username}: {e}")
        return "No bio"

# ── Grok roast ──────────────────────────────────────────────────────────────
def get_grok_roast(target_username, target_bio):
    bio_snippet = target_bio[:150] if target_bio else "no bio"
    prompt = (
        f"Short, funny, light-hearted one-sentence roast for @{target_username}. "
        f"Use this bio: '{bio_snippet}'. Involve a slap. Max 20 words."
    )
    url = "https://api.x.ai/v1/chat/completions"
    headers = {"Authorization": f"Bearer {GROK_API_KEY}", "Content-Type": "application/json"}
    payload = {
        "model": "grok-3-mini",
        "messages": [{"role": "user", "content": prompt}]
    }
    try:
        r = requests.post(url, headers=headers, json=payload, timeout=12)
        r.raise_for_status()
        roast = r.json()['choices'][0]['message']['content'].strip()
        return roast[:120] + "..." if len(roast) > 120 else roast
    except Exception as e:
        print(f"Grok fail: {e}")
        return f"@{target_username} just got slapped into next week! 💥"

# ── GIPHY GIF ───────────────────────────────────────────────────────────────
def get_slap_gif():
    if not GIPHY_API_KEY:
        print("GIPHY key missing!")
        return "https://giphy.com/gifs/slap-classic-cartoon-3o6Zt6KHxJTbXCnSvu"

    url = f"https://api.giphy.com/v1/gifs/search?api_key={GIPHY_API_KEY}&q=slap&limit=10&rating=pg"
    try:
        r = requests.get(url, timeout=10)
        r.raise_for_status()
        data = r.json().get('data', [])
        if data:
            gif = random.choice(data)['images']['fixed_height']['url']
            print(f"GIPHY OK: {gif[:80]}...")
            return gif
        return "https://giphy.com/gifs/fallback-slap-3o6Zt6KHxJTbXCnSvu"
    except Exception as e:
        print(f"GIPHY error: {e}")
        return "https://giphy.com/gifs/fallback-slap-3o6Zt6KHxJTbXCnSvu"

# ── Polling ─────────────────────────────────────────────────────────────────
bot_username = "slapchampai"
MAX_REPLIES_PER_POLL = 3
POLL_INTERVAL_SEC = 999999999999999

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
                    print("Max replies this poll — skip rest")
                    break

                text_lower = mention.text.lower()
                if 'slap' not in text_lower or mention.author_id == bot_id:
                    continue

                if len(text_lower.strip()) < 8 or text_lower.count('slap') > 3:
                    print(f"Skip suspicious {mention.id}")
                    continue

                uid = mention.author_id
                now = datetime.now()
                if uid in cooldowns and now - datetime.fromisoformat(cooldowns[uid]) < COOLDOWN_PERIOD:
                    print(f"Cooldown skip {uid}")
                    continue

                targets = extract_targets(mention.text, bot_username)
                if not targets:
                    print(f"No targets in {mention.id}")
                    continue

                # Roast first target
                target_username = targets[0]
                target_bio = get_user_bio(target_username)
                roast = get_grok_roast(target_username, target_bio)

                gif = get_slap_gif()

                # Signature (Unicode font: monospace/bold-ish)
                signature = " 𝚙𝚘𝚠𝚎𝚛𝚎𝚍 𝚋𝚢 𝚐𝚛𝚘𝚔😈"

                # Reply text: roast target + signature at end
                poster = next((u for u in mentions.includes.get('users', []) if u.id == uid), None)
                poster_tag = f"@{poster.username} " if poster else ""
                reply_text = f"{poster_tag}@{target_username} {roast}{signature}\n{gif}"

                try:
                    client.create_tweet(text=reply_text, in_reply_to_tweet_id=mention.id)
                    cooldowns[uid] = now.isoformat()  # Cooldown on poster
                    save_cooldowns(cooldowns)
                    print(f"Replied {mention.id} — roasted @{target_username}")
                    reply_count += 1
                    time.sleep(random.uniform(12, 28))
                except Exception as reply_err:
                    print(f"Reply fail {mention.id}: {reply_err}")

            # Save last ID
            if mentions.data:
                last_mention_id = max(last_mention_id or 0, max(m.id for m in mentions.data))
                save_last_mention_id(last_mention_id)
                print(f"Saved last_mention_id: {last_mention_id}")

    except Exception as e:
        print(f"Poll error: {e}")
        time.sleep(120)

    time.sleep(POLL_INTERVAL_SEC)
