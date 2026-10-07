from datetime import datetime

from pydantic import BaseModel, ConfigDict, model_validator
from typing import Optional


class EvidenceCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str
    description: Optional[str] = None
    # file_reference: free text describing WHERE the evidence is kept (e.g. "Policy v1.2 in the
    # customer's own document system") — never an uploaded file or document content (Batch O4:
    # metadata only, no file storage, no file upload).
    file_reference: Optional[str] = None
    ai_system_id: Optional[int] = None
    ai_risk_id: Optional[int] = None

    @model_validator(mode="after")
    def _at_least_one_link(self):
        if self.ai_system_id is None and self.ai_risk_id is None:
            raise ValueError("ai_system_id or ai_risk_id is required")
        return self


class EvidenceUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: Optional[str] = None
    description: Optional[str] = None
    file_reference: Optional[str] = None


class EvidenceResponse(BaseModel):
    id: int
    title: str
    description: Optional[str]
    file_reference: Optional[str]
    created_at: datetime
    ai_system_id: Optional[int]
    ai_risk_id: Optional[int]

    model_config = {"from_attributes": True}