"""Telegram notification helper for actionable scanner events.

Uses sync httpx.Client because the scanner runs in a background thread,
not inside the asyncio loop. All helpers swallow exceptions — notifications
are best-effort and must never break the scanner pipeline.
"""
import html
import logging
from typing import Optional, Tuple

import httpx

from app.database import SessionLocal, SettingsManager

logger = logging.getLogger(__name__)

_TELEGRAM_API_BASE = "https://api.telegram.org"
_HTTP_TIMEOUT_SECONDS = 10.0

_REASON_LABEL = {
    "pending": "📋 ملف جديد بانتظار المراجعة",
    "needs_manual": "⚠️ ملف يتطلب تدخلاً يدوياً",
    "error": "❌ خطأ أثناء معالجة ملف",
}


def send_message(
    bot_token: str,
    chat_id: str,
    text: str,
    message_thread_id: Optional[int] = None,
) -> Tuple[bool, str]:
    """
    Post a message to Telegram. Returns (ok, error_message).

    Never raises — network/HTTP errors are captured into the error string.
    """
    if not bot_token or not chat_id:
        return False, "bot_token and chat_id are required"

    url = f"{_TELEGRAM_API_BASE}/bot{bot_token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": True,
    }
    if message_thread_id is not None:
        payload["message_thread_id"] = message_thread_id

    try:
        with httpx.Client(timeout=_HTTP_TIMEOUT_SECONDS) as client:
            response = client.post(url, json=payload)
    except httpx.HTTPError as exc:
        return False, f"HTTP error: {exc}"
    except Exception as exc:  # noqa: BLE001 - defensive wrapper
        return False, f"Unexpected error: {exc}"

    if response.status_code != 200:
        detail = _extract_telegram_error(response)
        return False, f"Telegram API {response.status_code}: {detail}"

    body = _safe_json(response)
    if not body.get("ok", False):
        return False, f"Telegram rejected request: {body.get('description', 'unknown')}"

    return True, ""


def send_test(
    bot_token: str,
    chat_id: str,
    message_thread_id: Optional[int] = None,
) -> Tuple[bool, str]:
    """Send a verification ping with the *provided* credentials (not the stored ones)."""
    text = "✅ <b>Metadata-editor</b>\nرسالة اختبار — إعدادات الإشعارات تعمل."
    return send_message(bot_token, chat_id, text, message_thread_id)


def notify_actionable(item, reason: str) -> None:
    """
    Send a notification about an actionable pending item.

    Called from the scanner thread. Opens its own DB session to fetch
    the latest credentials. Returns early if Telegram is not configured.
    Logs but never raises.
    """
    try:
        db = SessionLocal()
        try:
            settings = SettingsManager.get_telegram_settings(db)
            bot_token = (settings.bot_token or "").strip()
            chat_id = (settings.chat_id or "").strip()
            message_thread_id = settings.message_thread_id
        finally:
            db.close()

        if not bot_token or not chat_id:
            logger.debug("Telegram not configured — skipping notification for item %s", getattr(item, "id", "?"))
            return

        text = _format_message(item, reason)
        ok, error = send_message(bot_token, chat_id, text, message_thread_id)
        if not ok:
            logger.warning("Failed to send Telegram notification for item %s: %s", getattr(item, "id", "?"), error)
    except Exception as exc:  # noqa: BLE001 - notifications must never bubble up
        logger.warning("Unexpected error sending Telegram notification: %s", exc)


def mask_token(token: Optional[str]) -> Optional[str]:
    """Return a masked preview of the bot token for display in the UI."""
    if not token:
        return None
    token = token.strip()
    if len(token) <= 12:
        return "••••••"
    return f"{token[:4]}••••{token[-4:]}"


def _format_message(item, reason: str) -> str:
    """Build a short HTML-formatted Telegram message describing the item."""
    label = _REASON_LABEL.get(reason, f"ℹ️ {reason}")
    title = _field(item, "current_title") or _field(item, "inferred_title") or _field(item, "video_title") or "(بدون عنوان)"
    artist = _field(item, "current_artist") or _field(item, "inferred_artist") or _field(item, "channel") or "(غير معروف)"

    lines = [
        f"<b>{html.escape(label)}</b>",
        f"<b>العنوان:</b> {html.escape(title)}",
        f"<b>الفنان:</b> {html.escape(artist)}",
    ]

    error_message = _field(item, "error_message")
    if error_message and reason in ("needs_manual", "error"):
        # Keep error snippet short so we don't flood Telegram messages
        snippet = error_message if len(error_message) <= 200 else error_message[:197] + "..."
        lines.append(f"<b>السبب:</b> {html.escape(snippet)}")

    return "\n".join(lines)


def _field(item, name: str) -> Optional[str]:
    """Read an attribute from the SQLAlchemy item safely, returning a stripped string or None."""
    value = getattr(item, name, None)
    if value is None:
        return None
    value = str(value).strip()
    return value or None


def _safe_json(response: httpx.Response) -> dict:
    try:
        return response.json()
    except ValueError:
        return {}


def _extract_telegram_error(response: httpx.Response) -> str:
    body = _safe_json(response)
    return str(body.get("description") or response.text or "no detail")
