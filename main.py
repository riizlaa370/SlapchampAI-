import os
import time
import requests
from requests.auth import HTTPBasicAuth
from tweepy import Client

# Load configuration from environment variables (set these in your hosting platform!)
API_KEY = os.getenv('TWITTER_API_KEY')
API_SECRET_KEY = os.getenv('TWITTER_API_SECRET_KEY')
BEARER_TOKEN = os.getenv('TWITTER_BEARER_TOKEN')          # optional / fallback
CLIENT_ID = os.getenv('TWITTER_CLIENT_ID')
CLIENT_SECRET = os.getenv('TWITTER_CLIENT_SECRET')
REFRESH_TOKEN = os.getenv('TWITTER_REFRESH_TOKEN')        # persistent refresh token

# Cooldown settings
COOLDOWN_PERIOD = 60  # seconds between roasts/polls

TOKEN_URL = "https://api.twitter.com/2/oauth2/token"


def refresh_access_token():
    """
    Refresh the OAuth 2.0 access token using the refresh token.
    Uses Basic Auth (client_id:client_secret) as required for confidential clients.
    Handles refresh token rotation by printing the new one (update your env var manually for now).
    """
    if not all([CLIENT_ID, CLIENT_SECRET, REFRESH_TOKEN]):
        print("Missing required env vars: TWITTER_CLIENT_ID, TWITTER_CLIENT_SECRET, or TWITTER_REFRESH_TOKEN")
        return None

    payload = {
        'grant_type': 'refresh_token',
        'refresh_token': REFRESH_TOKEN,
        'client_id': CLIENT_ID,
        # 'client_secret': CLIENT_SECRET   # Do NOT send in body — use Basic Auth instead
    }

    auth = HTTPBasicAuth(CLIENT_ID, CLIENT_SECRET)

    try:
        response = requests.post(TOKEN_URL, data=payload, auth=auth)
        response.raise_for_status()  # Raises exception for 4xx/5xx

        tokens = response.json()
        new_access_token = tokens.get('access_token')
        new_refresh_token = tokens.get('refresh_token')  # Often rotated!

        if new_refresh_token and new_refresh_token != REFRESH_TOKEN:
            print("!!! REFRESH TOKEN ROTATED !!!")
            print(f"New refresh_token: {new_refresh_token}")
            print("→ Update your env var TWITTER_REFRESH_TOKEN with this value and redeploy!")
            # TODO: in production → save to persistent storage / update secret via API

        print(f"Successfully refreshed access token: {new_access_token[:10]}...")
        return new_access_token

    except requests.exceptions.HTTPError as e:
        print(f"HTTP error refreshing token: {e}")
        if 'response' in locals():
            print("Response content:", response.text)
        return None
    except Exception as e:
        print(f"Unexpected error during refresh: {e}")
        return None


def setup_tweepy_client(access_token):
    """Create tweepy Client with fresh OAuth 2.0 User Context access token"""
    if not access_token:
        raise ValueError("No access token provided")
    return Client(bearer_token=access_token)  # Works for user context access tokens


def grok_roast_generator():
    """Placeholder — replace with real roast logic (e.g. call Grok API, generate funny roast)"""
    # Example placeholder
    return "Your roast is: You have the perfect face for radio!"


def main_polling_loop():
    while True:
        print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] Starting poll cycle...")

        access_token = refresh_access_token()
        if access_token is None:
            print("Failed to refresh access token. Sleeping longer before retry...")
            time.sleep(COOLDOWN_PERIOD * 3)  # backoff on failure
            continue

        try:
            client = setup_tweepy_client(access_token)
            roast = grok_roast_generator()
            print(roast)

            # TODO: Add your real bot action here, e.g.:
            # client.create_tweet(text=roast)
            # or search mentions → reply with roast, etc.

        except Exception as e:
            print(f"Error during this cycle: {e}")

        print(f"Sleeping for {COOLDOWN_PERIOD} seconds...\n")
        time.sleep(COOLDOWN_PERIOD)


if __name__ == '__main__':
    print("Starting Grok Roast Bot...")
    if not REFRESH_TOKEN:
        print("CRITICAL: No TWITTER_REFRESH_TOKEN set! Bot cannot authenticate.")
    else:
        main_polling_loop()
