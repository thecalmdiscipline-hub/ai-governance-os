from pydantic import BaseModel
from typing import Optional, Literal


class AIRiskCreate(BaseModel):
    title: str
    description: Optional[str] = None
    risk_level: Literal["low", "medium", "high"]
    mitigation: Optional[str] = None
    ai_system_id: int


class AIRiskResponse(BaseModel):
    id: int
    title: str
    description: Optional[str]
    risk_level: Literal["low", "medium", "high"]
    mitigation: Optional[str]
    ai_system_id: int

    class Config:
        orm_mode = True