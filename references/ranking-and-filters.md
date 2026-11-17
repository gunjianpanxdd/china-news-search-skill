# Ranking and filters

After search + full-text + dedupe, results pass a ranking funnel. The governing principle:
**absolute floor + relative cutoff + keep-K fallback** — never a single fixed threshold.

## Why the three-piece set

BGE-M3 cosine similarity has a high baseline (~0.55–0.84), so a fixed cutoff like 0.8 is
meaningless — it either keeps everything or wipes everything. And a hard heat floor once
wiped an entire direction in production (48 seen → 41 below floor → 0 kept). Hence:

- **Absolute similarity floor:** a minimum below which a hit is definitely irrelevant.
- **Relative cutoff:** keep the top fraction by score, whatever the absolute values are.
- **Keep-K fallback:** if everything is filtered, still return the best K hits.

## Production defaults

| Parameter | Default | Role |
|---|---|---|
| `max_pages` | 3 | pages per keyword (10 hits each) |
| `min_impression` | 5000 | Toutiao view floor |
| `juejin_min_impression` | 2500 | Juejin heat floor (spike P50 ≈ 2234) |
| `min_interactions` | 200 | The Paper interaction floor |
| `sim_filter_threshold` | 0.40 | compatibility lower bound |
| `keep_ratio` | 0.6 | keep top 60% by rank score |
| `min_sim` | 0.45 | effective floor = `max(min_sim, sim_filter_threshold)` |
| `fallback_keep` | 2 (ranking) | keep top 2 if all filtered |
| `llm_review_cap` | 60 | max items sent to AI review |
| `llm_fallback_keep` | 5 | keep top 5 if reviewer fails |

Other sources (NetEase, Sina) are not heat-filtered by default; an `unfiltered_channel_limit`
caps their contribution (0 = unlimited in manual requests, 3 in account defaults).

## Similarity × heat ranking

1. Embed the query and hit titles (use only the first ~8 query terms to avoid dilution).
2. Cosine similarity between query and title.
3. Effective floor = `max(min_sim, sim_filter_threshold)`; drop hits below it.
4. Relative cutoff: keep top `keep_ratio` fraction by a rank score; if that empties the
   set, restore the top `fallback_keep`.
5. Heat factor = `log(view) / log(100001)` (bounded, smooths outliers).
6. Final score = `similarity × heat factor`; sort descending.

## Relevance primitives

- **CJK bigram overlap** (used for event relevance): NFKC + casefold + strip whitespace,
  build CJK bigram sets; a short event (≤4 chars) contained in the candidate → relevant;
  bigram intersection ≥2 **and** overlap/min(len) ≥ 0.25 → relevant; shared alphanumeric
  token (len ≥3) → relevant.
- **Full-text validation:** native body ≥80 chars (GNE fallback ≥200), ≥2 paragraphs or
  ≥3 sentences, page-chrome hits <4 — otherwise `rejected` / `summary` / `title_only`.
- **Search evidence:** a hit's heat must come from a real positive signal (rank / views /
  interactions); no silent zeros.

## AI review (optional, persona-aware)

- Keep: directly relevant hits; tangentially related but interpretable hits.
- Drop: pure sports scores, celebrity gossip, unrelated social news.
- When unsure → keep (the cost of dropping a good item is higher).
- Cap the batch (`llm_review_cap`). **If parsing fails or everything is rejected, keep the
  top `llm_fallback_keep` by similarity** — a broken reviewer once let 60 irrelevant items
  through, and the opposite failure (reviewer rejects all) is equally damaging.

## Dedupe before ranking

Canonicalize URL (drop anchor / query / trailing slash), normalize title, and on collision
keep the higher-priority source. Channel priority (high→low): Toutiao → Juejin → NetEase →
Sina → The Paper.

## Failure modes

| Symptom | Cause | Fix |
|---|---|---|
| Whole direction empty | hard heat floor wiped it | enable low-heat fallback pool |
| Everything kept | fixed similarity threshold too low | add relative top-K cutoff |
| Nothing kept | fixed threshold too high | use relative cutoff + keep-K fallback |
| Same article N times | no cross-platform dedupe | canonicalize URL + normalize title |
| Irrelevant hits survive | reviewer skipped / parsing failed | enforce fallback keep + anchor check |
