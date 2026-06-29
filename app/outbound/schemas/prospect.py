from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict


class OutboundProspectCreate(BaseModel):
    organization_id: int
    company_id: str
    first_name: str
    last_name: str
    email: str
    title: Optional[str] = None
    linkedin_url: Optional[str] = None
    person_rank: int = 1
    sequence_state: str = "pending"
    last_touched_at: Optional[datetime] = None
    enrichment_data: Optional[dict[str, Any]] = None


class OutboundProspectUpdate(BaseModel):
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    email: Optional[str] = None
    title: Optional[str] = None
    linkedin_url: Optional[str] = None
    person_rank: Optional[int] = None
    sequence_state: Optional[str] = None
    last_touched_at: Optional[datetime] = None
    enrichment_data: Optional[dict[str, Any]] = None


class OutboundProspectRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    organization_id: int
    company_id: str
    first_name: str
    last_name: str
    email: str
    title: Optional[str] = None
    linkedin_url: Optional[str] = None
    person_rank: int
    sequence_state: str
    last_touched_at: Optional[datetime] = None
    enrichment_data: Optional[dict[str, Any]] = None
    created_at: datetime
    updated_at: datetime
