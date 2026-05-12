from typing import Dict, Any, List
import httpx

from app.core.microsoft_config import MICROSOFT_GRAPH_BASE_URL


class MicrosoftGraphClient:
    def __init__(self, access_token: str):
        self.access_token = access_token

    def _headers(self) -> Dict[str, str]:
        return {
            "Authorization": f"Bearer {self.access_token}",
        }

    def list_drive_items(self) -> List[Dict[str, Any]]:
        url = f"{MICROSOFT_GRAPH_BASE_URL}/me/drive/root/children"
        response = httpx.get(url, headers=self._headers(), timeout=30.0)
        response.raise_for_status()
        data = response.json()
        return data.get("value", [])

    def download_file_content(self, drive_id: str, item_id: str) -> bytes:
        url = f"{MICROSOFT_GRAPH_BASE_URL}/drives/{drive_id}/items/{item_id}/content"
        response = httpx.get(url, headers=self._headers(), timeout=60.0)
        response.raise_for_status()
        return response.content

    def get_me(self) -> Dict[str, Any]:
        url = f"{MICROSOFT_GRAPH_BASE_URL}/me"
        response = httpx.get(url, headers=self._headers(), timeout=30.0)
        response.raise_for_status()
        return response.json()
