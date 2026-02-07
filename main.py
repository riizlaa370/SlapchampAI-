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
from urllib.parse import urlencode

# ────────────────────────────────────────────────
# CONFIG
# ────────────────────────────────────────────────
BOT_USERNAME = "slapchampai"
COOLDOWN_SECONDS = 300
COOLDOWN_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "cooldowns.json")
POLL_INTERVAL = 180
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
        except Exception as e:
            print(f"Error loading cooldowns: {e}", file=sys.stderr)
            return {}
    return {}

def save_cooldowns(cooldowns):
    try:
        with open(COOLDOWN_FILE, "w") as f:
            json.dump(cooldowns, f, indent=2)
    except Exception as e:
        print(f"Failed to save cooldowns: {e}", file=sys.stderr)

cooldowns = load_cooldowns()

# ────────────────────────────────────────────────
# X OAuth 2.0 User Context Setup - FIXED VERSION
# ────────────────────────────────────────────────
client_id = os.getenv("TWITTER_CLIENT_ID")
refresh_token = os.getenv("TWITTER_REFRESH_TOKEN")
client_secret = os.getenv("TWITTER_CLIENT_SECRET")

print(f"[DEBUG] Loaded TWITTER_CLIENT_ID: {'present' if client_id else 'MISSING'}", file=sys.stderr)
print(f"[DEBUG] Loaded TWITTER_REFRESH_TOKEN: {'present' if refresh_token else 'MISSING'}", file=sys.stderr)
print(f"[DEBUG] Loaded TWITTER_CLIENT_SECRET: {'present' if client_secret else 'MISSING'}", file=sys.stderr)

if not client_id or not refresh_token or not client_secret:
    print("[ERROR] Missing required environment variables:", file=sys.stderr)
    print(f"  - TWITTER_CLIENT_ID: {bool(client_id)}", file=sys.stderr)
    print(f"  - TWITTER_REFRESH_TOKEN: {bool(refresh_token)}", file=sys.stderr)
    print(f"  - TWITTER_CLIENT_SECRET: {bool(client_secret)}", file=sys.stderr)
    sys.exit(1)

# ────────────────────────────────────────────────
# FIX: Proper OAuth 2.0 Token Refresh with Form Data
# ────────────────────────────────────────────────
refresh_url = "https://api.twitter.com/2/oauth2/token"

# Create proper form-urlencoded body
token_data = {
    "grant_type": "refresh_token",
    "refresh_token": refresh_token,
    "client_id": client_id,
}

# Create Basic Auth header
auth_str = f"{client_id}:{client_secret}"
auth_b64 = base64.b64encode(auth_str.encode()).decode()

headers = {
    "Authorization": f"Basic {auth_b64}",
    "Content-Type": "application/x-www-form-urlencoded",
}

print("[DEBUG] Attempting OAuth 2.0 token refresh...", file=sys.stderr)
print(f"[DEBUG] Using refresh URL: {refresh_url}", file=sys.stderr)

access_token = None
try:
    # IMPORTANT: Use data parameter with urlencode, not json parameter
    response = requests.post(
        refresh_url,
        data=urlencode(token_data),
        headers=headers,
        timeout=10
    )
    
    print(f"[DEBUG] Response status: {response.status_code}", file=sys.stderr)
    print(f"[DEBUG] Response body: {response.text}", file=sys.stderr)
    
    response.raise_for_status()
    token_response = response.json()
    
    access_token = token_response.get("access_token")
    if not access_token:
        print(f"[ERROR] No access_token in response: {token_response}", file=sys.stderr)
        sys.exit(1)
    
    print("[SUCCESS] Access token refreshed successfully!", file=sys.stderr)
    
except requests.exceptions.HTTPError as e:
    print(f"[ERROR] HTTP Error: {e.response.status_code}", file=sys.stderr)
    print(f"[ERROR] Response text: {e.response.text}", file=sys.stderr)
    
    if e.response.status_code == 400:
        print("[ERROR] 400 Bad Request - This usually means:", file=sys.stderr)
        print("  1. Invalid/expired refresh token", file=sys.stderr)
        print("  2. Wrong client credentials", file=sys.stderr)
        print("  3. Mismatched client_id/client_secret", file=sys.stderr)
        print("[FIX] Regenerate your tokens in Twitter Developer Portal", file=sys.stderr)
    
    sys.exit(1)
except requests.exceptions.Timeout:
    print("[ERROR] Request timeout - Twitter API not responding", file=sys.stderr)
    sys.exit(1)
except Exception as e:
    print(f"[ERROR] Unexpected error: {e}", file=sys.stderr)
    import traceback
    traceback.print_exc(file=sys.stderr)
    sys.exit(1)

# Create Tweepy Client with refreshed access token
print("[DEBUG] Creating Tweepy client...", file=sys.stderr)
client = tweepy.Client(
    bearer_token=access_token,
    wait_on_rate_limit=True
)

# Verify auth
me = None
try:
    me = client.get_me().data
    print(f"[SUCCESS] Connected as @{me.username} ✅", file=sys.stderr)
except Exception as e:
    print(f"[ERROR] Failed to verify auth: {e}", file=sys.stderr)
    sys.exit(1)

# ────────────────────────────────────────────────
# Grok roast generator
# ────────────────────────────────────────────────
def generate_nuclear_roast(target_username, attacker_username, bio_snippet=""):
    if not grok_client.api_key:
        return f"@{target_username} got slapped! 🔥"

    try:
        prompt = f"""Brutal savage roast for @{target_username}.
Bio: "{bio_snippet}"
Max 50 words. Nuclear mean, personal, hilarious.
End with 🔥"""

        response = grok_client.chat.completions.create(
            model="grok-beta",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=70,
            temperature=0.9,
        )

        roast = response.choices[0].message.content.strip()
        return roast[:190]
    except Exception as e:
        print(f"[ERROR] Grok API error: {e}", file=sys.stderr)
        return f"@{target_username} your vibe is landfill. Roasted. 🔥"

# ────────────────────────────────────────────────
# Main polling loop
# ────────────────────────────────────────────────
print("[INFO] Polling started – listening for mentions containing 'slap'", file=sys.stderr)
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
            print(f"[DEBUG] Found {len(tweets.data)} new tweets", file=sys.stderr)

            for tweet in tweets.data:
                if tweet.author_id == me.id:
                    continue

                text = tweet.text.lower()
                if "slap" not in text:
                    continue

                mentions = tweet.entities.get("mentions", []) if tweet.entities else []
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
                        print(f"[DEBUG] Cooldown active for {key}", file=sys.stderr)
                        continue

                cooldowns[key] = now.isoformat()
                save_cooldowns(cooldowns)

                try:
                    target_user = client.get_user(username=target_username, user_fields=["description"]).data
                    bio_snippet = target_user.description[:60] if target_user and target_user.description else ""
                except Exception as e:
                    print(f"[WARN] Failed to fetch user {target_username}: {e}", file=sys.stderr)
                    bio_snippet = ""

                author_username = tweet.author.username if hasattr(tweet, 'author') and tweet.author else "someone"

                roast = generate_nuclear_roast(target_username, author_username, bio_snippet)

                gif = random.choice(SLAP_GIFS) if random.random() < GIF_PROBABILITY else ""

                reply_text = f"@{target_username} {roast}"
                if gif:
                    reply_text += f"\n\n{gif}"
                reply_text += f"\n— @{{author_username}} 🔥"
                reply_text = reply_text[:270]

                try:
                    resp = client.create_tweet(
                        text=reply_text,
                        in_reply_to_tweet_id=tweet.id
                    )
                    print(f"[SUCCESS] Slapped @{target_username} - Tweet ID: {{resp.data['id']}}", file=sys.stderr)
                except tweepy.TweepyException as e:
                    print(f"[ERROR] Reply failed: {e}", file=sys.stderr)

        else:
            print("[DEBUG] No new mentions found", file=sys.stderr)

        time.sleep(POLL_INTERVAL)

    except tweepy.TooManyRequests:
        print("[WARN] Rate limit hit - sleeping 15 minutes", file=sys.stderr)
        time.sleep(900)
    except Exception as e:
        print(f"[ERROR] Loop error: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc(file=sys.stderr)
        time.sleep(180)