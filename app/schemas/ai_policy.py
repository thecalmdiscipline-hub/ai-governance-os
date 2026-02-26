from pydantic import BaseModel


class AIPolicyCreate(BaseModel):
    organization_id: int


class AIPolicyResponse(BaseModel):
    id: int
    purpose: str
    principles: str
    risk_commitment: str
    monitoring_commitment: str
    organization_id: int

    class Config:
        from_attributes = True