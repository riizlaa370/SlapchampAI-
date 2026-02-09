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
REFRESH_INTERVAL = 3600       # Refresh access_token every 60 min (before expiry)
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
# Global Tweepy client (refreshed in background)
# ────────────────────────────────────────────────
client = None

# ────────────────────────────────────────────────
# Manual Refresh Function
# ────────────────────────────────────────────────
def refresh_access_token():
    global client

    client_id = os.getenv("TWITTER_CLIENT_ID")
    refresh_token = os.getenv("TWITTER_REFRESH_TOKEN")
    client_secret = os.getenv("TWITTER_CLIENT_SECRET")

    print(f"Loaded TWITTER_CLIENT_ID: {'present' if client_id else 'MISSING'}", file=sys.stderr)
    print(f"Loaded TWITTER_REFRESH_TOKEN: {'present' if refresh_token else 'MISSING'}", file=sys.stderr)
    print(f"Loaded TWITTER_CLIENT_SECRET: {'present' if client_secret else 'MISSING (required!)'}", file=sys.stderr)

    if not client_id or not refresh_token:
        print("Missing TWITTER_CLIENT_ID or TWITTER_REFRESH_TOKEN", file=sys.stderr)
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
        print("Using Basic Auth with client_secret", file=sys.stderr)

    for attempt in range(3):
        try:
            print(f"Refreshing access token (attempt {attempt + 1}/3)...", file=sys.stderr)
            response = requests.post(refresh_url, data=data, headers=headers, auth=auth)
            response.raise_for_status()
            token_response = response.json()
            print("Token response:", token_response, file=sys.stderr)

            access_token = token_response["access_token"]

            # Handle rotation
            if "refresh_token" in token_response:
                new_refresh = token_response["refresh_token"]
                print(f"!!! REFRESH TOKEN ROTATED !!! New: {new_refresh}", file=sys.stderr)
                print("UPDATE RAILWAY WITH NEW TWITTER_REFRESH_TOKEN AND REDEPLOY!", file=sys.stderr)

            # Update global client
            client = tweepy.Client(
                bearer_token=access_token,
                wait_on_rate_limit=True
            )
            print("Refresh successful - client updated", file=sys.stderr)
            return True

        except Exception as e:
            print(f"Refresh failed (attempt {attempt + 1}): {e}", file=sys.stderr)
            if 'response' in locals():
                print(f"Status: {response.status_code} | Body: {response.text}", file=sys.stderr)
            if attempt < 2:
                time.sleep(10)  # delay before retry
            else:
                return False

    return False

# ────────────────────────────────────────────────
# Background Refresh Thread
# ────────────────────────────────────────────────
def background_refresh():
    while True:
        time.sleep(REFRESH_INTERVAL)
        if not refresh_access_token():
            print("Background refresh failed - retrying next cycle", file=sys.stderr
