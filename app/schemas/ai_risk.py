from pydantic import BaseModel, ConfigDict
from typing import Optional, Literal


class AIRiskCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str
    description: Optional[str] = None
    risk_level: Literal["low", "medium", "high"]
    mitigation: Optional[str] = None
    ai_system_id: int


class AIRiskUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: Optional[str] = None
    description: Optional[str] = None
    mitigation: Optional[str] = None
    risk_level: Optional[Literal["low", "medium", "high"]] = None


class AIRiskResponse(BaseModel):
    id: int
    title: str
    description: Optional[str]
    risk_level: Literal["low", "medium", "high"]
    mitigation: Optional[str]
    ai_system_id: int

    model_config = {"from_attributes": True}