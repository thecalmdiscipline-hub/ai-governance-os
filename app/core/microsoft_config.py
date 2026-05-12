import os


MICROSOFT_TENANT_ID = os.getenv("MICROSOFT_TENANT_ID", "")
MICROSOFT_CLIENT_ID = os.getenv("MICROSOFT_CLIENT_ID", "")
MICROSOFT_CLIENT_SECRET = os.getenv("MICROSOFT_CLIENT_SECRET", "")
MICROSOFT_REDIRECT_URI = os.getenv("MICROSOFT_REDIRECT_URI", "http://127.0.0.1:8001/microsoft/callback")

MICROSOFT_AUTHORITY = (
    f"https://login.microsoftonline.com/{MICROSOFT_TENANT_ID}"
    if MICROSOFT_TENANT_ID
    else "https://login.microsoftonline.com/common"
)

MICROSOFT_SCOPES = [
    "offline_access",
    "Files.Read",
    "User.Read",
]

MICROSOFT_GRAPH_BASE_URL = "https://graph.microsoft.com/v1.0"
