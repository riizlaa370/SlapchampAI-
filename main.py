import os
import time
import tweepy
import random
from datetime import datetime, timedelta
import json
import requests  # For Grok and Tenor APIs

# Load env vars for OAuth 1.0a
CONSUMER_KEY = os.environ.get('TWITTER_CONSUMER_KEY')
CONSUMER_SECRET = os.environ.get('TWITTER_CONSUMER_SECRET')
ACCESS_TOKEN = os.environ.get('TWITTER_ACCESS_TOKEN')
ACCESS_TOKEN_SECRET = os.environ.get('TWITTER_ACCESS_TOKEN_SECRET')
GROK_API_KEY = os.environ.get('GROK_API_KEY')
TENOR_API_KEY = os.environ.get('TENOR_API_KEY')

# Validate vars (debug: prevents NoneType)
if not all([CONSUMER_KEY, CONSUMER_SECRET, ACCESS_TOKEN, ACCESS_TOKEN_SECRET]):
    raise ValueError("Missing OAuth 1.0a credentials—check Railway vars.")

# Persistent storage (volume for cooldowns only)
DATA_DIR = '/app/data'
COOLDOWNS_FILE = os.path.join(DATA_DIR, 'cooldowns.json')
os.makedirs(DATA_DIR, exist_ok=True)

# Load/save cooldowns
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

# Tweepy Client init (pure OAuth 1.0a User Context)
client = tweepy.Client(
    consumer_key=CONSUMER_KEY,
    consumer_secret=CONSUMER_SECRET,
    access_token=ACCESS_TOKEN,
    access_token_secret=ACCESS_TOKEN_SECRET
)

# Get bot user ID (test auth early)
try:
    bot_user = client.get_me()
    bot_id = bot_user.data.id
    print(f"Bot authenticated successfully. User ID: {bot_id}")
except Exception as e:
    raise ValueError(f"Auth test failed: {e}—check credentials/permissions.")

# Grok roast function
def get_grok_roast(target_username):
    url = "https://api.x.ai/v1/chat/completions"
    headers = {"Authorization": f"Bearer {GROK_API_KEY}", "Content-Type": "application/json"}
    data = {
        "model": "grok-beta",
        "messages": [{"role": "user", "content": f"Generate a funny, light-hearted roast for X user @{target_username} involving a slap."}]
    }
    response = requests.post(url, headers=headers, json=data)
    if response.status_code == 200:
        return response.json()['choices'][0]['message']['content'].strip()
    print(f"Grok error: {response.status_code} - {response.text}")
    return "You're so slappable, even this AI glitched out!"

# Tenor GIF function
def get_slap_gif():
    url = f"https://tenor.googleapis.com/v2/search?q=slap&key={TENOR_API_KEY}&limit=10"
    response = requests.get(url)
    if response.status_code == 200:
        gifs = response.json()['results']
        if gifs:
            return random.choice(gifs)['media_formats']['gif']['url']
    print(f"Tenor error: {response.status_code}")
    return "https://tenor.com/view/fallback-slap-gif"  # Static fallback

# Main polling loop
last_mention_id = None
while True:
    try:
        mentions = client.get_users_mentions(
            bot_id,
            since_id=last_mention_id,
            expansions=['author_id'],
            tweet_fields=['text']
        )
        if mentions.data:
            for mention in mentions.data:
                if 'slap' in mention.text.lower() and mention.author_id != bot_id:
                    user_id = mention.author_id
                    if user_id in cooldowns and datetime.now() - datetime.fromisoformat(cooldowns[user_id]) < COOLDOWN_PERIOD:
                        print(f"User {user_id} on cooldown—skipping.")
                        continue
                    # Get author (safe fallback if includes missing)
                    author = next((u for u in mentions.includes.get('users', []) if u.id == user_id), None)
                    if author:
                        roast = get_grok_roast(author.username)
                        gif_url = get_slap_gif()
                        reply_text = f"@{author.username} {roast} 💥\n{gif_url}"
                        client.create_tweet(text=reply_text, in_reply_to_tweet_id=mention.id)
                        cooldowns[user_id] = datetime.now().isoformat()
                        save_cooldowns(cooldowns)
                        print(f"Replied to mention {mention.id} for @{author.username}")
                last_mention_id = max(last_mention_id or 0, mention.id)
    except tweepy.TweepyException as e:
        print(f"API error: {e}—sleeping longer.")
        time.sleep(60)  # Backoff on rate limits/errors
    except Exception as e:
        print(f"Unexpected error: {e}")
    time.sleep(15)  # Normal poll interval
