"""Test cases for the __main__ module."""

from soneda.twitter.client import TwitterAPIClient

def test_tweets_lookup() -> None:
    twitter = TwitterAPIClient()
    tweet = twitter.get("/2/tweets", ids=1460323737035677698)
    assert tweet[0]["id"] == "1460323737035677698"