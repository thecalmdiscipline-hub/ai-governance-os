from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict


class ReplyCreate(BaseModel):
    organization_id: int
    touchpoint_id: Optional[str] = None
    prospect_id: Optional[str] = None
    from_email: str
    subject: Optional[str] = None
    body_text: str
    body_html: Optional[str] = None
    received_at: datetime
    raw_headers: Optional[str] = None
    esp_inbound_id: Optional[str] = None
    processed_at: Optional[datetime] = None


class ReplyUpdate(BaseModel):
    touchpoint_id: Optional[str] = None
    prospect_id: Optional[str] = None
    subject: Optional[str] = None
    body_text: Optional[str] = None
    body_html: Optional[str] = None
    raw_headers: Optional[str] = None
    esp_inbound_id: Optional[str] = None
    processed_at: Optional[datetime] = None


class ReplyRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    organization_id: int
    touchpoint_id: Optional[str] = None
    prospect_id: Optional[str] = None
    from_email: str
    subject: Optional[str] = None
    body_text: str
    body_html: Optional[str] = None
    received_at: datetime
    raw_headers: Optional[str] = None
    esp_inbound_id: Optional[str] = None
    processed_at: Optional[datetime] = None
    created_at: datetime
