#!/usr/bin/env python3
"""
Trace WBXML payloads to JSON token stream for comparison/debugging.

Usage:
  python tools/trace_wbxml.py path/to/payload.wbxml > out.json
  # Or with hex input:
  echo "03016a..." | python tools/trace_wbxml.py --hex - > out.json
"""

from __future__ import annotations

import argparse
import json
import sys
from typing import Any, Dict, List


def _read_bytes(path: str, as_hex: bool) -> bytes:
    data = sys.stdin.buffer.read() if path == "-" else open(path, "rb").read()
    if as_hex:
        s = data.decode("utf-8").strip()
        return bytes.fromhex(s)
    return data


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("path", help="WBXML file path or - for stdin")
    p.add_argument("--hex", action="store_true", help="Treat input as hex string")
    args = p.parse_args()

    blob = _read_bytes(args.path, args.hex)
    try:
        # Use local parser if present
        from app.wbxml_parser import parse_wbxml  # type: ignore

        tokens = parse_wbxml(blob)
        # Ensure serializable
        print(json.dumps(tokens, ensure_ascii=False))
    except Exception:
        # Fallback: dump first bytes preview
        out = {
            "length": len(blob),
            "first64": blob[:64].hex(),
        }
        print(json.dumps(out))


if __name__ == "__main__":
    main()
