import os
import time
import tweepy
import random
from datetime import datetime, timedelta
import json
import requests

# Load env vars
CONSUMER_KEY = os.environ.get('TWITTER_CONSUMER_KEY')
CONSUMER_SECRET = os.environ.get('TWITTER_CONSUMER_SECRET')
ACCESS_TOKEN = os.environ.get('TWITTER_ACCESS_TOKEN')
ACCESS_TOKEN_SECRET = os.environ.get('TWITTER_ACCESS_TOKEN_SECRET')
GROK_API_KEY = os.environ.get('GROK_API_KEY')
TENOR_API_KEY = os.environ.get('TENOR_API_KEY')

# Debug: Print partial keys to confirm loading (remove in prod)
print(f"Loaded keys: Consumer Key starts {CONSUMER_KEY[:5] if CONSUMER_KEY else 'None'}..., "
      f"Access Token starts {ACCESS_TOKEN[:5] if ACCESS_TOKEN else 'None'}...")

if not all([CONSUMER_KEY, CONSUMER_SECRET, ACCESS_TOKEN, ACCESS_TOKEN_SECRET]):
    raise ValueError("Missing OAuth 1.0a credentials in env vars!")

# Persistent cooldowns
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
COOLDOWN_PERIOD = timedelta(hours=1)

# Tweepy Client with rate limit handling
client = tweepy.Client(
    consumer_key=CONSUMER_KEY,
    consumer_secret=CONSUMER_SECRET,
    access_token=ACCESS_TOKEN,
    access_token_secret=ACCESS_TOKEN_SECRET,
    wait_on_rate_limit=True  # Auto-sleep on 429
)

# Auth test
try:
    bot_user = client.get_me(user_auth=True)
    bot_id = bot_user.data.id
    print(f"Bot authenticated successfully. User ID: {bot_id}")
except tweepy.TweepyException as e:
    print(f"get_me failed: {e}")
    print(f"Full exception: {repr(e)}")
    raise

# Debug: Try a minimal mentions call early
try:
    test_mentions = client.get_users_mentions(
        id=bot_id,
        max_results=5,
        tweet_fields=['text'],
        user_auth=True
    )
    print(f"Test mentions call succeeded: {len(test_mentions.data or [])} mentions found")
except tweepy.TweepyException as e:
    print(f"Test get_users_mentions failed with: {e}")
    if hasattr(e, 'response') and e.response is not None:
        print(f"Status code: {e.response.status_code}")
        print(f"Response text: {e.response.text}")
        print(f"Headers: {e.response.headers}")
    raise

# Grok roast
def get_grok_roast(target_username):
    url = "https://api.x.ai/v1/chat/completions"
    headers = {"Authorization": f"Bearer {GROK_API_KEY}", "Content-Type": "application/json"}
    data = {
        "model": "grok-beta",
        "messages": [{"role": "user", "content": f"Generate a funny, light-hearted roast for X user @{target_username} involving a slap."}]
    }
    try:
        response = requests.post(url, headers=headers, json=data, timeout=10)
        response.raise_for_status()
        return response.json()['choices'][0]['message']['content'].strip()
    except Exception as err:
        print(f"Grok error: {err}")
        return "You're so slappable, even Grok short-circuited!"

# Tenor GIF
def get_slap_gif():
    url = f"https://tenor.googleapis.com/v2/search?q=slap&key={TENOR_API_KEY}&limit=10"
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        gifs = response.json()['results']
        return random.choice(gifs)['media_formats']['gif']['url'] if gifs else "https://tenor.com/view/fallback-slap-gif"
    except Exception as err:
        print(f"Tenor error: {err}")
        return "https://tenor.com/view/fallback-slap-gif"

# Polling loop with enhanced error handling
last_mention_id = None
while True:
    try:
        mentions = client.get_users_mentions(
            id=bot_id,
            since_id=last_mention_id,
            expansions=['author_id'],
            tweet_fields=['text'],
            max_results=100,  # Higher to catch more if allowed
            user_auth=True
        )
        print(f"Polling succeeded - found {len(mentions.data or [])} new mentions")

        if mentions.data:
            for mention in mentions.data:
                if 'slap' in mention.text.lower() and mention.author_id != bot_id:
                    user_id = mention.author_id
                    if user_id in cooldowns and datetime.now() - datetime.fromisoformat(cooldowns[user_id]) < COOLDOWN_PERIOD:
                        print(f"Cooldown skip for user {user_id}")
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
                last_mention_id = max(last_mention_id or 0, mention.id)
    except tweepy.TooManyRequests as e:
        print(f"Rate limit hit: {e} - sleeping 15 min")
        time.sleep(900)
    except tweepy.TweepyException as e:
        print(f"Tweepy API error during polling: {e}")
        if hasattr(e, 'response') and e.response:
            print(f"Status: {e.response.status_code}")
            print(f"Response body: {e.response.text}")
            print(f"Headers: {e.response.headers}")
        if e.response and e.response.status_code in (401, 403):
            print("401/403 detected - likely permissions/tier issue. Check X app settings & tier.")
            time.sleep(300)  # 5 min backoff
        else:
            time.sleep(60)
    except Exception as e:
        print(f"Unexpected error: {e}")
        time.sleep(60)
    time.sleep(15)
