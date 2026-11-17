#!/usr/bin/env python3
"""Offline triage for a keyword-search result set.

Answers: is the set empty? duplicated across platforms? full of low-heat or
 irrelevant rows? Prints a symptom-oriented diagnosis with the next action.

Usage:
    python diagnose_search.py --fixture results.json
    python diagnose_search.py --fixture results.json --min-heat 2500 --query "AI 监管"

Input: JSON array of hits, or {"items": [...]}. Each hit is a dict (or object) with
title / url / platform / heat fields, mirroring the NewsHit contract.
"""

from __future__ import annotations

import argparse
import json
import math
import re
import unicodedata
from pathlib import Path
from typing import Any


def to_dict(item: Any) -> dict:
    if isinstance(item, dict):
        return item
    fields = ("item_id", "platform", "title", "url", "rank", "heat", "summary")
    return {f: getattr(item, f) for f in fields if hasattr(item, f)}


def heat_of(item: Any) -> float:
    d = to_dict(item)
    heat = d.get("heat") or {}
    if not isinstance(heat, dict):
        heat = getattr(heat, "metrics", {}) or {}
    if not isinstance(heat, dict):
        return 0.0
    metrics = heat.get("metrics") if isinstance(heat.get("metrics"), dict) else heat
    vals = [v for v in metrics.values() if isinstance(v, (int, float)) and v > 0]
    return float(max(vals)) if vals else 0.0


def canonical(url: str) -> str:
    s = re.sub(r"^https?://", "", str(url).casefold())
    s = s.split("#", 1)[0].split("?", 1)[0].rstrip("/")
    return s


def _norm(text: str) -> str:
    return re.sub(r"\s+", "", unicodedata.normalize("NFKC", str(text)).casefold())


def diagnose(items: list[dict], min_heat: float, query: str) -> int:
    n = len(items)
    print(f"hits: {n}")
    if n == 0:
        print("[EMPTY] no hits — check envelope shape first, then cookies (Toutiao), "
              "then anti-bot / rate limit.")
        return 1

    issues = 0
    # duplicates
    urls = [canonical(to_dict(i).get("url", "")) for i in items]
    dup = len(urls) - len(set(u for u in urls if u))
    if dup:
        issues += 1
        print(f"[DUP] {dup} duplicate URL(s) — canonicalize URL + normalize title, "
              "keep higher-priority source.")
    else:
        print("[OK]   no duplicate URLs")

    # heat
    heats = [heat_of(i) for i in items]
    below = sum(1 for h in heats if h < min_heat) if min_heat > 0 else 0
    if min_heat > 0 and below == n:
        issues += 1
        print(f"[FLOOR-WIPE] all {n} hits below heat floor {min_heat:g} — "
              "this direction would be emptied; enable low-heat fallback pool.")
    elif below:
        print(f"[warn] {below}/{n} hits below heat floor {min_heat:g}")
    else:
        print("[OK]   heat floor not wiping the set")

    # rank / heat evidence
    no_heat = sum(1 for h in heats if h <= 0)
    if no_heat:
        issues += 1
        print(f"[NO-EVIDENCE] {no_heat} hit(s) have no positive heat signal — "
              "no silent zeros; check adapter heat mapping.")
    else:
        print("[OK]   every hit has a positive heat signal")

    # recommendation / relevance proxy
    if query:
        q = _norm(query)
        matched = sum(1 for i in items if q and q in _norm(to_dict(i).get("title", "")))
        if matched == 0:
            issues += 1
            print("[RELEVANCE] no title contains the query — likely recommendation "
                  "fallbacks; apply keyword-anchor / bigram relevance + AI review.")
        else:
            print(f"[OK]   {matched}/{n} titles contain the query")

    print(f"\nverdict: {'ATTENTION — ' + str(issues) + ' issue(s)' if issues else 'HEALTHY'}")
    return 0 if issues == 0 else 1


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--fixture", required=True, type=Path, help="saved results JSON")
    ap.add_argument("--min-heat", type=float, default=0.0, help="heat floor to test against")
    ap.add_argument("--query", default="", help="query keyword for relevance proxy")
    args = ap.parse_args()
    payload = json.loads(args.fixture.read_text(encoding="utf-8"))
    items = payload["items"] if isinstance(payload, dict) else payload
    return diagnose(list(items), args.min_heat, args.query)


if __name__ == "__main__":
    raise SystemExit(main())
