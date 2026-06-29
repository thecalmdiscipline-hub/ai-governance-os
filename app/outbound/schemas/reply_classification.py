from __future__ import annotations

from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict

ReplyLabel = Literal[
    "A_rejection",
    "B_interested",
    "C_ready",
    "needs_review",
    "ooo",
    "forwarded",
    "question",
    "referral",
    "hostile",
    "unsubscribe",
]

ClassifiedBy = Literal["llm", "human"]


class ReplyClassificationCreate(BaseModel):
    organization_id: int
    reply_id: str
    label: ReplyLabel
    confidence: float
    reasoning: str
    classified_by: ClassifiedBy = "llm"
    model: Optional[str] = None
    tokens_used: Optional[int] = None
    reviewed_by_user_id: Optional[int] = None
    reviewed_at: Optional[datetime] = None


class ReplyClassificationUpdate(BaseModel):
    label: Optional[ReplyLabel] = None
    confidence: Optional[float] = None
    reasoning: Optional[str] = None
    classified_by: Optional[ClassifiedBy] = None
    model: Optional[str] = None
    tokens_used: Optional[int] = None
    reviewed_by_user_id: Optional[int] = None
    reviewed_at: Optional[datetime] = None


class ReplyClassificationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    organization_id: int
    reply_id: str
    label: str
    confidence: float
    reasoning: str
    classified_by: str
    model: Optional[str] = None
    tokens_used: Optional[int] = None
    reviewed_by_user_id: Optional[int] = None
    reviewed_at: Optional[datetime] = None
    created_at: datetime
