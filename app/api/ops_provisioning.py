"""POST /ops/tenants/provision: a new customer in one call (see app/services/provisioning.py)."""
from typing import List, Optional

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.dependencies import get_db, require_ops_access
from app.models.user import User
from app.services.provisioning import ProvisionParams, ProvisioningError, provision_tenant

router = APIRouter(prefix="/ops", tags=["Ops"], dependencies=[Depends(require_ops_access)])

_NO_STORE = {"Cache-Control": "no-store"}  # the response of a first call contains a one-time password


class ProvisionBody(BaseModel):
    idempotency_key: str
    organization_name: str
    country: Optional[str] = None
    sector: Optional[str] = None
    tier: str
    modules: List[str]
    admin_username: str
    admin_email: Optional[str] = None  # validated, not stored (no e-mail column on users)
    include_demo_document: bool = True
    include_demo_run: bool = False


@router.post("/tenants/provision")
def provision(
    body: ProvisionBody,
    current_user: User = Depends(require_ops_access),
    db: Session = Depends(get_db),
):
    try:
        result = provision_tenant(db, ProvisionParams(**body.model_dump()), actor=current_user)
    except ProvisioningError as exc:
        return JSONResponse(status_code=exc.status, content={"error": exc.code, "problems": exc.problems}, headers=_NO_STORE)
    status = 201 if result["created"] else 200
    return JSONResponse(status_code=status, content=result, headers=_NO_STORE)
