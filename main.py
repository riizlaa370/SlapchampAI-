import requests

# OAuth 2.0 token refresh function

def refresh_access_token(token):
    try:
        response = requests.post('https://example.com/oauth2/token', data={
            'grant_type': 'refresh_token',
            'refresh_token': token
        })

        response.raise_for_status()  # Raise an error for bad responses
        return response.json()['access_token']
    except requests.exceptions.HTTPError as e:
        print(f"HTTP error occurred: {e}")
    except requests.exceptions.ConnectionError:
        print("Connection error occurred. Please check your network.")
    except Exception as e:
        print(f"An error occurred: {e}")
    return None

# Example usage
if __name__ == '__main__':
    token = 'your_refresh_token_here'
    new_access_token = refresh_access_token(token)
    if new_access_token:
        print(f'New access token: {new_access_token}')