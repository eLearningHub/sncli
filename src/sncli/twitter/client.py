import os
import re
import dbm
import toml
import json
import base64
import urllib
import hashlib
import oauthlib
import requests
from cryptography.fernet import Fernet
from requests_oauthlib import OAuth2Session
from oauthlib.oauth2 import BackendApplicationClient
from oauthlib.oauth2.rfc6749.errors import MissingTokenError

from sncli.twitter.exceptions import MissingToken

CREDENTIALS_FILE = os.path.expanduser(os.getenv("TWITTER_CREDENTIALS_FILE", "~/.sncli/.twitter"))

class TwitterAPIClient:

    API_ROOT = os.environ.get("TWITTER_API_ROOT", "https://api.twitter.com")
    AUTH_URL = "https://twitter.com/i/oauth2/authorize"
    TOKEN_URL = f"{API_ROOT}/oauth2/token"
    REDIRECT_URI = "http://127.0.0.1:5000/oauth/callback"
    API_ROOT = os.environ.get("TWITTER_API_ROOT", "https://api.twitter.com")
    KEY_DB = os.path.expanduser(os.getenv("TWITTER_KEY_DB", "~/.sncli/.twitter.key"))
    scopes = ["tweet.read", "users.read", "tweet.write", "offline.access"]

    def __init__(self, profile: str = None):

        profiles = toml.load(CREDENTIALS_FILE)
        if profile is None:
          profile = list(profiles.keys())[0]

        credentials = profiles[profile]
        self.consumer_key = credentials['consumer_key']
        self.consumer_secret = credentials['consumer_secret']

        # Create a code verifier
        self.code_verifier = base64.urlsafe_b64encode(os.urandom(30)).decode("utf-8")
        self.code_verifier = re.sub("[^a-zA-Z0-9]+", "", self.code_verifier)

        # Create a code challenge
        code_challenge = hashlib.sha256(self.code_verifier.encode("utf-8")).digest()
        code_challenge = base64.urlsafe_b64encode(code_challenge).decode("utf-8")
        self.code_challenge = code_challenge.replace("=", "")

        print(self.KEY_DB)
        if os.path.exists(self.KEY_DB):
            token = self.load_saved_token()
        else:
            token = self.fetch_api_token()
            self.token_saver(token)
        
        self.client = self.create_client_for_token(token)


    def fernet(self, key: str) -> Fernet:
        key = key + "=" * (len(key) % 4)
        _key = base64.urlsafe_b64encode(base64.urlsafe_b64decode(key))
        return Fernet(_key)

    def encrypt(self, data: str) -> bytes:
        return self.fernet(self.consumer_secret).encrypt(data.encode())

    def decrypt(self, data: bytes) -> bytes:
        return self.fernet(self.consumer_secret).decrypt(data)

    def token_saver(self, token: dict) -> None:
        data = json.dumps(token)
        print(data)
        _t = self.encrypt(data)
        with dbm.open(self.KEY_DB, "c") as db:
            db[self.consumer_key] = _t

    def load_saved_token(self) -> dict:
        try:
          with dbm.open(self.KEY_DB, "c") as db:
              _token = db[self.consumer_key]
          token = json.loads(self.decrypt(_token))
          return token
        except:
          raise(KeyError)

    def fetch_api_token(self) -> dict:
        backend = BackendApplicationClient(client_id=self.consumer_key)
        oauth = OAuth2Session(client=backend)
        try:
            token = oauth.fetch_token(
                token_url=self.TOKEN_URL,
                client_id=self.consumer_key,
                client_secret=self.consumer_secret
            )
        except MissingTokenError:
            # oauthlib gives the same error regardless of the problem
            print("Something went wrong, please check your client credentials.")
            raise
        return token

    def create_client_for_token(self, token: dict) -> OAuth2Session:
        return OAuth2Session(
            self.consumer_key,
            token=token,
            auto_refresh_url=self.REFRESH_URL,
            auto_refresh_kwargs={},
            token_updater=self.token_saver,
        )

    def clear_saved_token(self) -> None:
        with dbm.open(self.KEY_DB.as_posix(), "c") as db:
            if self.consumer_key in db:
                del db[self.consumer_key]

    def reset(self):
        self.clear_saved_token()
        token = self.fetch_api_token()
        self.token_saver(token)
        self.client = self.create_client_for_token(token)

    ### Dispatch methods ###

    def get(self, path:str, **query) -> requests.Response:
        url = f"{self.TWITTER_API_ROOT}{path}"
        if query:
            querystr = urllib.parse.urlencode(query)
            url = f"{url}?{querystr}"
        #logger.debug(f"GETing URL {url}")
        try:
            return self.client.get(url)
        except (oauthlib.oauth2.rfc6749.errors.MissingTokenError, MissingToken):
            self.reset()
            return self.client.get(url)

    def post(self, path:str, data:dict) -> requests.Response:
        url = self.api_url+path
        #logger.debug(f"POSTing URL {url}")
        return self.client.post(url, json=data)

    def put(self, path:str, data:dict) -> requests.Response:
        url = f"{self.TWITTER_API_ROOT}{path}"
        #logger.debug(f"PUTing URL {url}")
        try:
            resp = self.client.put(url, json=data)
            return resp
        except (oauthlib.oauth2.rfc6749.errors.MissingTokenError, MissingToken):
            self.reset()
            resp = self.client.post(url, json=data)
            return resp
