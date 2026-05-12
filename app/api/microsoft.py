from uuid import uuid4
from typing import Optional, Dict, Any

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.api.dependencies import get_db, get_current_user
from app.models.user import User
from app.core.microsoft_config import MICROSOFT_CLIENT_ID
from app.services.microsoft.oauth import build_authorization_url, exchange_code_for_token
from app.integrations.microsoft.graph_client import MicrosoftGraphClient
from app.models.microsoft_token import MicrosoftToken

router = APIRouter(prefix="/microsoft", tags=["Microsoft 365"])


@router.get("/status")
def microsoft_status(current_user: User = Depends(get_current_user)):
    return {
        "status": "ok",
        "connected": False,
        "message": "Microsoft 365 not connected yet",
        "client_configured": bool(MICROSOFT_CLIENT_ID),
        "organization_id": current_user.organization_id,
    }


@router.post("/connect")
def microsoft_connect(current_user: User = Depends(get_current_user)):
    if not MICROSOFT_CLIENT_ID:
        raise HTTPException(status_code=400, detail="Microsoft client is not configured")

    state = str(uuid4())
    url = build_authorization_url(state)
    return {
        "status": "ok",
        "authorization_url": url,
        "state": state,
    }


@router.get("/start")
def microsoft_start(current_user: User = Depends(get_current_user)):
    if not MICROSOFT_CLIENT_ID:
        raise HTTPException(status_code=400, detail="Microsoft client is not configured")

    state = str(uuid4())
    url = build_authorization_url(state)
    return RedirectResponse(url=url)


@router.get("/callback")
def microsoft_callback(
    code: str = Query(...),
    state: str = Query(""),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    del db
    del state

    token_data = exchange_code_for_token(code)
    access_token = token_data.get("access_token")
    if not access_token:
        raise HTTPException(status_code=400, detail="No access token received from Microsoft")

    graph = MicrosoftGraphClient(access_token)
    me = graph.get_me()

    return {
        "status": "ok",
        "message": "Microsoft 365 token exchange succeeded",
        "organization_id": current_user.organization_id,
        "microsoft_user": {
            "id": me.get("id"),
            "displayName": me.get("displayName"),
            "userPrincipalName": me.get("userPrincipalName"),
        },
        "token_received": True,
    }


@router.post("/files/list")
def microsoft_list_files(
    payload: Optional[Dict[str, Any]] = None,
    current_user: User = Depends(get_current_user),
):
    payload = payload or {}
    access_token = payload.get("access_token")

    if not access_token:
        token_row = db.query(MicrosoftToken).filter(
            MicrosoftToken.organization_id == current_user.organization_id
        ).order_by(MicrosoftToken.id.desc()).first()

        if not token_row:
            raise HTTPException(status_code=400, detail="No Microsoft connection found")

        access_token = token_row.access_token

    graph = MicrosoftGraphClient(access_token)
    items = graph.list_drive_items()

    return {
        "status": "ok",
        "organization_id": current_user.organization_id,
        "total": len(items),
        "items": items,
    }


from app.services.microsoft.microsoft_sync import sync_onedrive_to_documents


@router.post("/sync")
def microsoft_sync_documents(
    payload: dict,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    access_token = payload.get("access_token")

    if not access_token:
        token_row = db.query(MicrosoftToken).filter(
            MicrosoftToken.organization_id == current_user.organization_id
        ).order_by(MicrosoftToken.id.desc()).first()

        if not token_row:
            raise HTTPException(status_code=400, detail="No Microsoft connection found")

        access_token = token_row.access_token

    docs = sync_onedrive_to_documents(
        db=db,
        organization_id=int(current_user.organization_id),
        user_id=current_user.id,
        access_token=access_token,
    )

    return {
        "status": "ok",
        "imported": len(docs),
        "documents": docs,
    }
