from typing import List, Dict, Any
from sqlalchemy.orm import Session

from app.integrations.microsoft.graph_client import MicrosoftGraphClient
from app.services.document_storage import save_uploaded_document


def sync_onedrive_to_documents(
    db: Session,
    organization_id: int,
    user_id: int,
    access_token: str,
) -> List[Dict[str, Any]]:

    graph = MicrosoftGraphClient(access_token)

    items = graph.list_drive_items()

    saved_documents = []

    for item in items:
        if not item.get("file"):
            continue

        item_id = item.get("id")
        name = item.get("name")

        try:
            content = graph.download_file_content(
                drive_id="me",
                item_id=item_id,
            )

            saved = save_uploaded_document(
                db=db,
                organization_id=organization_id,
                uploaded_by_user_id=user_id,
                filename=name,
                content=content,
                content_type="application/octet-stream",
            )

            saved_documents.append(saved)

        except Exception:
            continue

    return saved_documents
