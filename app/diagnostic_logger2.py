#!/usr/bin/env python3
"""
ActiveSync split diagnostic logger.

Writes JSONL events under logs/activesync/{YYYY-MM-DD}/ into
separate category files for easier analysis:
  - comm.log   : high-level flow and request/response metadata
  - data.log   : WBXML hex previews, sizes, tokenization summaries
  - state.log  : sync state transitions, SyncKey, MoreAvailable
  - errors.log : exceptions, spec violations, unexpected states
  - perf.log   : timing and counters per request

Usage:
  from app.diagnostic_logger2 import write_event, aslog
  aslog("comm", "wbxml_response", status_code=200, ...)

Notes:
  - Honors config flags AS_LOG_SPLIT (enable), AS_REDACT (redact PII)
  - Auto-creates date directories; safe for concurrent appends
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from typing import Any, Dict

try:
    # Local config flags
    from config import DEBUG  # type: ignore
    from config import AS_LOG_SPLIT, AS_REDACT  # type: ignore
except Exception:  # pragma: no cover - default when config not yet updated
    DEBUG = True
    AS_LOG_SPLIT = True
    AS_REDACT = False


BASE_DIR = os.environ.get("LOGS_DIR", "logs")
ROOT = os.path.join(BASE_DIR, "activesync")

CATEGORY_TO_FILE = {
    "comm": "comm.log",
    "data": "data.log",
    "state": "state.log",
    "errors": "errors.log",
    "perf": "perf.log",
}


def _today_dir() -> str:
    today = datetime.now(timezone.utc).date().isoformat()
    path = os.path.join(ROOT, today)
    os.makedirs(path, exist_ok=True)
    return path


def _redact(value: Any) -> Any:
    if not AS_REDACT:
        return value
    if isinstance(value, str):
        # Basic redaction of addresses and auth-like fields
        if "@" in value:
            return "<redacted@domain>"
        if value.lower().startswith("bearer ") or value.lower().startswith("basic "):
            return "<redacted>"
    if isinstance(value, dict):
        return {k: _redact(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_redact(v) for v in value]
    return value


def write_event(category: str, event: str, **fields: Any) -> None:
    if not AS_LOG_SPLIT:
        return

    cat = CATEGORY_TO_FILE.get(category, "comm.log")
    dir_path = _today_dir()
    file_path = os.path.join(dir_path, cat)

    entry: Dict[str, Any] = {
        "ts": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "event": event,
    }
    entry.update(fields or {})
    entry = _redact(entry)

    try:
        with open(file_path, "a", encoding="utf-8") as fp:
            fp.write(json.dumps(entry) + "\n")
    except Exception:
        # Fallback to root single file in case of unexpected path issues
        try:
            fallback = os.path.join(ROOT, "fallback.log")
            os.makedirs(os.path.dirname(fallback), exist_ok=True)
            with open(fallback, "a", encoding="utf-8") as fp:
                fp.write(json.dumps({"category": category, **entry}) + "\n")
        except Exception:
            pass


def aslog(category: str, event: str, **fields: Any) -> None:
    """Convenience wrapper matching common call style.

    Example: aslog("state", "sync_key_update", old=..., new=...)
    """
    write_event(category, event, **fields)
