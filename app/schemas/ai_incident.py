from pydantic import BaseModel
from typing import Optional, Literal
from datetime import datetime


class AIIncidentCreate(BaseModel):
    title: str
    description: Optional[str] = None
    severity: Literal["low", "medium", "high", "critical"]
    ai_system_id: int


class AIIncidentResponse(BaseModel):
    id: int
    title: str
    description: Optional[str]
    severity: Literal["low", "medium", "high", "critical"]
    detected_at: datetime
    ai_system_id: int

    class Config:
        orm_mode = True