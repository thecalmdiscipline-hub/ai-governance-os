from app.services.microsoft.document_sync import normalize_microsoft_item


def test_normalize_microsoft_item():
    item = {
        "id": "item_123",
        "name": "Quarterly Report.docx",
        "webUrl": "https://example.com/file",
        "lastModifiedDateTime": "2026-04-14T10:00:00Z",
        "parentReference": {
            "driveId": "drive_456"
        },
        "file": {
            "mimeType": "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        }
    }

    result = normalize_microsoft_item(item)

    assert result["item_id"] == "item_123"
    assert result["drive_id"] == "drive_456"
    assert result["filename"] == "Quarterly Report.docx"
    assert result["web_url"] == "https://example.com/file"
    assert result["mime_type"] is not None
