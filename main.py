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
    # Add more GIFs here if you want
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
    except:
        pass  # silent fail

cooldowns = load_cooldowns()

# ────────────────────────────────────────────────
# X OAuth 2.0 User Context Setup with Refresh
# ────────────────────────────────────────────────
# (Grok thinking: To bypass the persistent InsecureTransportError, I'm adding a temporary environment variable override. This is a debug hack from requests-oauthlib docs – it allows non-https for local testing. Remove it once stable. Also switched redirect_uri to Postman's secure one for good measure. Added full token response print for debug.)
os.environ["OAUTHLIB_INSECURE_TRANSPORT"] = "1"  # Debug: Bypass HTTPS enforcement for local/refresh flow (remove in production)

client_id = os.getenv("TWITTER_CLIENT_ID")
refresh_token = os.getenv("TWITTER_REFRESH_TOKEN")

print(f"Loaded TWITTER_CLIENT_ID: {'present' if client_id else 'MISSING'}", file=sys.stderr)
print(f"Loaded TWITTER_REFRESH_TOKEN: {'present' if refresh_token else 'MISSING'}", file=sys.stderr)

if not client_id or not refresh_token:
    print("Missing TWITTER_CLIENT_ID or TWITTER_REFRESH_TOKEN in environment variables", file=sys.stderr)
    sys.exit(1)

oauth2_handler = tweepy.OAuth2UserHandler(
    client_id=client_id,
    redirect_uri="https://oauth.pstmn.io/v1/browser-callback",  # Use Postman's secure callback to avoid scheme issues
    scope=["tweet.read", "tweet.write", "users.read", "offline.access"]
)

try:
    print("Attempting to refresh access token...", file=sys.stderr)
    token_response = oauth2_handler.refresh_token(refresh_token)
    print("Token response: " + str(token_response), file=sys.stderr)  # Debug: Full response to see if refresh worked

    access_token = token_response["access_token"]
    
    # If X rotated the refresh token, save the new one (note: in production, persist this somewhere secure)
    if "refresh_token" in token_response:
        refresh_token = token_response["refresh_token"]
        print("Refresh token was rotated and updated", file=sys.stderr)
    
    print("Access token refreshed successfully", file=sys.stderr)
except tweepy.TweepyException as e:
    print(f"Refresh token failed: {e}", file=sys.stderr)
    if hasattr(e, 'response') and e.response:
        print(f"Status code: {e.response.status_code}", file=sys.stderr)
        print(f"Full response: {e.response.text}", file=sys.stderr)
    sys.exit(1)
except Exception as e:
    print(f"Unexpected error during refresh: {e}", file=sys.stderr)
    sys.exit(1)

# Create Tweepy Client with refreshed OAuth 2.0 user access token
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
# Main polling loop – now activates on ANY mention with "slap"
# ────────────────────────────────────────────────
print("Polling started – listening for any @slapchampai mention containing 'slap'", file=sys.stderr)
since_id = 1  # Will be updated from mentions

while True:
    try:
        # Search for recent tweets that mention the bot and contain "slap"
        tweets = client.search_recent_tweets(
            query=f"@{BOT_USERNAME} slap -is:retweet lang:en",
            max_results=10,  # increased slightly to catch more
            since_id=since_id,
            tweet_fields=["author_id", "entities", "id", "created_at"],
            expansions=["author_id"],
            user_fields=["username", "description"]
        )

        if tweets.data:
            # Update since_id to the newest tweet we've seen
            since_id = max(t.id for t in tweets.data)

            for tweet in tweets.data:
                # Skip our own tweets
                if tweet.author_id == me.id:
                    continue

                text = tweet.text.lower()

                # Trigger condition: mention contains "slap" (anywhere in the tweet)
                if "slap" not in text:
                    continue

                # Find the first mentioned user after the bot (potential target)
                mentions = tweet.entities.get("mentions", [])
                target_username = None
                for mention in mentions:
                    if mention["username"].lower() != BOT_USERNAME.lower():
                        target_username = mention["username"]
                        break

                if not target_username:
                    # No target mentioned → skip
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

                # Get target bio
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
