import os
import sys
import tweepy
import random
import time
import json
from datetime import datetime, timezone, timedelta
from openai import OpenAI
import requests
import base64
import threading

# ────────────────────────────────────────────────
# CONFIG
# ────────────────────────────────────────────────
BOT_USERNAME = "slapchampai"
COOLDOWN_SECONDS = 300
COOLDOWN_FILE = "cooldowns.json"
POLL_INTERVAL = 180           # Poll mentions every 3 min
REFRESH_INTERVAL = 3600       # Refresh access_token every 60 min
GIF_PROBABILITY = 0.30

SLAP_GIFS = [
    "https://tenor.com/view/slap-hard-slap-gif-22345678",
    "https://tenor.com/view/slap-gif-18481503",
    "https://tenor.com/view/slap-gif-19910281",
    "https://tenor.com/view/will-smith-slap-gif-24798075",
    "https://tenor.com/view/anime-slap-gif-19910282",
]

# ────────────────────────────────────────────────
# Grok API client
# ────────────────────────────────────────────────
grok_client = OpenAI(
    api_key=os.getenv("GROK_API_KEY"),
    base_url="https://api.x.ai/v1",
)

# ────────────────────────────────────────────────
# Cooldown helpers
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
            json.dump(cooldowns, f)
    except Exception as e:
        print(f"Failed to save cooldowns: {e}", file=sys.stderr)

cooldowns = load_cooldowns()

# ────────────────────────────────────────────────
# Global Tweepy client
# ────────────────────────────────────────────────
client = None

# ────────────────────────────────────────────────
# Manual Refresh Function - Uses OAUTH_REFRESH_TOKEN
# ────────────────────────────────────────────────
def refresh_access_token():
    global client

    client_id = os.getenv("TWITTER_CLIENT_ID")
    refresh_token = os.getenv("OAUTH_REFRESH_TOKEN") or os.getenv("TWITTER_REFRESH_TOKEN")  # detect both names
    client_secret = os.getenv("TWITTER_CLIENT_SECRET")

    print(f"Loaded TWITTER_CLIENT_ID: {'present' if client_id else 'MISSING'}", file=sys.stderr)
    print(f"Loaded refresh token from OAUTH_REFRESH_TOKEN or TWITTER_REFRESH_TOKEN: {'present' if refresh_token else 'MISSING'}", file=sys.stderr)
    print(f"Refresh token length: {len(refresh_token) if refresh_token else 0}", file=sys.stderr)
    print(f"Loaded TWITTER_CLIENT_SECRET: {'present' if client_secret else 'MISSING - REQUIRED'}", file=sys.stderr)

    if not client_id or not refresh_token:
        print("Missing TWITTER_CLIENT_ID or refresh token", file=sys.stderr)
        return False

    refresh_url = "https://api.twitter.com/2/oauth2/token"

    data = {
        "refresh_token": refresh_token,
        "grant_type": "refresh_token",
        "client_id": client_id,
    }

    headers = {
        "Content-Type": "application/x-www-form-urlencoded"
    }

    auth = None
    if client_secret:
        auth_str = f"{client_id}:{client_secret}"
        auth_b64 = base64.b64encode(auth_str.encode()).decode()
        headers["Authorization"] = f"Basic {auth_b64}"
        print("Added Basic Auth header", file=sys.stderr)

    for attempt in range(3):
        try:
            print(f"Refreshing access token (attempt {attempt + 1}/3)...", file=sys.stderr)
            response = requests.post(refresh_url, data=data, headers=headers, auth=auth)
            print(f"Response status: {response.status_code}", file=sys.stderr)

            if response.status_code == 200:
                token_response = response.json()
                print("Full token response:", token_response, file=sys.stderr)

                access_token = token_response["access_token"]

                if "refresh_token" in token_response:
                    new_refresh = token_response["refresh_token"]
                    print(f"!!! REFRESH TOKEN ROTATED !!! New: {new_refresh}", file=sys.stderr)
                    print("UPDATE RAILWAY WITH NEW OAUTH_REFRESH_TOKEN AND REDEPLOY!", file=sys.stderr)

                client = tweepy.Client(
                    bearer_token=access_token,
                    wait_on_rate_limit=True
                )
                print("Refresh successful - client updated", file=sys.stderr)
                return True
            else:
                print(f"Refresh failed - Status: {response.status_code}", file=sys.stderr)
                print(f"Body: {response.text}", file=sys.stderr)
                if attempt < 2:
                    time.sleep(10)

        except Exception as e:
            print(f"Refresh exception: {e}", file=sys.stderr)

    return False

# ────────────────────────────────────────────────
# Background Refresh Thread
# ────────────────────────────────────────────────
def background_refresh():
    while True:
        time.sleep(REFRESH_INTERVAL)
        if not refresh_access_token():
            print("Background refresh failed - retrying next cycle", file=sys.stderr)

threading.Thread(target=background_refresh, daemon=True).start()

# Initial refresh
if not refresh_access_token():
    print("Initial refresh failed - exiting", file=sys.stderr)
    sys.exit(1)

# ────────────────────────────────────────────────
# Verify auth + TEST POST
# ────────────────────────────────────────────────
try:
    me = client.get_me().data
    print(f"Connected as @{me.username}", file=sys.stderr)

    print("Running one-time write test...", file=sys.stderr)
    test_response = client.create_tweet(
        text="Test write from SlapchampAI – please ignore this #debug"
    )
    print(f"TEST POST SUCCESS – Tweet ID: {test_response.data['id']}", file=sys.stderr)
except Exception as e:
    print(f"Auth/test failed: {e}", file=sys.stderr)
    sys.exit(1)

# ────────────────────────────────────────────────
# Real Grok roast generator
# ────────────────────────────────────────────────
def generate_nuclear_roast(target_username, attacker_username, bio_snippet=""):
    if not grok_client.api_key:
        return f"@{target_username} got slapped into next week! (API key issue) 🔥"

    try:
        prompt = f"""
Brutal savage roast for @{target_username}.
Bio snippet (use if funny): "{bio_snippet}"
Max 50 words. Nuclear mean, personal, hilarious, no mercy.
End with 🔥
From: @{attacker_username}
""".strip()

        response = grok_client.chat.completions.create(
            model="grok-beta",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=70,
            temperature=0.9,
        )

        roast = response.choices[0].message.content.strip()
        return roast[:190]

    except Exception as e:
        print(f"Grok API error: {e}", file=sys.stderr)
        return f"@{target_username} your vibe is straight landfill. Roasted. 🔥"

# ────────────────────────────────────────────────
# Main polling loop
# ────────────────────────────────────────────────
print("Polling started – listening for any @slapchampai mention containing 'slap'", file=sys.stderr)
since_id = 1

while True:
    try:
        tweets = client.search_recent_tweets(
            query=f"@{BOT_USERNAME} slap -is:retweet lang:en",
            max_results=10,
            since_id=since_id,
            tweet_fields=["author_id", "entities", "id", "created_at"],
            expansions=["author_id"],
            user_fields=["username", "description"]
        )

        if tweets.data:
            since_id = max(t.id for t in tweets.data)

            for tweet in tweets.data:
                if tweet.author_id == me['id']:
                    continue

                text = tweet.text.lower()
                if "slap" not in text:
                    continue

                mentions = tweet.entities.get("mentions", [])
                target_username = None
                for mention in mentions:
                    if mention["username"].lower() != BOT_USERNAME.lower():
                        target_username = mention["username"]
                        break

                if not target_username:
                    continue

                now = datetime.now(timezone.utc)
                key = f"{tweet.author_id}_{target_username}"
                if key in cooldowns:
                    last = datetime.fromisoformat(cooldowns[key])
                    if now - last < timedelta(seconds=COOLDOWN_SECONDS):
                        print(f"Cooldown active for {key}", file=sys.stderr)
                        continue

                cooldowns[key] = now.isoformat()
                save_cooldowns(cooldowns)

                try:
                    target_user = client.get_user(username=target_username, user_fields=["description"]).data
                    bio_snippet = target_user.description[:60] if target_user and target_user.description else ""
                except:
                    bio_snippet = ""

                roast = generate_nuclear_roast(
                    target_username,
                    tweet.author.username if tweets.includes and 'users' in tweets.includes else "someone",
                    bio_snippet
                )

                gif = random.choice(SLAP_GIFS) if random.random() < GIF_PROBABILITY else ""

                reply_text = f"@{target_username} {roast}\n\n{gif}\n— @{tweet.author.username} 🔥"
                reply_text = reply_text[:270]

                try:
                    resp = client.create_tweet(
                        text=reply_text,
                        in_reply_to_tweet_id=tweet.id
                    )
                    print(f"Slapped @{target_username} - Reply ID: {resp.data['id']}", file=sys.stderr)
                except tweepy.TweepyException as e:
                    print(f"Reply failed: {e}", file=sys.stderr)
                    if hasattr(e, 'response') and e.response:
                        print(f"Status: {e.response.status_code} | Body: {e.response.text}", file=sys.stderr)

        else:
            print("No new mentions found", file=sys.stderr)

        time.sleep(POLL_INTERVAL)

    except tweepy.TooManyRequests:
        print("Rate limit hit - sleeping 15 min", file=sys.stderr)
        time.sleep(900)
    except tweepy.TweepyException as e:
        print(f"Loop error (Tweepy): {e}", file=sys.stderr)
        if hasattr(e, 'response') and e.response:
            print(f"Status: {e.response.status_code} | Body: {e.response.text}", file=sys.stderr)
        time.sleep(180)
    except Exception as e:
        print(f"Unexpected loop error: {e}", file=sys.stderr)
        time.sleep(180)
