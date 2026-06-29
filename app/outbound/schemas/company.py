from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict


class OutboundCompanyCreate(BaseModel):
    organization_id: int
    name: str
    domain: Optional[str] = None
    industry: Optional[str] = None
    employee_count: Optional[int] = None
    annual_revenue: Optional[Decimal] = None
    country: Optional[str] = None
    region_code: Optional[str] = None
    linkedin_url: Optional[str] = None
    website: Optional[str] = None
    icp_score: Optional[int] = None
    enrichment_source: Optional[str] = None
    enrichment_data: Optional[dict[str, Any]] = None
    status: str = "pending"


class OutboundCompanyUpdate(BaseModel):
    name: Optional[str] = None
    domain: Optional[str] = None
    industry: Optional[str] = None
    employee_count: Optional[int] = None
    annual_revenue: Optional[Decimal] = None
    country: Optional[str] = None
    region_code: Optional[str] = None
    linkedin_url: Optional[str] = None
    website: Optional[str] = None
    icp_score: Optional[int] = None
    enrichment_source: Optional[str] = None
    enrichment_data: Optional[dict[str, Any]] = None
    status: Optional[str] = None


class OutboundCompanyRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    organization_id: int
    name: str
    domain: Optional[str] = None
    industry: Optional[str] = None
    employee_count: Optional[int] = None
    annual_revenue: Optional[Decimal] = None
    country: Optional[str] = None
    region_code: Optional[str] = None
    linkedin_url: Optional[str] = None
    website: Optional[str] = None
    icp_score: Optional[int] = None
    enrichment_source: Optional[str] = None
    enrichment_data: Optional[dict[str, Any]] = None
    status: str
    created_at: datetime
    updated_at: datetime
