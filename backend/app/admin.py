import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Body, status

from . import auth, state_manager, security, redemption

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/admin", tags=["admin"])


@router.get("/sessions")
async def list_sessions(
    _: Annotated[dict, Depends(auth.require_admin)],
    limit: int = Query(50, ge=1, le=500),
):
    # Build a minimal summary list for admin
    sessions = state_manager.SESSIONS
    items = []
    for pid, s in sessions.items():
        last_modified = s.get("last_modified", 0)
        try:
            enc = security.encrypt_player_id(pid)
        except Exception:
            enc = ""
        items.append(
            {
                "player_id": pid,
                "encrypted_id": enc,
                "last_modified": last_modified,
                "daily_success_achieved": bool(s.get("daily_success_achieved")),
                "pending_punishment": s.get("pending_punishment"),
            }
        )
    items.sort(key=lambda x: x["last_modified"], reverse=True)
    return items[:limit]


def _resolve_player_id(id_or_encrypted: str) -> str | None:
    # Try decrypt first; fall back to plain ID if decrypt fails
    if not id_or_encrypted:
        return None
    real = security.decrypt_player_id(id_or_encrypted)
    return real if real else id_or_encrypted


@router.get("/session/{id_or_encrypted}")
async def get_session_detail(
    _: Annotated[dict, Depends(auth.require_admin)],
    id_or_encrypted: str,
):
    pid = _resolve_player_id(id_or_encrypted)
    session = await state_manager.get_session(pid)
    if session is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")
    return session


@router.post("/sessions/{id_or_encrypted}/clear")
async def clear_session(
    _: Annotated[dict, Depends(auth.require_admin)],
    id_or_encrypted: str,
):
    pid = _resolve_player_id(id_or_encrypted)
    if pid not in state_manager.SESSIONS:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")
    await state_manager.clear_session(pid)
    return {"ok": True}


@router.post("/redemptions")
async def create_redemption(
    current_admin: Annotated[dict, Depends(auth.require_admin)],
    body: dict = Body(...),
):
    try:
        quota = float(body.get("quota"))
    except (TypeError, ValueError):
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Invalid quota")
    name = (body.get("name") or "admin_generated").strip() or "admin_generated"
    user_id = int(current_admin.get("id") or 0)

    code = redemption.generate_and_insert_redemption_code(user_id=user_id, quota=quota, name=name)
    if not code:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to create code")
    return {"code": code}
