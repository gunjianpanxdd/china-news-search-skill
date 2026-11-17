---
name: china-news-search-skill
description: Search Chinese news and articles by keyword across Toutiao, Juejin, NetEase, Sina News and The Paper, then filter, dedupe and rank results with a production-proven relevance funnel. This skill should be used when searching news by keyword, expanding a topic into multiple query terms, fetching article full text, filtering irrelevant or low-heat results, or diagnosing why a keyword search returned empty or noisy results. Keywords: 中文新闻搜索, keyword news search, 关键词搜新闻, Chinese article search, multi-source news retrieval, relevance ranking. All bundled sources work anonymously without login cookies. Pairs with china-hot-board-skill.
agent_created: true
---

# China News Search Skill

Search Chinese news by keyword across five public sources, then run a six-stage relevance
funnel — keyword expansion, per-platform search, full-text fetch, dedupe, similarity +
heat ranking, and AI review — to turn noisy raw hits into a ranked, usable article list.

## Overview

This skill captures the search playbook behind a production news-collection system. The
hard part is not issuing the request — it is everything after: each platform has a
different response shape and hidden limit, headlines need relevance checks, article bodies
need cleaning, and a naive threshold can silently wipe out an entire search direction.
It is engineering knowledge (workflows, endpoint behavior, ranking rules, failure
playbooks, verification scripts), **not** a running service. No scheduler, no database,
no LLM keys are bundled — those stay in the host application.

This is the companion to `china-hot-board-skill`. That skill captures *what is trending*;
this one finds *articles about a specific keyword*.

## When to use

Use this skill when a task involves any of:

- Searching Chinese news / articles by one or more keywords.
- Expanding a single topic into diverse, event-shaped query terms.
- Fetching and cleaning the full text behind a search-result link.
- Filtering search hits by relevance, heat, or account persona fit.
- Deduplicating results across platforms, or ranking them for downstream use.
- Diagnosing an empty / noisy / rate-limited keyword search.

## Workflow decision tree

| Goal | Path |
|---|---|
| Run a keyword search end to end | Follow "The 6-stage funnel" below |
| Expand a topic into query terms | `references/keyword-expansion.md` |
| Know a platform's endpoint / limit / response shape | `references/platform-search-catalog.md` |
| Set relevance / heat / review thresholds | `references/ranking-and-filters.md` |
| Diagnose empty or noisy results | `references/troubleshooting.md` + `scripts/diagnose_search.py` |
| Verify a parser against a saved response | `scripts/verify_search_parser.py` |

## The 6-stage funnel

This is the core asset. Each stage has a failure mode; do not skip stages.

1. **Expand the keyword.** One topic → several diverse, event-shaped queries (seed term
   first, generic words blacklisted, anchored to the original topic). See
   `references/keyword-expansion.md`. Failure mode: a single broad term returns noise.
2. **Search each platform.** Anonymous endpoints only; one adapter per site. Each has a
   different response family and hidden limit — see `references/platform-search-catalog.md`.
   Failure mode: pagination silently ignored, recommendations mixed into results.
3. **Fetch article full text.** Search results often give only a title + a redirect/session
   link. Resolve the real URL, then extract the body with a fallback chain
   (native selector → JSON-LD / `__NEXT_DATA__` → GeneralNewsExtractor → reject). Validate
   with the full-text check. Failure mode: session links with no real URL; body is nav chrome.
4. **Dedupe across platforms.** Canonicalize URLs (drop anchor/query/trailing slash),
   normalize titles, keep the higher-priority source on collision. Failure mode: the same
   article counted five times.
5. **Rank by similarity × heat.** Embed the query and titles, apply an absolute similarity
   floor **and** a relative top-K cutoff, multiply by a log-scaled heat factor. Always keep
   a small fallback when everything is filtered. See `references/ranking-and-filters.md`.
   Failure mode: a fixed threshold wipes out the whole direction.
6. **AI review against persona (optional).** Keep directly relevant and interpretable hits;
   drop pure sports scores / celebrity gossip / unrelated social news; when unsure, keep.
   Cap the review batch and keep a top-K fallback if parsing fails. Failure mode: a broken
   reviewer lets 60 irrelevant items through.

## The normalized contract (non-negotiable)

Every adapter returns a `ProviderCapture(raw_text, raw_suffix, items, metadata)`, where each
item is a frozen `NewsHit` (mirrors `HotItem` in the companion skill):
`item_id, platform, title, url, rank, heat, summary, publication_time, collected_at,
raw_payload`. Search hits that lack a native rank use `search_rank` derived from position.
See `references/data-contract.md`.

Three invariants:

1. **Strict success contract.** A response that does not match the expected envelope
   raises or degrades to an empty capture with `metadata["schema_warning"]` — never leak
   garbage rows. Known drift (e.g. a moved row path) degrades, unknown drift is flagged.
2. **Evidence-backed heat.** A hit's heat metric must be a real, positive signal from the
   platform (view / interaction / rank). No silent zeros, no invented numbers.
3. **Relevance is earned.** A hit survives only if it passes keyword-anchor or
   bigram-overlap relevance, full-text validation, and the ranking funnel — not merely
   because it came back from the search endpoint.

## Platform snapshot (all anonymous)

| Platform | Search endpoint | Hard limit / gotcha |
|---|---|---|
| Toutiao 头条 | `so.toutiao.com/search/` (JSON `dom` or `data[]`) | JSON DOM gives only session `/search/jump` links — real URLs need browser rendering; **no cookies** (cookie → empty) |
| Juejin 掘金 | `api.juejin.cn/search_api/v1/search` | **Only first page of 20**; all pagination params ignored; expand via more keywords |
| NetEase 网易 | `www.163.com/search?keyword=` | DOM changed `li.keyword_new_list` → `div.keyword_new`; no page_size |
| Sina 新浪 | `search.sina.com.cn/api/news?q=&page=` | Multiple row shapes; `list: null` is a valid empty |
| The Paper 澎湃 | `api.thepaper.cn/search/web/news` (POST) | `contType==0`, skip paywalled; `code!=0` degrades to empty |

Baidu is intentionally **not** a general search channel: its plain `search()` is empty and
its context mode is captcha-prone. Zhihu hot / signed-in sources are out of scope.

## Key parameters (production defaults)

| Parameter | Default | Meaning |
|---|---|---|
| `max_pages` | 3 | pages per keyword (10 hits each) |
| `min_impression` | 5000 | Toutiao view floor |
| `juejin_min_impression` | 2500 | Juejin heat floor (spike P50 ≈ 2234) |
| `min_interactions` | 200 | The Paper interaction floor |
| `sim_floor` / `keep_ratio` / `min_sim` | 0.40 / 0.6 / 0.45 | relative similarity cutoff |
| `llm_review_cap` / `fallback_keep` | 60 / 5 | review batch / safety net |

Thresholds are "absolute floor + relative cutoff + keep-K fallback" three-piece sets —
never a single fixed number. See `references/ranking-and-filters.md`.

## Diagnose a failure

- **Empty results** → check the response envelope shape first, then cookies (Toutiao
  returns empty *with* cookies), then anti-bot (silent rate limit needs backoff + circuit
  breaker).
- **Only 20 results from Juejin** → expected; pagination is ignored server-side. Use more
  keywords, not more pages.
- **Recommendations mixed in** → a keyword with no hits still returns fuzzy fallbacks;
  apply relevance + heat thresholds, don't trust row count.
- **Whole direction filtered out** → a hard threshold (e.g. `min_impression`) wiped it;
  enable the low-heat fallback pool. This actually happened in production.
- **Article body is navigation chrome** → widen selectors / add the new noise marker and
  re-run `validate_full_text`.
- **Captcha** → degrade to empty and flag for compliance review. Do not bypass.

## Scope boundary

Skill-ify: keyword expansion, per-platform search endpoints & response shapes, full-text
extraction, relevance/heat rules, dedupe & ranking, failure playbooks, verification scripts.
Do **not** skill-ify: Tavily/LLM API keys, scheduler, DB/upsert, vector-store hosting,
browser-renderer thread pools — these are runtime concerns of the host service.

## Resources

### scripts/
- `verify_search_parser.py` — check a saved response parses into stable, heated, relevant hits.
- `diagnose_search.py` — offline triage for empty / noisy / duplicated fixtures.

### references/
- `platform-search-catalog.md` — 5 platforms: endpoints, params, response families, limits.
- `keyword-expansion.md` — turn one topic into diverse event-shaped queries.
- `ranking-and-filters.md` — similarity thresholds, heat factors, review rules, parameters.
- `troubleshooting.md` — empty / noisy / rate-limited search playbook.
- `data-contract.md` — `NewsHit` / `ProviderCapture` / validation semantics.
