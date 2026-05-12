from pathlib import Path
from typing import Optional

from pypdf import PdfReader
from docx import Document as DocxDocument

BASE_DIR = Path("uploaded_documents")


def get_document_path(organization_id: int, stored_name: str) -> Path:
    return BASE_DIR / f"org_{organization_id}" / stored_name


def read_text_file(file_path: Path) -> Optional[str]:
    try:
        return file_path.read_text(encoding="utf-8")
    except:
        try:
            return file_path.read_text(encoding="latin-1")
        except:
            return None


def read_pdf(file_path: Path) -> Optional[str]:
    try:
        reader = PdfReader(str(file_path))
        text = ""
        for page in reader.pages:
            text += page.extract_text() or ""
        return text.strip() or None
    except:
        return None


def read_docx(file_path: Path) -> Optional[str]:
    try:
        doc = DocxDocument(str(file_path))
        return "\n".join([p.text for p in doc.paragraphs]).strip() or None
    except:
        return None


def read_text_document(organization_id: int, stored_name: str) -> Optional[str]:
    file_path = get_document_path(organization_id, stored_name)

    if not file_path.exists() or not file_path.is_file():
        return None

    suffix = file_path.suffix.lower()

    # TEXT FILES
    if suffix in {".txt", ".md", ".csv", ".json"}:
        return read_text_file(file_path)

    # PDF
    if suffix == ".pdf":
        return read_pdf(file_path)

    # WORD
    if suffix == ".docx":
        return read_docx(file_path)

    return None
