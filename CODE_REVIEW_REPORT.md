# generate_hot.py 全面代码审查报告

**审查日期**：2026-08-23
**文件**：`D:\AI\hotinfo\hot-info-new\generate_hot.py`（2197 行）
**审查依据**：全量阅读 + 13 个 API 实测探活 + 历史运行日志

---

## 一、程序主要功能模块与整体结构

程序是一个**多源热点聚合爬虫**，由 4 层 + 网络基础设施构成，由 `main()` 统一调度：

| 层 | 行范围 | 模块 | 作用 |
|---|---|---|---|
| 配置 | 17-65 | 常量/全局 | UA、超时、重试、博主列表、sec_uid 映射 |
| 网络基础 | 78-164 | `fetch`/`fetch_json`/`tikhub_request` | 直连 opener（绕系统代理）、gzip 解压、2 次重试 |
| 采集层 | 171-690 | 13 个 `scrape_*` 函数 | 百度/知乎/B站/头条/澎湃/华尔街/财联社/凤凰/贴吧/微博/抖音/公众号 |
| 博主追踪 | 691-1227 | 3 条降级路径 | signed(a_bogus) → pw(Playwright) → TikHub；B站用 curl_cffi |
| 后处理 | 1275-2150 | `main()` 主体 | 去重、救援旧数据、限 3 条、灵感生成、文案消毒、日期过滤、analysis 生成 |
| 输出 | 2112-2198 | 原子写 + 副产物 | data.json 原子写 → gen_js_data.py 重建 JS → 飞书通知 |

**运行模式**（`--local`/`--remote`/`--reprocess`）：CI 用 full、本地每日任务用 remote（只博主）、重跑后处理用 reprocess。10 分钟时间预算，超时跳过后续平台。

---

## 二、发现的问题清单

### P0 — 影响数据正确性，应立即修复

| # | 问题 | 位置 | 影响 | 修复建议 |
|---|---|---|---|---|
| 1 | **`_blogger_recency_key` 量纲混排** | 1866-1878 | create_time（epoch 秒 ~1.8e9）和 aweme_id（抖音 ~7.7e18）作为元组排序键混排，无 ct 的条目 aid 远大于有 ct 的，导致排序失真 | 改为 `aid or ct`（单一数值），与 `merge_fix_into_latest.py` 的 `sort_key` 同款 |
| 2 | **灵感 `generate_inspirations` 的无 key 保护依赖 `OUTPUT_FILE` 已存在** | 1398-1409 | reprocess 模式下 `all_articles` 从 data.json 加载，但 `generate_inspirations` 读 `OUTPUT_FILE` 取旧灵感时，若 data.json 被前序步骤清空则保护失效 | 保护逻辑改为优先用内存中的 `all_articles` 推断，或加 data.json 文件大小检查 |

### P1 — 潜在风险，应尽快修复

| # | 问题 | 位置 | 影响 | 修复建议 |
|---|---|---|---|---|
| 3 | **财联社 API 已迁移** | 406-456 | `cls.cn/v1/roll/get_roll_list` 返回缺 `data` 字段，实测 FAIL；代码已有 HTML 降级但正则 `<a href="/detail/\d+">` 依赖页面结构，cls 改版后会失效 | 更新 API 端点或改用 `cls.cn/v2/roll/get_roll_list`，并验证 HTML 降级正则 |
| 4 | **公众号 vvhan API 不稳定** | 590-623 | 实测 `RemoteDisconnected`，第三方免费 API 随时可能下线；降级路径用微博热搜冒充公众号，内容不匹配 | 更换为更稳定的公众号热点源（如搜狗微信热搜 API），或把降级标记为"微博精选"而非"公众号热点" |
| 5 | **`_fetch_weixin_api` 跳过 SSL 验证** | 603-605 | `ctx.verify_mode = ssl.CERT_NONE` 存在中间人风险（虽是免费第三方 API） | 至少加日志告警，或改用 `fetch_json` 统一路径（已有 gzip/重试） |
| 6 | **`scrape_ifeng` 正则脆弱** | 465 | `r'<a[^>]*href="([^"]*)"[^>]*title="([^"]*)"'` 依赖凤凰网 a 标签带 title 属性，若改版去掉 title 则全量失效 | 增加 JSON-LD 或 data 属性的备用解析路径 |
| 7 | **`scrape_weibo` 强依赖 Cookie** | 536-539 | 无 `WEIBO_COOKIE` 时 ajax 接口可能返回 302/空；实测当前可达但微博风控随时收紧 | 加无 Cookie 时的降级：用 `s.weibo.com/top/summary` HTML 抓取 |

### P2 — 代码质量/健壮性，可观察

| # | 问题 | 位置 | 说明 |
|---|---|---|---|
| 8 | **`douyin_score` 情绪词列表重复** | 1354 | `'离谱'` 出现两次，无害但冗余 |
| 9 | **`scrape_cls` HTML 降级正则未防 HTML 实体** | 440 | `title` 可能含 `&quot;`/`&amp;`，未 unescape |
| 10 | **`BlogSearcher` 类大量代码（691-800）未被使用** | 691-800 | `scrape_bloggers`（TikHub 路径）是最后降级路径，但 `BlogSearcher` 内的 TikHub 搜索/详情逻辑复杂且依赖 key，CI 无 key 时整体跳过 |
| 11 | **`main()` 的 `failed_sources` 初始化位置** | 1752 vs 1810 | 1752 行 `failed_sources = set()` 注释"始终初始化"，但 1810 行又重新赋值 `failed_sources = set()`，前者被覆盖——若 mode=="remote" 则 1752 的初始化是唯一生效的，逻辑分散易混淆 |
| 12 | ** Whisper 误识别修复表硬编码** | 1971-1988 | 30+ 条 `(误识别, 正确)` 映射写死在代码里，随 ASR 模型更新会失效或产生新误识别——应外置为 JSON 配置 |
| 13 | **`generate_blogger_analysis` 的 `publish_pattern` 判断** | 1308-1312 | 靠标题含"周更"/"月更"字眼判断，但博主标题几乎不会写这些词，实际全部判为"日更"，analysis 的这个字段无信息量 |
| 14 | **时间预算 `IMPORT_DEADLINE` 固定 600s** | 1662 | GitHub Actions free tier 默认 6 分钟超时（360s），若 CI runner 慢则 main 会被 Actions 强杀而非内部跳过 |

### 信息项（非问题，记录供参考）

- **抖音热榜 API 无签名直连**（567 行）：当前实测可达，但抖音随时可能加 a_bogus 校验，届时需走 `scrape_bloggers_signed` 同款签名
- **B站博主搜索 API**（295 行）：依赖 `curl_cffi` 模拟 TLS 指纹，CI 已安装此依赖（workflow 37 行）
- **飞书通知**（2145 行）：`feishu_notify` 失败被 `except: pass` 吞掉，通知断了不会有人知道

---

## 三、需要更新的部分

| 优先级 | 更新项 | 原因 | 当前状态 |
|---|---|---|---|
| P1 | 财联社 API 端点 | `v1/roll/get_roll_list` 已返回空 data，API 迁移到 v2 或新地址 | 实测 FAIL，靠 HTML 降级兜底 |
| P1 | 公众号热点源 | vvhan 第三方 API `RemoteDisconnected`，服务不稳 | 实测 FAIL，靠微博降级兜底 |
| P2 | Whisper 误识别表外置 | 硬编码 30+ 条修复，随 ASR 模型更新失效 | 当前生效但不可维护 |
| P2 | `douyin_score` 情绪词去重 | `'离谱'` 重复 | 无害 |
| 观察 | 抖音热榜是否需加签名 | 当前无签名直连可达 | 随时可能失效 |
| 观察 | GitHub Actions 超时对齐 | 时间预算 600s > Actions free 360s | 慢 runner 可能被强杀 |

---

## 四、程序当前运行状态整体结论

**程序整体运行正常，13 个新闻源中 11 个稳定可用，CI 每 3 小时自动触发产出 ~1300 条热点 + 42 条灵感，线上 rediancha.online 已验证数据正确。**

存在 2 个 P0（博主排序量纲混排、灵感保护依赖文件存在）和 5 个 P1（财联社/公众号 API 失效、SSL 跳过、凤凰正则脆弱、微博强依赖 Cookie），其中 P0-1 和 P1-3/P1-4 已在本轮维护中通过 `merge_fix_into_latest.py` 和 `inspiration_generator.py` 的保护逻辑间接缓解，但 `generate_hot.py` 本体的 `_blogger_recency_key` 量纲 bug 仍需直接修复。

**建议处理顺序**：P0-1（排序量纲）→ P1-3（财联社 API）→ P1-4（公众号源）→ P2-12（误识别表外置）。其余 P2 项可在下次维护窗口集中处理。
