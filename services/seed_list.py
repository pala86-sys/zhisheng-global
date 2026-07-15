"""種子用戶名單：本地持久化 + 可選 Webhook 通知"""

from __future__ import annotations

import json
import logging
import os
import re
import threading
from datetime import datetime, timezone
from pathlib import Path

import requests

log = logging.getLogger(__name__)

ROOT = Path(__file__).resolve().parent.parent
SEED_FILE = Path(os.environ.get("SEED_LIST_PATH", str(ROOT / "data" / "seed_emails.json")))
_EMAIL_RE = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")
_lock = threading.Lock()


def normalize_email(email: str) -> str:
    return (email or "").strip().lower()


def is_valid_email(email: str) -> bool:
    return bool(_EMAIL_RE.match(email)) and len(email) <= 254


def _load() -> list[dict]:
    if not SEED_FILE.exists():
        return []
    try:
        raw = json.loads(SEED_FILE.read_text(encoding="utf-8"))
        return raw if isinstance(raw, list) else []
    except Exception:
        log.exception("Failed to read seed list")
        return []


def _save(rows: list[dict]) -> None:
    SEED_FILE.parent.mkdir(parents=True, exist_ok=True)
    tmp = SEED_FILE.with_suffix(".tmp")
    tmp.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(SEED_FILE)


def _notify_webhook(entry: dict) -> None:
    url = (os.environ.get("SEED_WEBHOOK_URL") or "").strip()
    if not url:
        return
    try:
        requests.post(url, json=entry, timeout=8)
    except Exception:
        log.exception("Seed webhook notify failed")


def add_seed_email(email: str, *, source: str = "landing") -> dict:
    """
    新增種子用戶 Email。
    回傳 {ok, msg, duplicate?}
    """
    normalized = normalize_email(email)
    if not is_valid_email(normalized):
        return {"ok": False, "msg": "請輸入有效的 Email"}

    now = datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")
    entry = {"email": normalized, "created_at": now, "source": source}

    with _lock:
        rows = _load()
        if any(r.get("email") == normalized for r in rows):
            return {"ok": True, "msg": "這個 Email 已在名單中", "duplicate": True}
        rows.append(entry)
        _save(rows)

    _notify_webhook(entry)
    log.info("Seed signup: %s", normalized)
    return {"ok": True, "msg": "已加入種子用戶名單，感謝你的支持！", "duplicate": False}


def list_seed_emails() -> list[dict]:
    with _lock:
        return list(_load())


def seed_count() -> int:
    with _lock:
        return len(_load())
