#!/usr/bin/env python3
import base64
import json
import os
import sqlite3
import sys
from typing import Optional, Tuple

# Ensure app modules are importable
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _read_latest_wbxml_hex_from_log(log_path: str) -> Optional[str]:
    if not os.path.exists(log_path):
        return None
    latest_hex = None
    latest_ts = None
    try:
        with open(log_path, "r", encoding="utf-8", errors="ignore") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                except Exception:
                    continue
                if obj.get("event") == "sync_emails_sent_wbxml_simple" and obj.get(
                    "wbxml_full_hex"
                ):
                    latest_hex = obj.get("wbxml_full_hex")
                    latest_ts = obj.get("ts")
    except Exception:
        return None
    return latest_hex


def _decode_mb_uint32(data: bytes, pos: int) -> Tuple[int, int]:
    """Decode WBXML mb_u_int32 starting at position pos. Returns (value, new_pos)."""
    result = 0
    while True:
        if pos >= len(data):
            raise ValueError("Truncated mb_u_int32")
        byte = data[pos]
        pos += 1
        result = (result << 7) | (byte & 0x7F)
        if (byte & 0x80) == 0:
            break
    return result, pos


def _extract_largest_opaque(data: bytes) -> Optional[bytes]:
    """Return the payload of the largest OPAQUE (0xC3) block in the WBXML payload."""
    i = 0
    best = None
    best_len = -1
    while i < len(data):
        b = data[i]
        i += 1
        if b == 0xC3:  # OPAQUE token
            try:
                length, i2 = _decode_mb_uint32(data, i)
            except Exception:
                break
            end = i2 + length
            if end <= len(data):
                chunk = data[i2:end]
                if length > best_len:
                    best = chunk
                    best_len = length
                i = end
            else:
                break
        else:
            # Skip inline string content for speed (STR_I)
            if b == 0x03:
                while i < len(data) and data[i] != 0x00:
                    i += 1
                i += 1  # consume NUL
            # SWITCH_PAGE has 1 param byte
            elif b == 0x00:
                i += 1
            else:
                # Other tokens: nothing to do (single-byte tokens); continue scanning
                pass
    return best


def _resolve_db_path() -> Optional[str]:
    # Try env DATABASE_URL (sqlite:////abs/path or sqlite:///rel)
    db_url = os.environ.get("DATABASE_URL")
    candidates = []
    if db_url and db_url.startswith("sqlite:"):
        path = db_url.split("sqlite:///")[-1]
        if db_url.startswith("sqlite:////"):
            path = db_url[len("sqlite:////") :]
            candidates.append("/" + path if not path.startswith("/") else path)
        else:
            candidates.append(path)
    # Common defaults
    repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    candidates.extend(
        [
            os.path.join(repo_root, "data", "email_system.db"),
            os.path.join(repo_root, "email_system.db"),
        ]
    )
    for p in candidates:
        if p and os.path.exists(p):
            return p
    return None


def _get_latest_email_b64_sqlite(db_path: str) -> Optional[str]:
    try:
        conn = sqlite3.connect(db_path)
        cur = conn.cursor()
        cur.execute(
            "SELECT mime_content FROM emails WHERE IFNULL(is_deleted, 0)=0 ORDER BY id DESC LIMIT 1"
        )
        row = cur.fetchone()
        conn.close()
        if not row or not row[0]:
            return None
        mime_content = row[0]
        try:
            raw = base64.b64decode(mime_content)
        except Exception:
            raw = str(mime_content).encode("utf-8", errors="ignore")
        return base64.b64encode(raw).decode("ascii")
    except Exception:
        return None


def _sanitize_hex(s: str) -> str:
    # Keep only [0-9A-Fa-f]
    return "".join(ch for ch in s if ch.isdigit() or ("a" <= ch.lower() <= "f"))


def main():
    # 1) Load WBXML hex
    log_path = os.environ.get(
        "AS_LOG_PATH",
        os.path.join(
            os.path.dirname(os.path.dirname(__file__)), "activesync", "activesync.log"
        ),
    )
    wbxml_hex = None

    # If provided via stdin, prefer that
    if not sys.stdin.isatty():
        stdin_data = sys.stdin.read().strip()
        if stdin_data:
            wbxml_hex = stdin_data

    if not wbxml_hex:
        wbxml_hex = _read_latest_wbxml_hex_from_log(log_path)

    if not wbxml_hex:
        print("ERROR: Could not find wbxml_full_hex in log and no input provided.")
        sys.exit(2)

    cleaned_hex = _sanitize_hex(wbxml_hex)
    try:
        wbxml_bytes = bytes.fromhex(cleaned_hex)
    except Exception as e:
        print(f"ERROR: Invalid WBXML hex after sanitization: {e}")
        sys.exit(2)

    # 2) Extract OPAQUE (largest) as MIME
    mime_bytes = _extract_largest_opaque(wbxml_bytes)
    if not mime_bytes:
        print("ERROR: Could not locate OPAQUE MIME in WBXML.")
        sys.exit(3)
    wbxml_mime_b64 = base64.b64encode(mime_bytes).decode("ascii")

    # 3) Load latest email MIME from DB (sqlite3)
    db_path = _resolve_db_path()
    if not db_path:
        # Try default mounted path used in Docker
        db_path = "/app/data/email_system.db"
        if not os.path.exists(db_path):
            print(
                "ERROR: Could not locate database file. Set DATABASE_URL or place DB under ./data/email_system.db"
            )
            sys.exit(5)
    db_b64 = _get_latest_email_b64_sqlite(db_path)

    if not db_b64:
        print("ERROR: No email with MIME content found in database.")
        sys.exit(4)

    # 4) Compare
    if wbxml_mime_b64 == db_b64:
        print("OK: WBXML MIME matches DB last email MIME (base64 identical).")
        print(f"MIME size: {len(mime_bytes)} bytes")
        sys.exit(0)
    else:
        # Provide brief diagnostics
        print("MISMATCH: WBXML MIME != DB last email MIME")
        print(f"WBXML MIME size: {len(mime_bytes)} bytes")
        try:
            db_raw = base64.b64decode(db_b64)
        except Exception:
            db_raw = b""
        print(f"DB MIME size: {len(db_raw)} bytes")

        # Show small diff windows
        def head_tail(b: bytes, n: int = 64) -> str:
            h = base64.b64encode(b[:n]).decode("ascii")
            t = base64.b64encode(b[-n:]).decode("ascii") if len(b) > n else ""
            return f"head64={h} tail64={t}"

        print("WBXML sample:", head_tail(mime_bytes))
        print("DB sample:", head_tail(db_raw))
        sys.exit(1)


if __name__ == "__main__":
    main()
