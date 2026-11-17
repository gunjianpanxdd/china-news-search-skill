# Keyword expansion

One topic should become several diverse, event-shaped query terms before searching. A
single broad keyword is the most common cause of noisy or empty results — this stage is
what turns "养娃" into concrete, searchable events.

## The production recipe

Given a user topic / direction, produce 5 diverse queries:

1. **Seed term first.** The original topic is always query #1. It anchors relevance and
   guarantees the search is about what the user asked.
2. **Recall signals (three sources), then fuse:**
   - seed term itself;
   - first-search feedback — search the seed once, take the top ~8 titles as vocabulary;
   - hot-board candidates — take the top ~20 current hot titles as trending context.
3. **LLM fusion.** Generate event-shaped keywords (a concrete happening, not an abstract
   concept), force the seed into first position, de-duplicate, cap at 5.
4. **Fallback** when LLM is unavailable: a rule-based expander with prefix/suffix affixes,
   capped at 12 terms per direction (e.g. `topic + 怎么做 / 案例 / 政策 / 新闻`).

## Guardrails

- **Generic-word blacklist.** Drop empty verbs/nouns that match everything:
  `处理 / 方法 / 调查 / 专利 / 新闻 / 怎么办 / 相关` … A query made of these returns noise.
- **Anchor check.** Every generated query must still relate to the seed term; drop ones
  that drifted. A query that passes the blacklist but loses the anchor is still bad.
- **Diversity over volume.** 5 distinct events beat 20 near-duplicate phrasings. Search
  volume for rate-limited sources (Juejin) comes from more *distinct* keywords.

## Persona-aware directions

When the search serves a specific account, generation can be steered by profile fields:

- Only a small set of fields are exposed as overrides (e.g. `core_persona`,
  `personal_advantage`, `desc`); an empty override falls back to the account value, and a
  disabled override is excluded from the prompt.
- `direction_plan` is an authoritative constraint (which directions to produce);
  `exclude_directions` lists what to avoid.
- Inject a few current hot titles as context so directions feel timely.

## Failure modes

| Symptom | Cause | Fix |
|---|---|---|
| All queries return the same articles | queries are paraphrases, not distinct events | enforce event-shaped diversity; de-dup by meaning, not string |
| Noise dominates | generic-word queries | apply the blacklist + anchor check |
| Too few hits on rate-limited source | too few keywords | expand via more distinct keywords (Juejin ignores pagination) |
| LLM expansion silently fails | reasoning consumed max_tokens / thinking not disabled | explicitly disable thinking, validate output, keep the rule-based fallback |
