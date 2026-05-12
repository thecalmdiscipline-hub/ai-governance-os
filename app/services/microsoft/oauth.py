from urllib.parse import urlencode
import httpx

from app.core.microsoft_config import (
    MICROSOFT_AUTHORITY,
    MICROSOFT_CLIENT_ID,
    MICROSOFT_CLIENT_SECRET,
    MICROSOFT_REDIRECT_URI,
    MICROSOFT_SCOPES,
)


def build_authorization_url(state: str) -> str:
    query = urlencode(
        {
            "client_id": MICROSOFT_CLIENT_ID,
            "response_type": "code",
            "redirect_uri": MICROSOFT_REDIRECT_URI,
            "response_mode": "query",
            "scope": " ".join(MICROSOFT_SCOPES),
            "state": state,
        }
    )
    return f"{MICROSOFT_AUTHORITY}/oauth2/v2.0/authorize?{query}"


def exchange_code_for_token(code: str) -> dict:
    token_url = f"{MICROSOFT_AUTHORITY}/oauth2/v2.0/token"

    response = httpx.post(
        token_url,
        data={
            "client_id": MICROSOFT_CLIENT_ID,
            "client_secret": MICROSOFT_CLIENT_SECRET,
            "code": code,
            "redirect_uri": MICROSOFT_REDIRECT_URI,
            "grant_type": "authorization_code",
            "scope": " ".join(MICROSOFT_SCOPES),
        },
        timeout=30.0,
    )
    response.raise_for_status()
    return response.json()
