import os

def test_openai_key_present():
    assert os.getenv("OPENAI_API_KEY"), "OPENAI_API_KEY is not set"
