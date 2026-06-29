from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict


class OutboundCampaignCreate(BaseModel):
    organization_id: int
    name: str
    description: Optional[str] = None
    status: str = "draft"
    campaign_type: str = "cold"
    config: Optional[dict[str, Any]] = None
    created_by_user_id: Optional[int] = None


class OutboundCampaignUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    status: Optional[str] = None
    campaign_type: Optional[str] = None
    config: Optional[dict[str, Any]] = None


class OutboundCampaignRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    organization_id: int
    name: str
    description: Optional[str] = None
    status: str
    campaign_type: str
    config: Optional[dict[str, Any]] = None
    created_by_user_id: Optional[int] = None
    created_at: datetime
    updated_at: datetime
