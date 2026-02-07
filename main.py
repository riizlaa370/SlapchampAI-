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

# ────────────────────────────────────────────────
# CONFIG
# ────────────────────────────────────────────────
BOT_USERNAME = "slapchampai"
COOLDOWN_SECONDS = 300
COOLDOWN_FILE = "cooldowns.json"
POLL_INTERVAL = 180           # 3 minutes - low read usage
GIF_PROBABILITY = 0.30

SLAP_GIFS = [
    "https://tenor.com/view/slap-hard-slap-gif-22345678",
    "https://tenor.com/view/anime-slap-gif-12345678",
    "https://tenor.com/view/funny-slap-cat-gif-98765432",
    "https://tenor.com/view/will-smith-slap-chris-rock-gif-24798075",
    "https://tenor.com/view/slap-gif-19910281",
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
# X OAuth 2.0 User Context Setup with Manual Refresh
# ────────────────────────────────────────────────
client_id = os.getenv("TWITTER_CLIENT_ID")
refresh_token = os.getenv("TWITTER_REFRESH_TOKEN")
client_secret = os.getenv("TWITTER_CLIENT_SECRET")  # Required for Confidential apps

print(f"Loaded TWITTER_CLIENT_ID: {'present' if client_id else 'MISSING'}", file=sys.stderr)
print(f"Loaded TWITTER_REFRESH_TOKEN: {'present' if refresh_token else 'MISSING'}", file=sys.stderr)
print(f"Loaded TWITTER_CLIENT_SECRET: {'present' if client_secret else 'MISSING - REQUIRED for refresh!'}", file=sys.stderr)
print(f"Refresh token length: {len(refresh_token) if refresh_token else 0} chars | Starts with: {refresh_token[:10] if refresh_token else 'N/A'}...", file=sys.stderr)

if not client_id or not refresh_token:
    print("Missing TWITTER_CLIENT_ID or TWITTER_REFRESH_TOKEN", file=sys.stderr)
    sys.exit(1)

if not client_secret:
    print("WARNING: TWITTER_CLIENT_SECRET missing – add it in Railway (needed for 400 fix)", file=sys.stderr)

refresh_url = "https://api.twitter.com/2/oauth2/token"

data = {
    "refresh_token": refresh_token,
    "grant_type": "refresh_token",
    "client_id": client_id,
}

headers = {
    "Content-Type": "application/x-www-form-urlencoded"
}

# Basic Auth header (fixes 400 for Confidential apps)
auth = None
if client_secret:
    auth_str = f"{client_id}:{client_secret}"
    auth_b64 = base64.b64encode(auth_str.encode()).decode()
    headers["Authorization"] = f"Basic {auth_b64}"
    print("Added Basic Auth header for refresh (client_id:client_secret)", file=sys.stderr)

try:
    print("Attempting manual refresh...", file=sys.stderr)
    response = requests.post(refresh_url, data=data, headers=headers, auth=auth)
    response.raise_for_status()
    token_response = response.json()
    print("Full token response from X:", token_response, file=sys.stderr)

    access_token = token_response["access_token"]
    
    if "refresh_token" in token_response:
        print("Refresh token rotated – update Railway with new:", token_response["refresh_token"], file=sys.stderr)
    
    print("Access token refreshed successfully", file=sys.stderr)
except requests.exceptions.HTTPError as e:
    print(f"Refresh HTTP error: {e}", file=sys.stderr)
    print(f"Status code: {response.status_code}", file=sys.stderr)
    print(f"Full response: {response.text}", file=sys.stderr)
    if response.status_code == 400:
        print("400 'invalid_request' – likely: invalid/expired refresh_token, wrong client_id, or missing client_secret. Regenerate token in Postman.", file=sys.stderr)
    sys.exit(1)
except Exception as e:
    print(f"Unexpected refresh error: {e}", file=sys.stderr)
    sys.exit(1)

# Create Tweepy Client with refreshed access token
client = tweepy.Client(
    bearer_token=access_token,
    wait_on_rate_limit=True
)

# Verify auth + ONE-TIME TEST POST
try:
    me = client.get_me().data
    print(f"Connected as @{me.username} with OAuth 2.0 user context", file=sys.stderr)

    # ONE-TIME TEST POST TO CONFIRM WRITE ACCESS
    print("Running one-time write test...", file=sys.stderr)
    try:
        test_response = client.create_tweet(
            text="Test write from SlapchampAI – please ignore this #debug"
        )
        print(f"TEST POST SUCCESS – Tweet ID: {test_response.data['id']}", file=sys.stderr)
    except tweepy.TweepyException as te:
        print(f"TEST POST FAILED: {te}", file=sys.stderr)
        if hasattr(te, 'response') and te.response:
            print(f"Status code: {te.response.status_code}", file=sys.stderr)
            print(f"Full response: {te.response.text}", file=sys.stderr)
except Exception as e:
    print(f"Auth or test failed: {e}", file=sys.stderr)
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
# Main polling loop – activates on ANY mention containing "slap"
# ────────────────────────────────────────────────
print("Polling started – listening for any @slapchampai mention containing 'slap'", file=sys.stderr)
since_id = 1  # Updated from mentions

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
                if tweet.author_id == me.id:
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
