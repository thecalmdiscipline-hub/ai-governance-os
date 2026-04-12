from pathlib import Path
from typing import Optional

BASE_DIR = Path("uploaded_documents")


def get_document_path(organization_id: int, stored_name: str) -> Path:
    return BASE_DIR / f"org_{organization_id}" / stored_name


def read_text_document(organization_id: int, stored_name: str) -> Optional[str]:
    file_path = get_document_path(organization_id, stored_name)

    if not file_path.exists() or not file_path.is_file():
        return None

    suffix = file_path.suffix.lower()
    if suffix not in {".txt", ".md", ".csv", ".json"}:
        return None

    try:
        return file_path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        try:
            return file_path.read_text(encoding="latin-1")
        except Exception:
            return None
