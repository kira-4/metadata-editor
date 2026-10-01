"""Settings endpoints (Telegram notifications, etc)."""
import logging
import re
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
    enabled: bool = True
    app_url: Optional[str] = None


class TelegramSettingsUpdate(BaseModel):
    # If bot_token is None or empty string, preserve the existing stored token.
    bot_token: Optional[str] = None
    chat_id: Optional[str] = None
    message_thread_id: Optional[int] = None
    enabled: Optional[bool] = None  # None leaves it as is
    app_url: Optional[str] = None  # None leaves it as is, "" clears it


class TelegramTestRequest(BaseModel):
    # If bot_token is empty/None, fall back to the stored token (test after save).
    bot_token: Optional[str] = None
    chat_id: str
    message_thread_id: Optional[int] = None
    app_url: Optional[str] = None  # the test message links to the queue, so the link can be tried


class TelegramTestResponse(BaseModel):
    ok: bool
    error: Optional[str] = None


def _public(settings) -> TelegramSettingsResponse:
    token = (settings.bot_token or "").strip()
    return TelegramSettingsResponse(
        bot_token_masked=mask_token(token) if token else None,
        bot_token_set=bool(token),
        chat_id=settings.chat_id,
        message_thread_id=settings.message_thread_id,
        enabled=bool(settings.enabled),
        app_url=settings.app_url,
    )


def _normalize_app_url(raw: Optional[str]) -> Optional[str]:
    """None stays None (leave as is); blank becomes "" (clear); otherwise an http(s) base without a trailing slash."""
    if raw is None:
        return None
    url = raw.strip().split("#", 1)[0].rstrip("/")
    if not url:
        return ""
    if not re.match(r"^https?://[^\s/]+", url):
        raise HTTPException(status_code=400, detail="app_url must start with http:// or https://")
    return url


@settings_router.get("/telegram", response_model=TelegramSettingsResponse)
def get_telegram_settings(db: Session = Depends(get_db)) -> TelegramSettingsResponse:
    """Return the current Telegram settings with the token masked."""
    return _public(SettingsManager.get_telegram_settings(db))


@settings_router.delete("/telegram", response_model=TelegramSettingsResponse)
def disconnect_telegram(db: Session = Depends(get_db)) -> TelegramSettingsResponse:
    """Forget the bot token, chat and topic."""
    return _public(SettingsManager.clear_telegram_settings(db))


@settings_router.put("/telegram", response_model=TelegramSettingsResponse)
def update_telegram_settings(
    request: TelegramSettingsUpdate,
    db: Session = Depends(get_db),
) -> TelegramSettingsResponse:
    """Update Telegram settings. Blank bot_token preserves the existing token."""
    # Normalize inputs
    incoming_token = (request.bot_token or "").strip()
    chat_id = (request.chat_id or "").strip() or None
    thread_id = request.message_thread_id
    app_url = _normalize_app_url(request.app_url)

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
        enabled=request.enabled,
        app_url=app_url,
    )
    return _public(updated)


@settings_router.post("/telegram/test", response_model=TelegramTestResponse)
def test_telegram_settings(
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

    app_url = _normalize_app_url(request.app_url) or None
    ok, error = send_test(incoming_token, chat_id, thread_id, app_url)
    return TelegramTestResponse(ok=ok, error=error or None)
