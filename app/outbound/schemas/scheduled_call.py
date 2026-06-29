from __future__ import annotations

from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict

CallType = Literal["intake_b", "sales_c"]
MeetingPlatform = Literal["zoom", "google_meet", "teams", "whereby"]
CallStatus = Literal["scheduled", "completed", "no_show", "cancelled", "rescheduled"]


class ScheduledCallCreate(BaseModel):
    organization_id: int
    prospect_id: str
    call_type: CallType
    scheduled_at: datetime
    duration_minutes: int
    meeting_platform: MeetingPlatform = "zoom"
    meeting_link: str
    calcom_event_id: Optional[str] = None
    status: CallStatus = "scheduled"
    notes: Optional[str] = None


class ScheduledCallUpdate(BaseModel):
    call_type: Optional[CallType] = None
    scheduled_at: Optional[datetime] = None
    duration_minutes: Optional[int] = None
    meeting_platform: Optional[MeetingPlatform] = None
    meeting_link: Optional[str] = None
    calcom_event_id: Optional[str] = None
    status: Optional[CallStatus] = None
    notes: Optional[str] = None


class ScheduledCallRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    organization_id: int
    prospect_id: str
    call_type: str
    scheduled_at: datetime
    duration_minutes: int
    meeting_platform: str
    meeting_link: str
    calcom_event_id: Optional[str] = None
    status: str
    notes: Optional[str] = None
    created_at: datetime
    updated_at: datetime
