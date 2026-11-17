#!/usr/bin/env python3
"""Offline parser checker for a keyword-search adapter.

Verifies that a saved search response parses into hits with stable IDs, populated heat
metrics, and query relevance — without touching the network or the host service.

Usage:
    # Mode A: normalized hits already saved as JSON (array or {"items": [...]})
    python verify_search_parser.py --fixture hits.json --query "AI regulation"

    # Mode B: raw response + your adapter class
    python verify_search_parser.py --fixture raw.json --query "AI regulation" \
        --module my_parser.py --class MyParser --parser parse_search

The checker inspects dicts or objects exposing the NewsHit field names. It never imports
httpx or any network client; your adapter may need its own deps to import.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import re
import sys
import unicodedata
from pathlib import Path
from typing import Any


def load_adapter(module_path: str | None, class_name: str | None):
    if not module_path:
        return None
    spec = importlib.util.spec_from_file_location("target_search_adapter", module_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot import module from {module_path}")
    module = importlib.util.module_from_spec(spec)
    # dataclasses resolve annotations via sys.modules; register before exec.
    sys.modules["target_search_adapter"] = module
    spec.loader.exec_module(module)
    if not class_name:
        raise RuntimeError("--class is required when --module is given")
    return getattr(module, class_name)


def to_dict(item: Any) -> dict:
    if isinstance(item, dict):
        return item
    fields = ("item_id", "platform", "title", "url", "rank", "heat", "summary",
              "publication_time", "collected_at", "raw_payload")
    return {f: getattr(item, f) for f in fields if hasattr(item, f)}


def metrics_of(item: Any) -> dict:
    d = to_dict(item)
    heat = d.get("heat") or {}
    if not isinstance(heat, dict):
        heat = getattr(heat, "metrics", {}) or {}
    return heat.get("metrics", {}) if isinstance(heat, dict) else {}


def _norm(text: str) -> str:
    return re.sub(r"\s+", "", unicodedata.normalize("NFKC", str(text)).casefold())


def _bigrams(text: str) -> set[str]:
    s = _norm(text)
    return {s[i:i + 2] for i in range(len(s) - 1) if "\u4e00" <= s[i] <= "\u9fff"}


def relevant(title: str, query: str) -> bool:
    """Cheap CJK-bigram relevance proxy of the production _event_relevant check."""
    q, t = _norm(query), _norm(title)
    if not q or not t:
        return False
    if len(q) <= 4 and q in t:
        return True
    a, b = _bigrams(query), _bigrams(title)
    if a and b:
        inter = a & b
        if len(inter) >= 2 and len(inter) / min(len(a), len(b)) >= 0.25:
            return True
    return bool(set(re.findall(r"[a-z0-9]{3,}", q)) & set(re.findall(r"[a-z0-9]{3,}", t)))


def check(fixture: Path, query: str, adapter_cls, parser_name: str) -> int:
    raw = fixture.read_text(encoding="utf-8")
    if adapter_cls is not None:
        if not hasattr(adapter_cls, parser_name):
            print(f"[FAIL] class {adapter_cls.__name__} has no parser '{parser_name}'")
            return 2
        items = getattr(adapter_cls, parser_name)(raw, "2026-01-01T00:00:00Z")
    else:
        payload = json.loads(raw)
        items = payload["items"] if isinstance(payload, dict) else payload
    items = list(items)

    ids = [to_dict(i).get("item_id") for i in items]
    empty_ids = sum(1 for i in ids if not i)
    dup_ids = len(ids) - len(set(ids))
    no_metrics = sum(1 for i in items if not metrics_of(i))
    irrelevant = sum(1 for i in items
                     if not relevant(to_dict(i).get("title", ""), query))

    verdict = "OK" if (items and not empty_ids and not dup_ids
                       and not no_metrics and irrelevant == 0) else "FAIL"
    print(f"[{verdict}] {fixture.name}: {len(items)} hits | "
          f"empty_id={empty_ids} dup_id={dup_ids} "
          f"no_metrics={no_metrics} irrelevant={irrelevant}")

    if not items:
        print("       no hits — check envelope shape / row path first")
    if empty_ids:
        print("       stable item_id missing on some rows")
    if dup_ids:
        print(f"       {dup_ids} duplicate item_id(s)")
    if no_metrics:
        print("       heat.metrics empty on some rows")
    if irrelevant:
        print(f"       {irrelevant} hit(s) failed the bigram relevance proxy")
    return 0 if verdict == "OK" else 1


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--fixture", required=True, type=Path, help="saved response file")
    ap.add_argument("--query", required=True, help="the keyword used for this search")
    ap.add_argument("--module", help="path to a .py file containing the adapter class")
    ap.add_argument("--class", dest="class_name", help="adapter class name")
    ap.add_argument("--parser", default="parse_search", help="parser method (default: parse_search)")
    args = ap.parse_args()
    try:
        adapter = load_adapter(args.module, args.class_name)
    except Exception as exc:  # noqa: BLE001 - surface import failure to the user
        print(f"[FAIL] adapter import: {type(exc).__name__}: {exc}")
        return 2
    return check(args.fixture, args.query, adapter, args.parser)


if __name__ == "__main__":
    sys.exit(main())
