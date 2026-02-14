import os
import time
import tweepy
import random
from datetime import datetime, timedelta
import json
import requests

# Env vars
CONSUMER_KEY = os.environ.get('TWITTER_CONSUMER_KEY')
CONSUMER_SECRET = os.environ.get('TWITTER_CONSUMER_SECRET')
ACCESS_TOKEN = os.environ.get('TWITTER_ACCESS_TOKEN')
ACCESS_TOKEN_SECRET = os.environ.get('TWITTER_ACCESS_TOKEN_SECRET')
GROK_API_KEY = os.environ.get('GROK_API_KEY')
TENOR_API_KEY = os.environ.get('TENOR_API_KEY')

print(f"Loaded keys: Consumer Key {CONSUMER_KEY[:5] if CONSUMER_KEY else 'MISSING'}..., "
      f"Access Token {ACCESS_TOKEN[:5] if ACCESS_TOKEN else 'MISSING'}..., "
      f"Tenor Key {TENOR_API_KEY[:5] if TENOR_API_KEY else 'MISSING/NONE'}...")

if not all([CONSUMER_KEY, CONSUMER_SECRET, ACCESS_TOKEN, ACCESS_TOKEN_SECRET]):
    raise ValueError("Missing Twitter OAuth 1.0a vars!")

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
COOLDOWN_PERIOD = timedelta(hours=2)  # Increased to reduce spam risk

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
    print(f"Auth fail: {e}")
    raise

# Grok roast (updated model)
def get_grok_roast(target_username):
    url = "https://api.x.ai/v1/chat/completions"
    headers = {"Authorization": f"Bearer {GROK_API_KEY}", "Content-Type": "application/json"}
    payload = {
        "model": "grok-3-mini",  # Valid 2026 model; change to grok-4 if you have access
        "messages": [{"role": "user", "content": f"Generate a funny, light-hearted roast for X user @{target_username} involving a slap. Keep it short and playful."}]
    }
    print("Grok payload:", payload)  # Debug
    try:
        response = requests.post(url, headers=headers, json=payload, timeout=15)
        response.raise_for_status()
        return response.json()['choices'][0]['message']['content'].strip()
    except Exception as err:
        print(f"Grok failed: {err} - Response: {response.text if 'response' in locals() else 'No resp'}")
        return f"@{target_username} just earned a classic slap! 💥 (Grok is napping)"

# Tenor GIF
def get_slap_gif():
    if not TENOR_API_KEY or TENOR_API_KEY == "None":
        print("Tenor key missing!")
        return "https://tenor.com/view/slap-fallback-gif"
    url = f"https://tenor.googleapis.com/v2/search?q=slap&key={TENOR_API_KEY}&limit=10&client_key=slapchampai-bot"
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        gifs = response.json().get('results', [])
        return random.choice(gifs)['media_formats']['gif']['url'] if gifs else "https://tenor.com/view/fallback-slap"
    except Exception as err:
        print(f"Tenor failed: {err} - URL was {url}")
        return "https://tenor.com/view/fallback-slap"

# Polling
last_mention_id = None
MAX_REPLIES_PER_POLL = 5
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
        print(f"Polling OK - {len(mentions.data or [])} new mentions")

        if mentions.data:
            reply_count = 0
            for mention in mentions.data:
                if reply_count >= MAX_REPLIES_PER_POLL:
                    print("Max replies per poll reached - skipping rest")
                    break
                if 'slap' in mention.text.lower() and mention.author_id != bot_id:
                    user_id = mention.author_id
                    if user_id in cooldowns and datetime.now() - datetime.fromisoformat(cooldowns[user_id]) < COOLDOWN_PERIOD:
                        print(f"Cooldown skip: {user_id}")
                        continue
                    author = next((u for u in mentions.includes.get('users', []) if u.id == user_id), None)
                    if author:
                        roast = get_grok_roast(author.username)
                        gif_url = get_slap_gif()
                        reply_text = f"@{author.username} {roast} 💥\n{gif_url}"
                        client.create_tweet(text=reply_text, in_reply_to_tweet_id=mention.id)
                        cooldowns[user_id] = datetime.now().isoformat()
                        save_cooldowns(cooldowns)
                        print(f"Replied to {mention.id} for @{author.username}")
                        reply_count += 1
                        time.sleep(10)  # Delay between replies to avoid spam flag
                last_mention_id = max(last_mention_id or 0, mention.id)
    except Exception as e:
        print(f"Polling error: {e}")
        time.sleep(60)
    time.sleep(30)  # Slower poll to reduce load
