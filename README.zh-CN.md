# China News Search Skill · 中文文档

> [English](README.md) · 中文

[![Skill](https://img.shields.io/badge/type-agent%20skill-blueviolet)](README.md)
[![Python](https://img.shields.io/badge/python-3.10%2B-yellow)](https://www.python.org/)
[![License](https://img.shields.io/badge/license-MIT-green)](LICENSE)
[![数据源](https://img.shields.io/badge/数据源-5%20个匿名源-orange)](#支持哪些平台)

**中文新闻关键词搜索 —— 带生产级相关性漏斗。**

按关键词搜索头条、掘金、网易、新浪新闻、澎湃，然后扩展查询词、抓正文、跨平台去重、按相似度 × 热度排序，最后过一遍 AI 审核。这是从生产级多源检索系统提炼出的**工程手册**——难点从来不是发请求，而是把一堆嘈杂的原始结果变成能用的文章列表。

**是 [china-hot-board-skill](https://github.com/gunjianpanxdd/china-hot-board-skill) 的姊妹篇。** 那个 skill 抓"当前最热"，这个 skill 找"关于某个关键词的文章"。所有数据源均为匿名公开端点，无需 Cookie。

## 为什么不只是"调一下搜索 API"

- **隐性限制都记下来了** —— 掘金匿名搜索静默封顶 20 条（所有分页参数被忽略）；头条 JSON 返回的是会话跳转链接，不是真实 URL。
- **阈值不会一刀切清空** —— "绝对下限 + 相对截断 + 保底 K 条"三件套。因为单个固定阈值曾把整个方向清空（实测 48 条 → 41 条低于下限 → 剩 0 条）。
- **相关性是筛出来的** —— 中文 bigram 重叠、正文校验、相似度排序、画像审核，一条结果要全部闯关才算数。
- **故障有剧本** —— 空结果 / 噪音 / 限流 / schema 漂移，每种都有诊断路径。

## 支持哪些平台

| 平台 | 端点 | 硬限制 / 坑 |
|---|---|---|
| 今日头条 | `so.toutiao.com/search/` | 会话链接需浏览器渲染；带 Cookie 反而空 |
| 掘金 | `api.juejin.cn/search_api/v1/search` | 只返回第一页 20 条；分页无效 |
| 网易新闻 | `www.163.com/search?keyword=` | DOM 从 `li` 改成 `div.keyword_new` |
| 新浪新闻 | `search.sina.com.cn/api/news` | 多种行结构；`list: null` 是合法空结果 |
| 澎湃新闻 | `api.thepaper.cn/search/web/news` | `contType==0`，跳过付费墙 |

百度**不是**通用搜索渠道（普通 `search()` 是空实现，context 模式易验证码）；知乎热榜等需登录的源不在范围内。

## 怎么用

### 第 1 步：安装

```bash
git clone https://github.com/gunjianpanxdd/china-news-search-skill.git
cp -r china-news-search-skill <你的项目>/.claude/skills/
# 或 .workbuddy/skills/ —— 目录名必须和 SKILL.md 的 name 字段一致
```

### 第 2 步：确认识别

重启会话后问一句「你有哪些 skill？」，能看到 `china-news-search-skill` 就装好了。

### 第 3 步：直接说人话

`description` 写好了触发词，下面这些都能命中：

```
# 按关键词搜
"帮我搜一下国内 AI 监管相关的新闻，多平台找"
"把这个话题扩展成 5 个搜索词，找相关文章"

# 排查
"为什么我搜掘金只出来 20 条"
"搜出来一堆不相关的，帮我过滤一下"

# 定规则
"新搜索源的热度阈值该怎么设"
```

**触发词规律**：句子里出现「搜新闻 / 关键词 / 多平台 / 过滤 / 去重 / 相关性 / 20 条 / 阈值」这类词，命中率最高。

### 显式引用 / slash

```
@skill:china-news-search-skill 帮我搜 XX 的新闻
/china-news-search-skill
```

## 6 阶段漏斗（核心）

```
关键词 → [扩展] → [逐平台搜] → [抓正文] → [去重] → [相似度×热度排序] → [AI审核] → 排序后的结果
```

每个阶段都有记录好的失败模式，详见 [SKILL.md](SKILL.md) 和 `references/ranking-and-filters.md`。

## 怎么用：校验脚本

`scripts/verify_search_parser.py` 可离线验证你写的解析器：把站点原始响存成文件，脚本检查能否解析出稳定 ID、非空热度、过相关性的条目。

```bash
# 校验解析器
python scripts/verify_search_parser.py --fixture resp.json --module my_parser.py --class MyParser

# 离线分诊：空/噪音/重复
python scripts/diagnose_search.py --fixture results.json
```

## 目录结构

```
china-news-search-skill/
├── SKILL.md                        # 触发词、6阶段漏斗、契约、参数、排障
├── README.md / README.zh-CN.md     # 门面
├── LICENSE                         # MIT
├── references/
│   ├── platform-search-catalog.md  # 5 平台：端点、参数、响应、限制
│   ├── keyword-expansion.md        # 一个话题 → 多个事件型查询词
│   ├── ranking-and-filters.md      # 相似度阈值、热度因子、审核规则
│   ├── troubleshooting.md          # 空/噪音/限流剧本
│   └── data-contract.md            # NewsHit / ProviderCapture / 校验
└── scripts/
    ├── verify_search_parser.py     # 离线解析校验
    └── diagnose_search.py          # 空/噪音/重复分诊
```

## 验证状态（如实说明）

已实测：`quick_validate` 结构校验通过、脚本 `py_compile` 通过、离线 fixture 冒烟测试通过。

**未做**：实网搜索 5 个平台的端到端测试（会触发站点限流，端点随时可能变）、装进具体 agent 后的自动触发测试。请在自己的环境验证这两项——端点是采集时的形态，站点改版是正常的。

## License

MIT — 见 [LICENSE](LICENSE)。

> 均为公开端点，请遵守各站点的服务条款与 robots 政策。遇到验证码降级为空并标记审查，不绕过。
