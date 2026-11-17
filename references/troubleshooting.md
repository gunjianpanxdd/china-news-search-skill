# Troubleshooting a keyword search

Symptom-first playbook. Always check the response envelope shape before anything else —
most "empty search" bugs are a parser mismatch, not a real absence of results.

## Empty results

Work down this order:

1. **Envelope shape drift** — dump `raw_text`, diff against `platform-search-catalog.md`.
   Check the guard (`err_no`/`code`/`status`) and row path first. A row list that moved
   (e.g. The Paper's `_ROW_PATHS`) looks exactly like "no results".
2. **Cookies** — Toutiao returns empty **with** cookies. Search must be anonymous.
3. **Anti-bot / silent rate limit** — consecutive searches get silently emptied. Detect a
   throttle page (tiny DOM + count=0 + no "no results" text), back off (~2s between queries,
   ~30s on retry), and circuit-break after 3 consecutive failures.
4. **Keyword problem** — a generic/over-long keyword. Apply blacklist + anchor check; for
   NetEase, shorten long queries but never below 3 chars (2-char substrings retrieve junk).
5. **Everything filtered downstream** — a hard heat/similarity threshold wiped the set.
   Check with `scripts/diagnose_search.py`; enable the keep-K fallback.

## Juejin returns exactly 20

Expected. Anonymous search ignores all pagination (`page_no/page/cursor/page_size`). Expand
via more *distinct* keywords. If the 20 look fuzzy/unrelated, they are recommendation
fallbacks for a no-hit keyword — apply the heat floor + review, don't trust the count.

## Recommendations mixed in as results

A no-hit keyword still returns fuzzy rows. Defenses:
- NetEase: return `[]` explicitly when the keyword card list is empty.
- Juejin: heat threshold + AI review.
- Any source: relevance check (keyword anchor / bigram overlap) before accepting a hit.

## Whole direction filtered out

A single hard threshold (e.g. `min_impression=5000`) removed every item — production hit
`seen=48 / below_min=41 / keep=0`. Fix: keep a low-heat fallback pool (top 5 by score) so a
direction never goes fully empty. See `ranking-and-filters.md`.

## Article body is navigation chrome

- Widen selectors or add the new noise marker, then re-run full-text validation.
- Respect GNE fallback min length (200 chars vs 80 for native).
- Check `content_status` reasons: `too_short`, `insufficient_structure`, `page_chrome`,
  `title_or_summary`.

## Captcha / login wall

Degrade to an empty capture and flag the source for compliance review. Do **not** attempt
to bypass. Baidu's context mode is especially captcha-prone, which is why Baidu is not a
general search channel here.

## Schema drift

- Unknown envelope → empty capture with `metadata["schema_warning"]`, not a crash.
- Known drift (moved row path, changed DOM `li` → `div`) → handle both forms in the parser.
- Never treat a parse failure as "zero results" in logs — surface it as a warning.

## LLM reviewer fails or rejects everything

- Parsing failure → fall back to top-5 by similarity.
- All rejected → keep top-5. Never let a broken reviewer pass the whole batch through.

## Rate-limit / performance

- Back off between keywords and pages; circuit-break on repeated failure.
- Keep the browser renderer bounded (semaphore, shared loop) and swallow its exceptions
  into a typed "renderer unavailable" signal.
- Don't cache empty results (a transient empty window should be retryable).
