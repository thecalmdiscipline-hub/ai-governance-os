from typing import Dict, Any, List


def normalize_microsoft_item(item: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "item_id": item.get("id"),
        "drive_id": item.get("parentReference", {}).get("driveId"),
        "filename": item.get("name"),
        "web_url": item.get("webUrl"),
        "mime_type": item.get("file", {}).get("mimeType") if item.get("file") else None,
        "last_modified": item.get("lastModifiedDateTime"),
    }


def normalize_microsoft_items(items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return [normalize_microsoft_item(item) for item in items]
