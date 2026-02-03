import os
import sys
import tweepy
import random
import time
import json
from datetime import datetime, timezone, timedelta
from openai import OpenAI

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
    # Add 3–8 more short links if desired
]

# ────────────────────────────────────────────────
# Grok API client (created once)
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
    except:
        pass  # silent fail

cooldowns = load_cooldowns()

# ────────────────────────────────────────────────
# X Client setup
# ────────────────────────────────────────────────
consumer_key = os.getenv("TWITTER_API_KEY") or os.getenv("TWITTER_CONSUMER_KEY")
consumer_secret = os.getenv("TWITTER_API_SECRET") or os.getenv("TWITTER_CONSUMER_SECRET")
access_token = os.getenv("TWITTER_ACCESS_TOKEN")
access_token_secret = os.getenv("TWITTER_ACCESS_TOKEN_SECRET")

if not all([consumer_key, consumer_secret, access_token, access_token_secret]):
    print("Missing Twitter credentials", file=sys.stderr)
    sys.exit(1)

client = tweepy.Client(
    consumer_key=consumer_key,
    consumer_secret=consumer_secret,
    access_token=access_token,
    access_token_secret=access_token_secret,
    wait_on_rate_limit=True
)

# Verify auth + ONE-TIME TEST POST
try:
    me = client.get_me(user_auth=True).data
    print(f"Connected as @{me.username}", file=sys.stderr)

    # ─── ONE-TIME TEST POST TO CONFIRM WRITE ACCESS ───
    # This runs only once per startup/redeploy
    print("Running one-time write test...", file=sys.stderr)
    try:
        test_response = client.create_tweet(
            text="Test write from SlapchampAI – please ignore this #debug",
            user_auth=True
        )
        print(f"TEST POST SUCCESS – Tweet ID: {test_response.data['id']}", file=sys.stderr)
    except tweepy.TweepyException as te:
        print(f"TEST POST FAILED: {te}", file=sys.stderr)
        print(f"Status code: {te.response.status_code if hasattr(te, 'response') and te.response else 'N/A'}", file=sys.stderr)
        if hasattr(te, 'response') and te.response:
            print(f"Full response body: {te.response.text}", file=sys.stderr)
        else:
            print("No detailed response body available", file=sys.stderr)
    except Exception as e:
        print(f"TEST POST UNEXPECTED ERROR: {e}", file=sys.stderr)

except Exception as e:
    print(f"Auth failed: {e}", file=sys.stderr)
    sys.exit(1)

# ────────────────────────────────────────────────
# Real Grok roast generator - low cost
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
            model="grok-beta",           # or grok-3-mini-beta if available & cheaper
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
# Main loop
# ────────────────────────────────────────────────
print("Polling started", file=sys.stderr)
since_id = 1

while True:
    try:
        tweets = client.search_recent_tweets(
            query=f"@{BOT_USERNAME} slap -is:retweet lang:en",
            max_results=5,
            since_id=since_id,
            tweet_fields=["author_id", "entities", "id"],
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
                if len(mentions) < 2:
                    continue

                target_username = mentions[1]["username"]

                now = datetime.now(timezone.utc)
                key = f"{tweet.author_id}_{target_username}"
                if key in cooldowns:
                    last = datetime.fromisoformat(cooldowns[key])
                    if now - last < timedelta(seconds=COOLDOWN_SECONDS):
                        continue

                cooldowns[key] = now.isoformat()
                save_cooldowns(cooldowns)

                target_user = client.get_user(username=target_username, user_fields=["description"]).data
                bio_snippet = target_user.description[:60] if target_user and target_user.description else ""

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
                        in_reply_to_tweet_id=tweet.id,
                        user_auth=True
                    )
                    print(f"Slapped @{target_username}", file=sys.stderr)
                except Exception as e:
                    print(f"Reply failed: {e}", file=sys.stderr)

        time.sleep(POLL_INTERVAL)

    except Exception as e:
        print(f"Loop error: {e}", file=sys.stderr)
        time.sleep(180)
