from datetime import date
from typing import Optional

from pydantic import BaseModel, ConfigDict, model_validator


class CorrectiveActionCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str
    description: str
    ai_risk_id: Optional[int] = None
    ai_incident_id: Optional[int] = None
    # owner: free text (a role or team name, e.g. "Compliance team") — the API never validates or
    # requires this to be a person's name; the portal shows a short warning instead.
    owner: Optional[str] = None
    due_date: Optional[date] = None

    @model_validator(mode="after")
    def _at_least_one_link(self):
        if self.ai_risk_id is None and self.ai_incident_id is None:
            raise ValueError("ai_risk_id or ai_incident_id is required")
        return self


class CorrectiveActionResponse(BaseModel):
    id: int
    title: str
    description: str
    status: str
    ai_risk_id: Optional[int]
    ai_incident_id: Optional[int]
    owner: Optional[str]
    due_date: Optional[date]

    model_config = ConfigDict(from_attributes=True)


class CorrectiveActionStatusUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    new_status: str
    reason: str