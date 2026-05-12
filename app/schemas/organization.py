from pydantic import BaseModel
from typing import Optional


class OrganizationCreate(BaseModel):
    name: str
    country: Optional[str] = None
    sector: Optional[str] = None


class OrganizationResponse(BaseModel):
    id: int
    name: str
    country: Optional[str]
    sector: Optional[str]

    model_config = {"from_attributes": True}