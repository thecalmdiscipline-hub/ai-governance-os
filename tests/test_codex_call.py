import os
import pytest

@pytest.mark.codex
def test_codex_smoke():
    require = os.getenv("REQUIRE_CODEX") == "1"
    api_key = os.getenv("OPENAI_API_KEY")

    if not api_key:
        if require:
            pytest.fail("OPENAI_API_KEY is not set")
        pytest.skip("OPENAI_API_KEY not set")

    from openai import OpenAI
    from openai import AuthenticationError

    client = OpenAI()

    try:
        resp = client.chat.completions.create(
            model="gpt-4.1",
            messages=[{"role": "user", "content": "Geef 1 korte FastAPI JWT protected endpoint."}],
            max_tokens=200,
        )
    except AuthenticationError as e:
        if require:
            raise
        pytest.skip(f"OPENAI_API_KEY invalid or not authorized: {e}")

    assert resp.choices[0].message.content
