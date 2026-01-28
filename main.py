import os
import sys
import tweepy
import random
import time
import json
from datetime import datetime, timezone, timedelta

# ────────────────────────────────────────────────
#  Debug: Show environment variables + Tweepy version
# ────────────────────────────────────────────────
print("Tweepy version:", tweepy.__version__, file=sys.stderr)
print("=== ENV DEBUG START ===", file=sys.stderr)

keys_we_care_about = [
    "TWITTER_API_KEY", "TWITTER_API_SECRET",
    "TWITTER_ACCESS_TOKEN", "TWITTER_ACCESS_TOKEN_SECRET",
    "TWITTER_BEARER_TOKEN", "GROK_API_KEY"
]

for key in keys_we_care_about:
    value = os.getenv(key)
    if value:
        print(f"{key}: present (starts with {value[:6]}...)", file=sys.stderr)
    else:
        print(f"{key}: MISSING / None", file=sys.stderr)

print("\nFull TWITTER* & GROK* vars:", file=sys.stderr)
for k, v in sorted(os.environ.items()):
    if k.upper().startswith("TWITTER") or k.upper().startswith("GROK") or "OAUTH" in k.upper():
        print(f"  {k} = {v[:10]}...", file=sys.stderr)

print("=== ENV DEBUG END ===", file=sys.stderr)

# ────────────────────────────────────────────────
#  CONFIG
# ────────────────────────────────────────────────
BOT_USERNAME = "slapchampai"
COOLDOWN_SECONDS = 300
COOLDOWN_FILE = "cooldowns.json"

SLAP_GIFS = [
    "https://tenor.com/view/slap-hard-slap-gif-22345678",
    # ... add your full list here
]

# ────────────────────────────────────────────────
#  Cooldown helpers
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
            json.dump(cooldowns, f, indent=2)
    except Exception as e:
        print(f"Failed to save cooldowns: {e}", file=sys.stderr)

cooldowns = load_cooldowns()

# ────────────────────────────────────────────────
# Twitter/X Client – OAuth 1.0a USER CONTEXT
# ────────────────────────────────────────────────
consumer_key        = os.getenv("TWITTER_API_KEY") or os.getenv("TWITTER_CONSUMER_KEY")
consumer_secret     = os.getenv("TWITTER_API_SECRET") or os.getenv("TWITTER_CONSUMER_SECRET")
access_token        = os.getenv("TWITTER_ACCESS_TOKEN")
access_token_secret = os.getenv("TWITTER_ACCESS_TOKEN_SECRET")

print("\n=== CREDENTIALS ACTUALLY USED ===", file=sys.stderr)
print(f"consumer_key       : {'NOT_SET' if not consumer_key else consumer_key[:8] + '...'}", file=sys.stderr)
print(f"consumer_secret    : {'NOT_SET' if not consumer_secret else 'present (' + str(len(consumer_secret)) + ' chars)'}", file=sys.stderr)
print(f"access_token       : {'NOT_SET' if not access_token else access_token[:8] + '...'}", file=sys.stderr)
print(f"access_token_secret: {'NOT_SET' if not access_token_secret else 'present (' + str(len(access_token_secret)) + ' chars)'}", file=sys.stderr)
print("===================================\n", file=sys.stderr)

missing = [k for k, v in {
    "consumer_key": consumer_key,
    "consumer_secret": consumer_secret,
    "access_token": access_token,
    "access_token_secret": access_token_secret
}.items() if not v]

if missing:
    print("CRITICAL: Missing Twitter credentials:", ", ".join(missing), file=sys.stderr)
    sys.exit(1)

client = tweepy.Client(
    consumer_key=consumer_key,
    consumer_secret=consumer_secret,
    access_token=access_token,
    access_token_secret=access_token_secret,
    wait_on_rate_limit=True
)

# Verify + quick test (uncomment test after first deploy to confirm write)
try:
    me = client.get_me(user_auth=True).data
    print(f"Connected as @{me.username} — SlapchampAI LIVE 🔥", file=sys.stderr)
    
    # ─── TEMP TEST POST (uncomment once, run, check if posts, then comment out) ───
    # test_response = client.create_tweet(text="Test write from bot — ignore this #debug", user_auth=True)
    # print(f"TEST POST SUCCESS — ID: {test_response.data['id']}", file=sys.stderr)
    
except tweepy.TweepyException as e:
    print(f"Auth / connection failed: {e}", file=sys.stderr)
    if hasattr(e, 'response') and e.response:
        print(f"Status: {e.response.status_code}", file=sys.stderr)
        print(f"Full body: {e.response.text}", file=sys.stderr)
    sys.exit(1)

# ────────────────────────────────────────────────
#  Grok Roast Generator (placeholder — fill your logic)
# ────────────────────────────────────────────────
def generate_nuclear_roast(target_username, attacker_username, bio_snippet="", pfp_desc=""):
    # Replace with your actual roast generation code
    return f"{target_username} just got absolutely roasted! 💥"

# ────────────────────────────────────────────────
#  Main Loop
# ────────────────────────────────────────────────
print("SlapchampAI polling mentions...", file=sys.stderr)

while True:
    try:
        tweets = client.search_recent_tweets(
            query=f"@{BOT_USERNAME} slap -is:retweet lang:en",
            max_results=10,
            tweet_fields=["author_id", "entities", "created_at", "id"],
            expansions=["author_id"],
            user_fields=["username", "description", "profile_image_url"]
        )

        if not tweets.data:
            print("No new slaps — sleep 60s", file=sys.stderr)
            time.sleep(60)
            continue

        for tweet in tweets.data:
            author_id = tweet.author_id
            if author_id == me.id:
                continue

            text = tweet.text.lower()
            if "slap" not in text:
                continue

            mentions = tweet.entities.get("mentions", [])
            if len(mentions) < 2:
                continue

            target_username = mentions[1]["username"]

            now = datetime.now(timezone.utc)
            key = f"{author_id}_{target_username}"
            last = cooldowns.get(key)
            if last:
                last_time = datetime.fromisoformat(last)
                if now - last_time < timedelta(seconds=COOLDOWN_SECONDS):
                    print(f"Cooldown for {target_username}", file=sys.stderr)
                    continue

            cooldowns[key] = now.isoformat()
            save_cooldowns(cooldowns)

            target = client.get_user(username=target_username,
                                     user_fields=["description", "profile_image_url"]).data

            bio_snippet = target.description[:80] if target and target.description else ""
            pfp_desc = "unknown"

            roast = generate_nuclear_roast(
                target_username,
                tweet.author.username if 'users' in (tweets.includes or {}) else "someone",
                bio_snippet,
                pfp_desc
            )

            gif = random.choice(SLAP_GIFS)

            reply_text = (
                f"@{target_username} {roast}\n\n"
                f"{gif}\n"
                f"Slapped by @{tweet.author.username} — Powered by Grok 🔥"
            )

            # ─── POST REPLY ───
            try:
                print(f"Posting reply to {tweet.id} as @{me.username}", file=sys.stderr)
                response = client.create_tweet(
                    text=reply_text,
                    in_reply_to_tweet_id=tweet.id,
                    user_auth=True
                )
                print(f"Success slap @{target_username} — ID: {response.data['id']}", file=sys.stderr)
            except tweepy.TweepyException as te:
                print(f"Reply failed: {te}", file=sys.stderr)
                print(f"Details: {repr(te)}", file=sys.stderr)
                if hasattr(te, 'response') and te.response:
                    print(f"Status: {te.response.status_code}", file=sys.stderr)
                    print(f"Full body: {te.response.text}", file=sys.stderr)
            except Exception as e:
                print(f"Unexpected in reply: {e}", file=sys.stderr)

        time.sleep(60)

    except tweepy.TweepyException as te:
        print(f"Loop Tweepy error: {te}", file=sys.stderr)
        time.sleep(60)
    except Exception as e:
        print(f"Unexpected loop error: {e}", file=sys.stderr)
        time.sleep(60)
