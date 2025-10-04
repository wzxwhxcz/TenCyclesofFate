import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Body, status

from . import auth, state_manager, security
from .config import settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/admin", tags=["admin"])


@router.get("/check-permission")
async def check_admin_permission(
    current_user: Annotated[dict, Depends(auth.get_current_active_user)],
):
    """
    检查当前用户是否有管理员权限
    返回用户信息和权限状态
    """
    username = current_user.get("username", "")
    trust_level = current_user.get("trust_level", 0)
    
    # 检查是否在白名单中
    whitelist = settings.ADMIN_USER_WHITELIST
    is_whitelisted = username in whitelist if whitelist else False
    
    # 检查信任等级
    has_trust_level = trust_level >= settings.ADMIN_MIN_TRUST_LEVEL
    
    # 判断是否是管理员
    is_admin = is_whitelisted or has_trust_level
    
    return {
        "username": username,
        "trust_level": trust_level,
        "is_admin": is_admin,
        "is_whitelisted": is_whitelisted,
        "has_trust_level": has_trust_level
    }


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


@router.post("/sessions/{id_or_encrypted}/update-opportunities")
async def update_opportunities(
    _: Annotated[dict, Depends(auth.require_admin)],
    id_or_encrypted: str,
    opportunities: int = Body(..., ge=0, le=100, description="新的机缘次数"),
):
    """更新指定用户的机缘次数"""
    pid = _resolve_player_id(id_or_encrypted)
    session = await state_manager.get_session(pid)
    
    if session is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")
    
    # 更新机缘次数
    session["opportunities_remaining"] = opportunities
    
    # 如果设置了机缘次数大于0，确保用户可以继续游戏
    if opportunities > 0 and session.get("daily_success_achieved"):
        session["daily_success_achieved"] = False
        logger.info(f"Reset daily_success_achieved for {pid} after updating opportunities to {opportunities}")
    
    # 保存更新后的会话
    await state_manager.save_session(pid, session)
    
    logger.info(f"Updated opportunities for {pid} to {opportunities}")
    
    return {
        "ok": True,
        "player_id": pid,
        "opportunities_remaining": opportunities,
        "message": f"成功将用户 {pid} 的机缘次数更新为 {opportunities}"
    }


@router.post("/sessions/{id_or_encrypted}/update")
async def update_session(
    _: Annotated[dict, Depends(auth.require_admin)],
    id_or_encrypted: str,
    updates: dict = Body(..., description="要更新的会话字段"),
):
    """更新指定用户的会话数据
    
    允许管理员修改会话的任意字段，包括但不限于：
    - opportunities_remaining: 机缘次数
    - daily_success_achieved: 今日成功状态
    - pending_punishment: 待处理惩罚
    - current_trial: 当前试炼
    - trial_count: 试炼次数
    - 以及其他任何会话字段
    """
    pid = _resolve_player_id(id_or_encrypted)
    session = await state_manager.get_session(pid)
    
    if session is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")
    
    # 记录原始值用于日志
    original_values = {}
    for key in updates:
        if key in session:
            original_values[key] = session[key]
    
    # 应用更新
    for key, value in updates.items():
        # 防止修改一些关键系统字段
        if key in ["player_id", "encrypted_id"]:
            logger.warning(f"Attempted to modify protected field '{key}' for {pid}")
            continue
        
        session[key] = value
        logger.info(f"Updated {key} for {pid}: {original_values.get(key, 'undefined')} -> {value}")
    
    # 特殊逻辑：如果设置了机缘次数大于0，确保用户可以继续游戏
    if updates.get("opportunities_remaining", 0) > 0 and session.get("daily_success_achieved"):
        session["daily_success_achieved"] = False
        logger.info(f"Auto-reset daily_success_achieved for {pid} after updating opportunities")
    
    # 更新修改时间
    import time
    session["last_modified"] = time.time()
    
    # 保存更新后的会话
    await state_manager.save_session(pid, session)
    
    return {
        "ok": True,
        "player_id": pid,
        "updated_fields": list(updates.keys()),
        "message": f"成功更新用户 {pid} 的会话数据"
    }


"""兑换码功能已下线：相关管理端接口已移除。"""
