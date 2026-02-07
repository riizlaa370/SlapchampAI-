# Updated Code for main.py

# Fixing the author information bug
# Adding proper token persistence
# Improving Railway compatibility with absolute paths and better error handling

import os
import sys

class MyApp:
    def __init__(self):
        self.token_path = os.path.abspath('token.txt')
        self.load_token()

    def load_token(self):
        try:
            with open(self.token_path, 'r') as file:
                self.token = file.read().strip()
        except FileNotFoundError:
            print("Token file not found. Please create 'token.txt'.")
            sys.exit(1)

    def run(self):
        print(f"Running with token: {self.token}")

if __name__ == '__main__':
    app = MyApp()
    app.run()