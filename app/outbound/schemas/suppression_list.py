from __future__ import annotations

from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict

SuppressionReason = Literal[
    "unsubscribed", "hard_bounce", "manual", "spam_complaint", "dnc_list"
]


class SuppressionListEntryCreate(BaseModel):
    organization_id: int
    email: str
    reason: SuppressionReason
    source: Optional[str] = None


class SuppressionListEntryRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    organization_id: int
    email: str
    reason: str
    source: Optional[str] = None
    added_at: datetime
