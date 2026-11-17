# Platform search catalog

Five anonymous Chinese news sources with the exact search endpoint, parameters, response
family, parser strategy, hard limit and heat signals — observed in a production multi-source
search system. Use this when adding a source, writing a search parser, or diagnosing a
search that went empty / noisy.

**Scope:** these are keyword-search endpoints (find articles about a query), distinct from
the hot-board endpoints (what is trending) in `china-hot-board-skill`. All work without
login cookies. Baidu and Zhihu are deliberately excluded — see the last section.

## Toutiao 今日头条

- **Search endpoint:** `GET https://so.toutiao.com/search/`
- **Params:** `keyword`, `pd=information`, `source=search_subtab_switch`, `from=information`,
  `format=json`, `count`, `offset`. Production uses `count=30` on the browser-render path
  and `count=10` + `offset=page*10` on the JSON path.
- **Response family:** JSON object with two shapes.
  - `dom`: `dom` is an HTML string and `count` an int — parse with an HTML parser.
    `count==0` plus a non-empty DOM is a contract violation.
  - `data`: a legacy `data[]` list — map rows directly.
- **Row fields:** `title`, `url`, `source`, `publish_time`, `read_count` / `view_count`,
  `abstract`. Filter rows older than `collected_at - 24h`.
- **Heat metrics:** `views` / `reads` (+ comments into engagement); `search_rank` fallback.
- **Hard gotcha:** the JSON API's DOM contains only session `/search/jump` links — no real
  article URL. Real URLs require browser rendering (Playwright) of the search page.
- **Anti-bot:** **do not send cookies** — an authenticated request returns empty. Silent
  rate limiting after consecutive searches: back off ~2s between keywords/pages, ~30s on
  retry, and circuit-break a direction after 3 consecutive keyword failures. Detect a
  captcha/throttle page by a tiny DOM (<5000 chars) with `count==0` and no "no results" text.
- **Full text:** resolve real URL, then article page; fallback to a bounded browser renderer
  when plain fetch is too short. Clean nav chrome before `validate_full_text`.

## Juejin 掘金

- **Search endpoint:** `POST https://api.juejin.cn/search_api/v1/search`
- **Body:** `{"key_word": keyword, "id_type": 0, "page_no": page, "page_size": 20}`
- **Response family:** JSON, guard `err_no == 0`; rows at `data[]`, with the article nested
  one level deeper at `data[].result_model.article_info`.
- **Row fields:** `article_id` / `content_id`, `title`, `brief`, `ctime`, `hot_rank` /
  `hot_index`, counters `view_count / digg_count / comment_count / collect_count`.
- **Heat metrics:** `hot_rank` primary; engagement = views + likes + collects + comments.
- **Hard limit (spike-tested):** anonymous search returns **only the first page of 20**.
  `page_no`, `page`, `cursor`, `search_after`, `page_size` are all ignored server-side;
  `page_size` is always 20. **Expand volume via more keywords, not pagination.**
- **Gotcha:** a keyword with no real hits still returns 20 fuzzy "recommendation" rows.
  Never trust row count — apply relevance + heat thresholds (production `juejin_min_impression=2500`,
  spike P50 ≈ 2234) and an AI review pass.

## NetEase 网易新闻

- **Search endpoint:** `GET https://www.163.com/search?keyword=<kw>`. No `page_size` param.
- **Response family:** HTML search page. Parse with an `HTMLParser` subclass that tracks
  card boundaries.
- **Row fields:** article URL (must match a `/dy/article/<docid>.html` pattern), title,
  snippet. De-duplicate by `docid`. Only one native heat signal: comments.
- **DOM drift:** the card markup changed from `li.keyword_new_list` (legacy/fixtures) to
  `div.keyword_new` containing `h3` (live). A state-machine parser handling both forms is
  required; anchor on the `/dy/article/` URL regex as a conservative fallback.
- **Gotcha:** empty keyword card lists must return `[]` explicitly — otherwise recommendation
  blocks get mistaken for search results.
- **Full text:** selectors `.post_body`, `#endText`, `.post_text` → GNE fallback → validate.

## Sina News 新浪新闻

- **Search endpoint:** `GET https://search.sina.com.cn/api/news?q=<kw>&page=<n>`
- **Response family:** JSON, rows may be under `result.data`, top-level `data`, or
  `data.list | data | items` — support all shapes. `list: null` is a valid empty result.
- **Row fields:** `title`, `url`, `top_num`, `create_date`, `media`, `commentid`. Keep only
  `docType == "news"`.
- **Heat metrics:** `top_num` + comments. Comments endpoint:
  `GET https://comment5.news.sina.com.cn/page/info?channel=<c>&newsid=<id>`.
- **Full text:** selectors `#artibody`, `#article-content`, `.article-content` → GNE →
  validate. Clean tail markers (特别声明 / 版权所有 / 责任编辑 …) and exact noise rows.

## The Paper 澎湃新闻

- **Search endpoint:** `POST https://api.thepaper.cn/search/web/news`, header `client-type: 1`
- **Body:** `{"word": keyword, "orderType": 3, "pageNum": n, "pageSize": 15, "searchType": 1}`
- **Response family:** JSON. Select rows where `contType == 0`, skip `paywalled == true`,
  require an internal URL path or a `contId`.
- **Row fields:** `contId`, `name`, `summary`, `interactionNum`, `praiseTimes`, `pubTimeLong`.
- **Heat metrics:** `interaction_num` (floor 1) + `praise_times` (floor 10).
- **Drift policy:** `code != 0` degrades to an empty capture, not a hard failure; emit a
  `schema_warning` in metadata. Envelope/row paths have moved historically — probe several.
- **Full text:** `__NEXT_DATA__` `articleBody` → DOM selectors → GNE, each through
  `validate_full_text`.

## Deliberately excluded

| Source | Why not a general search channel |
|---|---|
| Baidu 百度 | Plain `search()` is an empty implementation; the real path is a context mode that pairs a hot-board parent event with search cards, and it is captcha-prone. Not wired as a search channel. |
| Zhihu 知乎 | Hot-board/search requires cookies — out of the anonymous scope. |
| Tavily / general web | A different stack (paid API, whole-web). This catalog is for the five anonymous Chinese news sources above. |

## Adding a sixth source

Implement the same adapter interface as the others: `search(keyword, page, page_size,
collected_at) -> ProviderCapture`. Fill in: endpoint, envelope guard, row path, stable
`item_id`, heat fields, full-text selectors, noise constants, and drift behavior. Then
verify with `scripts/verify_search_parser.py` against a saved response. Keep the relevance
and full-text invariants — a new source that bypasses them pollutes the whole funnel.
