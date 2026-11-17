# Data contract

The shapes every adapter and funnel stage agrees on. Mirrors the companion
`china-hot-board-skill` contract so the two skills interoperate.

## ProviderCapture

Every search adapter returns `ProviderCapture(raw_text, raw_suffix, items, metadata)`:

- `raw_text` — the untouched response (for diagnosis / reparse).
- `raw_suffix` — file-type hint (`.json`, `.html`, `.jsonp`).
- `items` — tuple of `NewsHit`.
- `metadata` — non-secret diagnostics, e.g. `{"schema_warning": "juejin envelope code=..."}`.
  Never put cookies, tokens or credentials here.

## NewsHit (frozen)

| Field | Type | Meaning |
|---|---|---|
| `item_id` | str | Stable across runs: `<platform>_<hash or native id>`. A sha256 of NFKC/casefolded query+url is acceptable. |
| `platform` | str | source slug: `toutiao` / `juejin` / `netease_news` / `sina_news` / `thepaper` |
| `title` | str | article title |
| `url` | str | real article URL (not a session redirect) |
| `rank` | int \| None | native position starting at 1; search hits without native rank use `search_rank` from position |
| `heat` | HeatMetrics | platform metrics (views / interactions / comments / rank) |
| `summary` | str | brief/abstract |
| `publication_time` | str \| None | publish timestamp when available |
| `collected_at` | str | collection timestamp |
| `raw_payload` | dict | all platform-specific fields, untouched |

## HeatMetrics / HeatEvidence

- `HeatMetrics.metrics` — mapping of metric name → positive number. Recognized names:
  `views`, `comments`, `likes`, `collects`, `interactions`, `top_num`, `hot_rank`,
  `search_rank`, `interaction_num`, `praise_times`.
- `HeatEvidence` ties a hit's heat to a real signal: `metric_name`, `qualified_by`,
  and a positive value. A search hit must carry a positive signal; no silent zeros, no
  invented numbers.
- Structural validation rejects an evidence object whose `qualified_by` metric is missing
  or ≤ 0.

## ItemDetail (full-text stage)

`fetch_detail` returns an `ItemDetail` with the extracted body and a `content_status`:

| Status | Meaning |
|---|---|
| `accepted` | passed all full-text checks |
| `summary` | only a summary was available (body too short) |
| `title_only` | title-only fallback |
| `rejected` | failed validation (reason recorded) |

Validation reasons: `too_short`, `insufficient_structure`, `page_chrome`,
`title_or_summary`.

## Three invariants

1. **Strict success contract** — a response not matching the expected envelope raises or
   degrades to an empty capture with `schema_warning`; garbage rows never leak downstream.
2. **Evidence-backed heat** — heat is a real positive platform signal.
3. **Relevance is earned** — a hit survives only after relevance, full-text and ranking
   stages; arriving from the search endpoint alone is not enough.
