import os
import pytest

def test_openai_key_present():
    if not os.getenv("OPENAI_API_KEY"):
        pytest.skip("OPENAI_API_KEY not set (local only)")
