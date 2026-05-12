from app.services.microsoft.microsoft_sync import sync_onedrive_to_documents
from app.db.session import SessionLocal


class FakeGraphClient:
    def __init__(self, access_token: str):
        self.access_token = access_token

    def list_drive_items(self):
        return [
            {
                "id": "file_1",
                "name": "Quarterly Report.txt",
                "file": {"mimeType": "text/plain"},
            },
            {
                "id": "folder_1",
                "name": "Folder",
            },
        ]

    def download_file_content(self, drive_id: str, item_id: str) -> bytes:
        assert item_id == "file_1"
        return b"Revenue grew by 12 percent."


def test_sync_onedrive_to_documents_imports_files(monkeypatch):
    from app.services.microsoft import microsoft_sync as sync_module

    monkeypatch.setattr(sync_module, "MicrosoftGraphClient", FakeGraphClient)

    db = SessionLocal()
    try:
        docs = sync_onedrive_to_documents(
            db=db,
            organization_id=1,
            user_id=1,
            access_token="fake_token",
        )

        assert len(docs) == 1
        assert docs[0]["filename"] == "Quarterly Report.txt"
        assert docs[0]["size"] > 0
    finally:
        db.close()
