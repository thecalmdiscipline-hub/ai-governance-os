from pydantic import BaseModel
from typing import Optional


class AISystemCreate(BaseModel):
    name: str
    description: Optional[str] = None
    purpose: Optional[str] = None
    organization_id: int


class AISystemResponse(BaseModel):
    id: int
    name: str
    description: Optional[str]
    purpose: Optional[str]
    organization_id: int

    class Config:
        orm_mode = True
from datetime import datetime
from typing import Optional
from pydantic import BaseModel


class AISystemUpdate(BaseModel):
    risk_category: Optional[str] = None
    lifecycle_stage: Optional[str] = None
    conformity_assessed: Optional[bool] = None
    last_reviewed_at: Optional[datetime] = None        