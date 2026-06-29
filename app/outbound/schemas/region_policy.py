from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict


class RegionPolicyCreate(BaseModel):
    organization_id: int
    country_code: str
    region_name: str
    allowed: bool = False
    legal_basis_text: str
    footer_template_id: Optional[str] = None
    notes: Optional[str] = None


class RegionPolicyUpdate(BaseModel):
    region_name: Optional[str] = None
    allowed: Optional[bool] = None
    legal_basis_text: Optional[str] = None
    footer_template_id: Optional[str] = None
    notes: Optional[str] = None


class RegionPolicyRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    organization_id: int
    country_code: str
    region_name: str
    allowed: bool
    legal_basis_text: str
    footer_template_id: Optional[str] = None
    notes: Optional[str] = None
    created_at: datetime
    updated_at: datetime
