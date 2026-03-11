from pydantic import BaseModel


class CorrectiveActionBase(BaseModel):
    title: str
    description: str
    status: str
    ai_risk_id: int


class CorrectiveActionCreate(CorrectiveActionBase):
    pass


class CorrectiveActionResponse(CorrectiveActionBase):
    id: int

    class Config:
        from_attributes = True

class CorrectiveActionStatusUpdate(BaseModel):
    new_status: str
    reason: str