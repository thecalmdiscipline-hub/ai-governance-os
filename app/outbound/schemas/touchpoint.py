from __future__ import annotations

from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict

TouchpointChannel = Literal["email"]
TouchpointStatus = Literal["scheduled", "sent", "delivered", "bounced", "failed"]


class TouchpointCreate(BaseModel):
    organization_id: int
    campaign_id: str
    prospect_id: str
    sequence_step: int = 1
    channel: TouchpointChannel = "email"
    subject: str
    body_text: str
    body_html: Optional[str] = None
    scheduled_at: datetime
    sent_at: Optional[datetime] = None
    esp_message_id: Optional[str] = None
    status: TouchpointStatus = "scheduled"
    error_message: Optional[str] = None


class TouchpointUpdate(BaseModel):
    sequence_step: Optional[int] = None
    channel: Optional[TouchpointChannel] = None
    subject: Optional[str] = None
    body_text: Optional[str] = None
    body_html: Optional[str] = None
    scheduled_at: Optional[datetime] = None
    sent_at: Optional[datetime] = None
    esp_message_id: Optional[str] = None
    status: Optional[TouchpointStatus] = None
    error_message: Optional[str] = None


class TouchpointRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    organization_id: int
    campaign_id: str
    prospect_id: str
    sequence_step: int
    channel: str
    subject: str
    body_text: str
    body_html: Optional[str] = None
    scheduled_at: datetime
    sent_at: Optional[datetime] = None
    esp_message_id: Optional[str] = None
    status: str
    error_message: Optional[str] = None
    created_at: datetime
