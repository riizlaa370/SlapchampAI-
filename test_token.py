# test_token.py

# This script is designed to diagnose the Twitter OAuth 2.0 token refresh issue.

import requests

# Replace with your actual credentials
CLIENT_ID = 'your_client_id'
CLIENT_SECRET = 'your_client_secret'

# Function to refresh the OAuth token

def refresh_token():
    url = 'https://api.twitter.com/oauth2/token'
    headers = {
        'Authorization': f'Basic {CLIENT_ID}:{CLIENT_SECRET}',
        'Content-Type': 'application/x-www-form-urlencoded;charset=UTF-8',
    }
    data = {'grant_type': 'client_credentials'}

    response = requests.post(url, headers=headers, data=data)
    if response.status_code == 200:
        return response.json()
    else:
        return response.text

# Test the function
if __name__ == '__main__':
    token_info = refresh_token()
    print(token_info)