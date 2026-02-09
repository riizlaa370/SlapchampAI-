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
# X OAuth 2.0 - Temporary Direct Access Token (for testing)
# ────────────────────────────────────────────────
# Prefer new OAuth 2.0 token from Postman if set
access_token = os.getenv("TWITTER_OAUTH2_ACCESS_TOKEN") or os.getenv("TWITTER_BEARER_TOKEN")

if access_token:
    print("Using NEW OAuth 2.0 Bearer token from Postman for testing", file=sys.stderr)
else:
    print("No new OAuth 2.0 token found - falling back to old auth", file=sys.stderr)
    # Fallback to your old OAuth 1.0a token if you have it
    access_token = os.getenv("TWITTER_ACCESS_TOKEN")
    if not access_token:
        print("Missing ANY access token for testing", file=sys.stderr)
        sys.exit(1)

client = tweepy.Client(
    bearer_token=access_token,
    wait_on_rate_limit=True
)

print("Client initialized with access_token", file=sys.stderr)

# Verify auth + ONE-TIME TEST POST
try:
    me = client.get_me().data
    print(f"Connected as @{me.username} with OAuth 2.0 user context", file=sys.stderr)

    print("Running one-time write test...", file=sys.stderr)
    test_response = client.create_tweet(
        text="Test write from SlapchampAI – please ignore this #debug"
    )
    print(f"TEST POST SUCCESS – Tweet ID: {test_response.data['id']}", file=sys.stderr)
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
