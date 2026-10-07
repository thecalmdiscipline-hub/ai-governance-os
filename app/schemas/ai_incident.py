from pydantic import BaseModel, ConfigDict
from typing import Optional, Literal
from datetime import datetime

# Batch O1 (2026-10-07): ai_system_id stays required (not "optional" as the hand-off's prose
# suggested) — AIIncident has no organization_id column of its own; the linked AISystem is the
# only way an incident is ever scoped to a tenant (see GET /ai-incidents's join). An incident with
# no system would be unscoped and invisible in every org's list forever. Reported as a deliberate
# deviation, not a silent one.
INCIDENT_STATUSES = ("open", "in_progress", "closed")


class AIIncidentCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str
    description: Optional[str] = None
    severity: Literal["low", "medium", "high", "critical"]
    ai_system_id: int
    detected_at: Optional[datetime] = None


class AIIncidentUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: Optional[str] = None
    description: Optional[str] = None
    severity: Optional[Literal["low", "medium", "high", "critical"]] = None
    status: Optional[Literal["open", "in_progress", "closed"]] = None


class AIIncidentResponse(BaseModel):
    id: int
    title: str
    description: Optional[str]
    severity: Literal["low", "medium", "high", "critical"]
    detected_at: datetime
    status: str
    ai_system_id: int

    model_config = {"from_attributes": True}