#!/usr/bin/env python3
"""
Compare two WBXML token traces and highlight ordering/value mismatches.

Usage:
  python tools/compare_traces.py left.json right.json
  # or with hex inputs:
  python tools/compare_traces.py --hex left.hex right.hex
"""

from __future__ import annotations

import argparse
import json
from typing import Any, List


def _load(path: str, as_hex: bool) -> Any:
    if as_hex:
        return {"hex": open(path, "r", encoding="utf-8").read().strip()}
    return json.load(open(path, "r", encoding="utf-8"))


def _flatten(tokens: Any) -> List[str]:
    out: List[str] = []
    if isinstance(tokens, list):
        for t in tokens:
            out.extend(_flatten(t))
    elif isinstance(tokens, dict):
        # naive stringify
        out.append(json.dumps(tokens, sort_keys=True))
    else:
        out.append(str(tokens))
    return out


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("left")
    p.add_argument("right")
    p.add_argument("--hex", action="store_true")
    args = p.parse_args()

    left = _load(args.left, args.hex)
    right = _load(args.right, args.hex)

    if args.hex:
        if left.get("hex") == right.get("hex"):
            print("OK: hex matches")
        else:
            print("DIFF: hex differs")
        return

    lf = _flatten(left)
    rf = _flatten(right)
    maxlen = max(len(lf), len(rf))
    diffs = 0
    for i in range(maxlen):
        lv = lf[i] if i < len(lf) else "<missing>"
        rv = rf[i] if i < len(rf) else "<missing>"
        if lv != rv:
            print(f"[{i}]\n- {lv}\n+ {rv}")
            diffs += 1
            if diffs > 200:
                print("... (truncated)")
                break
    if diffs == 0:
        print("OK: token streams match")


if __name__ == "__main__":
    main()
