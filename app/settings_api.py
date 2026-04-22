"""Settings endpoints (Telegram notifications, etc)."""
import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import SettingsManager, get_db
from app.telegram_notifier import mask_token, send_test

logger = logging.getLogger(__name__)

settings_router = APIRouter(prefix="/api/settings")


class TelegramSettingsResponse(BaseModel):
    """Public view of Telegram settings — the raw token is never exposed."""
    bot_token_masked: Optional[str] = None
    bot_token_set: bool = False
    chat_id: Optional[str] = None
    message_thread_id: Optional[int] = None


class TelegramSettingsUpdate(BaseModel):
    # If bot_token is None or empty string, preserve the existing stored token.
    bot_token: Optional[str] = None
    chat_id: Optional[str] = None
    message_thread_id: Optional[int] = None


class TelegramTestRequest(BaseModel):
    # If bot_token is empty/None, fall back to the stored token (test after save).
    bot_token: Optional[str] = None
    chat_id: str
    message_thread_id: Optional[int] = None


class TelegramTestResponse(BaseModel):
    ok: bool
    error: Optional[str] = None


@settings_router.get("/telegram", response_model=TelegramSettingsResponse)
async def get_telegram_settings(db: Session = Depends(get_db)) -> TelegramSettingsResponse:
    """Return the current Telegram settings with the token masked."""
    settings = SettingsManager.get_telegram_settings(db)
    token = (settings.bot_token or "").strip()
    return TelegramSettingsResponse(
        bot_token_masked=mask_token(token) if token else None,
        bot_token_set=bool(token),
        chat_id=settings.chat_id,
        message_thread_id=settings.message_thread_id,
    )


@settings_router.put("/telegram", response_model=TelegramSettingsResponse)
async def update_telegram_settings(
    request: TelegramSettingsUpdate,
    db: Session = Depends(get_db),
) -> TelegramSettingsResponse:
    """Update Telegram settings. Blank bot_token preserves the existing token."""
    # Normalize inputs
    incoming_token = (request.bot_token or "").strip()
    chat_id = (request.chat_id or "").strip() or None
    thread_id = request.message_thread_id

    existing = SettingsManager.get_telegram_settings(db)

    # Decide whether to overwrite the token
    update_bot_token = bool(incoming_token)
    new_token = incoming_token if update_bot_token else existing.bot_token

    # Require a chat_id whenever a token is present — otherwise notifications can't fire
    if (new_token or "").strip() and not chat_id:
        raise HTTPException(status_code=400, detail="chat_id is required when a bot token is set")

    updated = SettingsManager.update_telegram_settings(
        db,
        bot_token=new_token,
        chat_id=chat_id,
        message_thread_id=thread_id,
        update_bot_token=True,  # we've already computed the effective token
    )

    token = (updated.bot_token or "").strip()
    return TelegramSettingsResponse(
        bot_token_masked=mask_token(token) if token else None,
        bot_token_set=bool(token),
        chat_id=updated.chat_id,
        message_thread_id=updated.message_thread_id,
    )


@settings_router.post("/telegram/test", response_model=TelegramTestResponse)
async def test_telegram_settings(
    request: TelegramTestRequest,
    db: Session = Depends(get_db),
) -> TelegramTestResponse:
    """Send a test message using the submitted credentials (falling back to stored token)."""
    incoming_token = (request.bot_token or "").strip()
    chat_id = (request.chat_id or "").strip()
    thread_id = request.message_thread_id

    if not chat_id:
        return TelegramTestResponse(ok=False, error="chat_id is required")

    if not incoming_token:
        stored = SettingsManager.get_telegram_settings(db)
        incoming_token = (stored.bot_token or "").strip()

    if not incoming_token:
        return TelegramTestResponse(ok=False, error="bot_token is required (none stored)")

    ok, error = send_test(incoming_token, chat_id, thread_id)
    return TelegramTestResponse(ok=ok, error=error or None)
