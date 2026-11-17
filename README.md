# China News Search Skill

> English · [中文文档](README.zh-CN.md)

[![Skill](https://img.shields.io/badge/type-agent%20skill-blueviolet)](README.zh-CN.md)
[![Python](https://img.shields.io/badge/python-3.10%2B-yellow)](https://www.python.org/)
[![License](https://img.shields.io/badge/license-MIT-green)](LICENSE)
[![Sources](https://img.shields.io/badge/sources-5%20anonymous-orange)](#supported-sources)

**Keyword news search across Chinese platforms — with a production-proven relevance funnel.**

Search Toutiao, Juejin, NetEase, Sina News and The Paper by keyword, then expand the query,
fetch article full text, dedupe, and rank by similarity × heat with an AI review pass.
This is the engineering playbook distilled from a production multi-source search system —
the part that matters is not the request, it is the six-stage funnel that turns noisy raw
hits into a usable article list.

**Companion to [china-hot-board-skill](https://github.com/gunjianpanxdd/china-hot-board-skill).**
That skill captures *what is trending right now*; this one finds *articles about a specific
keyword*. All bundled sources are anonymous — no login cookies.

## Why this is not just "call the search API"

- **Hidden limits are documented** — Juejin silently caps anonymous search at 20 (all
  pagination params ignored); Toutiao's JSON links are session redirects, not real URLs.
- **Thresholds that don't nuke everything** — "absolute floor + relative cutoff + keep-K
  fallback" three-piece sets, because a single fixed threshold once wiped an entire search
  direction (48 seen → 41 below floor → 0 kept, in production).
- **Relevance is earned** — CJK bigram overlap, full-text validation, similarity ranking,
  persona review — a hit must survive all of them.
- **Failure playbooks** — empty / noisy / rate-limited / schema-drift, each with a diagnosis.

## Supported sources

| Platform | Endpoint | Hard limit / gotcha |
|---|---|---|
| Toutiao 头条 | `so.toutiao.com/search/` | session links need browser render; no cookies |
| Juejin 掘金 | `api.juejin.cn/search_api/v1/search` | first page of 20 only; pagination ignored |
| NetEase 网易 | `www.163.com/search?keyword=` | DOM changed `li` → `div.keyword_new` |
| Sina 新浪 | `search.sina.com.cn/api/news` | multiple row shapes; `list: null` valid |
| The Paper 澎湃 | `api.thepaper.cn/search/web/news` | `contType==0`, skip paywalled |

## Install

```bash
git clone https://github.com/gunjianpanxdd/china-news-search-skill.git
cp -r china-news-search-skill <your-project>/.claude/skills/
# or: .workbuddy/skills/ — the folder name must match the SKILL.md `name` field
```

## Usage

Ask naturally — the `description` triggers the skill:

- "Search news about AI regulation in China across multiple platforms."
- "Expand this topic into 5 search keywords and find relevant articles."
- "Why did my Juejin search only return 20 results?"
- "The search came back with a lot of irrelevant hits, help me filter them."
- "How should I set the heat threshold for a new search source?"

Or invoke explicitly: `/china-news-search-skill`

## The 6-stage funnel

```
keyword → [expand] → [per-platform search] → [full text] → [dedupe] → [similarity×heat rank] → [AI review] → ranked hits
```

Each stage has a documented failure mode. See [SKILL.md](SKILL.md) and
`references/ranking-and-filters.md`.

## What's inside

```
china-news-search-skill/
├── SKILL.md                       # triggers, 6-stage funnel, contract, parameters, diagnosis
├── README.md / README.zh-CN.md    # this page
├── LICENSE                        # MIT
├── references/
│   ├── platform-search-catalog.md # 5 platforms: endpoints, params, shapes, limits
│   ├── keyword-expansion.md       # one topic → diverse event-shaped queries
│   ├── ranking-and-filters.md     # similarity thresholds, heat factor, review rules
│   ├── troubleshooting.md         # empty / noisy / rate-limited playbook
│   └── data-contract.md           # NewsHit / ProviderCapture / validation
└── scripts/
    ├── verify_search_parser.py    # offline parser check against a saved response
    └── diagnose_search.py         # offline triage for empty / noisy / duplicate fixtures
```

## License

MIT — see [LICENSE](LICENSE).

> These are public endpoints. Respect each site's terms of use and robots policy. Captcha
> walls degrade to empty and are flagged for review — never bypassed.
