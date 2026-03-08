#!/usr/bin/env python3
"""
Fetch issues from ruanyf/weekly GitHub repository.
Supports pagination, incremental updates, and two-level categorization.
"""

import json
import os
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode

# Configuration
REPO = "ruanyf/weekly"
API_BASE = f"https://api.github.com/repos/{REPO}/issues"
SINCE_DATE = "2024-01-01T00:00:00Z"
PER_PAGE = 100
DATA_DIR = Path(__file__).resolve().parent.parent / "data"
STATE_FILE = DATA_DIR / ".fetch_state.json"

# ===== Level-1 Category: title prefix matching =====
CATEGORY_PATTERNS = [
    (r"[\[【].*?开源.*?自荐.*?[\]】]", "开源项目"),
    (r"[\[【].*?工具.*?自荐.*?[\]】]", "工具/产品"),
    (r"[\[【].*?产品.*?自荐.*?[\]】]", "工具/产品"),
    (r"[\[【].*?项目.*?自荐.*?[\]】]", "开源项目"),  # 项目自荐 -> 开源项目
    (r"[\[【].*?文章.*?自荐.*?[\]】]", "投稿推荐"),  # 文章自荐
    (r"[\[【].*?资源.*?推荐.*?[\]】]", "投稿推荐"),  # 资源推荐
    (r"[\[【].*?(?:投稿|推荐).*?[\]】]", "投稿推荐"),
    (r"[\[【].*?自荐.*?[\]】]", "开源项目"),  # generic 自荐 -> 开源项目
]
DEFAULT_CATEGORY = "讨论/反馈"

# Category metadata for frontend
CATEGORY_META = {
    "开源项目": {"color": "#58a6ff", "icon": "📦"},
    "工具/产品": {"color": "#f0883e", "icon": "🔧"},
    "投稿推荐": {"color": "#d29922", "icon": "📮"},
    "讨论/反馈": {"color": "#8b949e", "icon": "💬"},
}

# ===== Level-2 Subcategory: body keyword matching =====
# Order matters — first match wins. Keywords are matched case-insensitively.
SUBCATEGORY_RULES = [
    {
        "name": "AI/LLM",
        "icon": "🤖",
        "color": "#da3633",
        "keywords": [
            r"(?<![a-zA-Z])AI(?![a-zA-Z])", r"LLM", r"大模型", r"GPT", r"Claude",
            r"(?<![a-zA-Z])Agent(?![a-zA-Z])", r"机器学习", r"深度学习", r"(?<![a-zA-Z])ML(?![a-zA-Z])", r"自然语言",
            r"NLP", r"神经网络", r"transformer", r"RAG", r"向量数据库",
            r"embedding", r"diffusion", r"stable.?diffusion", r"midjourney",
            r"copilot", r"chatbot", r"聊天机器人", r"智能体", r"大语言",
            r"ollama", r"langchain", r"openai", r"gemini", r"(?<![a-zA-Z])bert(?![a-zA-Z])",
            r"text.to.image", r"文生图", r"语音合成", r"TTS", r"ASR",
            r"OCR", r"计算机视觉", r"computer.vision",
        ],
    },
    {
        "name": "前端/Web",
        "icon": "🌐",
        "color": "#1f6feb",
        "keywords": [
            r"\bReact\b", r"\bVue\b", r"\bSvelte\b", r"\bAngular\b",
            r"\bCSS\b", r"前端", r"浏览器", r"\bWeb\b", r"\bHTML\b",
            r"\bJavaScript\b", r"\bTypeScript\b", r"\bJS\b", r"\bTS\b",
            r"\bNode\.?js\b", r"\bDeno\b", r"\bBun\b", r"\bNext\.?js\b",
            r"\bNuxt\b", r"\bVite\b", r"\bWebpack\b", r"\bTailwind\b",
            r"UI.组件", r"组件库", r"responsive", r"响应式", r"\bDOM\b",
            r"\bSPA\b", r"\bPWA\b", r"\bSSR\b", r"\bSSG\b", r"静态站点",
            r"landing.page", r"网页", r"博客", r"主题",
        ],
    },
    {
        "name": "后端/服务",
        "icon": "⚙️",
        "color": "#238636",
        "keywords": [
            r"(?<![a-zA-Z])API(?![a-zA-Z])", r"后端", r"服务器", r"数据库", r"微服务",
            r"Docker", r"K8s", r"Kubernetes", r"Redis",
            r"MySQL", r"Postgres", r"MongoDB", r"(?<![a-zA-Z])SQL(?![a-zA-Z])",
            r"(?<![a-zA-Z])Go(?:lang)?(?![a-zA-Z])", r"(?<![a-zA-Z])Rust(?![a-zA-Z])", r"(?<![a-zA-Z])Java(?!Script)",
            r"(?<![a-zA-Z])Python(?![a-zA-Z])", r"(?<![a-zA-Z])Ruby(?![a-zA-Z])", r"(?<![a-zA-Z])PHP(?![a-zA-Z])",
            r"GraphQL", r"(?<![a-zA-Z])REST(?![a-zA-Z])", r"gRPC", r"消息队列",
            r"Kafka", r"RabbitMQ", r"中间件", r"网关",
            r"负载均衡", r"缓存", r"分布式", r"(?<![a-zA-Z])ORM(?![a-zA-Z])",
        ],
    },
    {
        "name": "DevOps/效率",
        "icon": "🔨",
        "color": "#bf8700",
        "keywords": [
            r"CI/?CD", r"部署", r"自动化", r"(?<![a-zA-Z])CLI(?![a-zA-Z])", r"终端",
            r"效率工具", r"命令行", r"(?<![a-zA-Z])Git(?!Hub)(?![a-zA-Z])", r"脚手架",
            r"terraform", r"ansible", r"监控", r"日志",
            r"运维", r"DevOps", r"容器", r"编排", r"pipeline",
            r"workflow", r"cron", r"定时任务", r"shell", r"(?<![a-zA-Z])bash(?![a-zA-Z])",
            r"开发工具", r"开发者工具", r"生产力", r"提效",
            r"脚本", r"Makefile", r"dotfiles", r"配置管理",
        ],
    },
    {
        "name": "移动端",
        "icon": "📱",
        "color": "#a371f7",
        "keywords": [
            r"\biOS\b", r"\bAndroid\b", r"小程序", r"\bFlutter\b",
            r"React.Native", r"\bSwift\b", r"\bKotlin\b", r"移动端",
            r"移动应用", r"\bApp\b", r"手机", r"客户端",
            r"\bTaro\b", r"uni.?app", r"跨平台", r"原生",
            r"\bAPK\b", r"\bIPA\b", r"应用商店",
        ],
    },
    {
        "name": "数据/可视化",
        "icon": "📊",
        "color": "#3fb950",
        "keywords": [
            r"数据分析", r"图表", r"可视化", r"\bBI\b", r"报表",
            r"\bEcharts\b", r"\bD3\b", r"dashboard", r"仪表盘",
            r"统计", r"大数据", r"\bETL\b", r"数据仓库",
            r"\bExcel\b", r"电子表格", r"数据集",
            r"爬虫", r"抓取", r"scrape", r"crawl",
        ],
    },
    {
        "name": "设计/创意",
        "icon": "🎨",
        "color": "#f778ba",
        "keywords": [
            r"UI设计", r"UX设计", r"图片", r"视频",
            r"音频", r"\b3D\b", r"动画", r"插画", r"图标",
            r"配色", r"字体", r"\bSVG\b", r"素材", r"壁纸",
            r"截图", r"录屏", r"编辑器", r"画板", r"原型",
            r"\bFigma\b", r"Sketch", r"海报", r"封面",
            r"音乐", r"播客", r"podcast", r"creative",
        ],
    },
    {
        "name": "安全/隐私",
        "icon": "🔒",
        "color": "#f85149",
        "keywords": [
            r"网络安全", r"加密", r"隐私", r"\bVPN\b", r"代理",
            r"\bproxy\b", r"防火墙", r"漏洞", r"渗透",
            r"密码管理", r"认证", r"\bSSL\b", r"\bTLS\b", r"证书",
            r"\bSSH\b", r"端到端", r"zero.knowledge", r"零知识",
            r"沙箱", r"隔离", r"审计", r"合规",
        ],
    },
    {
        "name": "学习/教程",
        "icon": "📚",
        "color": "#79c0ff",
        "keywords": [
            r"教程", r"学习", r"入门", r"指南", r"文档",
            r"面试", r"算法", r"刷题", r"\bLeetCode\b", r"课程",
            r"电子书", r"书籍", r"知识库", r"笔记", r"博客",
            r"wiki", r"手册", r"cheatsheet", r"速查",
            r"roadmap", r"路线图", r"教学", r"培训",
        ],
    },
]
DEFAULT_SUBCATEGORY = "其他"
DEFAULT_SUBCATEGORY_META = {"icon": "📌", "color": "#8b949e"}


def get_headers():
    """Build request headers, optionally with auth token."""
    headers = {
        "Accept": "application/vnd.github.v3+json",
        "User-Agent": "ruanyf-weekly-issue-browser/1.0",
    }
    token = os.environ.get("GITHUB_TOKEN")
    if token:
        headers["Authorization"] = f"token {token}"
        print("✓ Using GITHUB_TOKEN for authentication (5000 req/hr)")
    else:
        print("⚠ No GITHUB_TOKEN set, using unauthenticated access (60 req/hr)")
    return headers


def categorize_title(title: str) -> str:
    """Level-1 category: match issue title prefix."""
    for pattern, category in CATEGORY_PATTERNS:
        if re.search(pattern, title):
            return category
    return DEFAULT_CATEGORY


def categorize_body(title: str, body: str) -> str:
    """Level-2 subcategory: match keywords in title + body."""
    text = (title + " " + (body or "")).lower()
    for rule in SUBCATEGORY_RULES:
        for kw in rule["keywords"]:
            if re.search(kw, text, re.IGNORECASE):
                return rule["name"]
    return DEFAULT_SUBCATEGORY


def clean_body(body: str | None, max_len: int = 500) -> str:
    """Truncate and clean issue body text."""
    if not body:
        return ""
    # Remove images to save space
    body = re.sub(r'!\[.*?\]\(.*?\)', '[图片]', body)
    # Remove HTML tags
    body = re.sub(r'<[^>]+>', '', body)
    # Collapse whitespace
    body = re.sub(r'\s+', ' ', body).strip()
    if len(body) > max_len:
        body = body[:max_len] + "…"
    return body


def get_year_month(date_str: str) -> str:
    """Extract YYYY-MM from ISO date string."""
    return date_str[:7]


def fetch_page(page: int, headers: dict) -> tuple[list, dict]:
    """Fetch a single page of issues. Returns (issues_list, response_headers)."""
    # Don't use 'since' param - it filters by updated_at, not created_at
    # We'll filter by created_at locally after fetching all issues
    params = urlencode({
        "state": "open",
        "per_page": PER_PAGE,
        "page": page,
        "sort": "created",
        "direction": "desc",
    })
    url = f"{API_BASE}?{params}"
    req = Request(url, headers=headers)

    try:
        resp = urlopen(req, timeout=30)
        data = json.loads(resp.read().decode("utf-8"))
        resp_headers = {k.lower(): v for k, v in resp.headers.items()}
        return data, resp_headers
    except HTTPError as e:
        if e.code == 403:
            reset_time = int(e.headers.get("X-RateLimit-Reset", 0))
            if reset_time:
                wait = max(reset_time - int(time.time()), 1)
                print(f"\n⏳ Rate limited. Waiting {wait}s until reset...")
                time.sleep(wait + 1)
                return fetch_page(page, headers)
            raise
        elif e.code == 422:
            print(f"\n⚠ GitHub API returned 422 for page {page}, skipping...")
            return [], {}
        else:
            raise


def check_rate_limit(resp_headers: dict):
    """Check and display rate limit status."""
    remaining = resp_headers.get("x-ratelimit-remaining", "?")
    limit = resp_headers.get("x-ratelimit-limit", "?")
    return remaining, limit


def load_state() -> dict:
    """Load fetch state (last run time, existing issues)."""
    if STATE_FILE.exists():
        with open(STATE_FILE, "r") as f:
            return json.load(f)
    return {"last_fetch": SINCE_DATE, "total_fetched": 0}


def save_state(state: dict):
    """Save fetch state."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with open(STATE_FILE, "w") as f:
        json.dump(state, f, indent=2)


def fetch_all_issues():
    """Main fetch logic - always fetch all open issues, then filter by SINCE_DATE."""
    headers = get_headers()

    # Parse SINCE_DATE for local filtering
    since_dt = datetime.fromisoformat(SINCE_DATE.replace("Z", "+00:00"))
    fetch_start = datetime.now(timezone.utc).isoformat()

    print(f"\n📡 Fetching issues from ruanyf/weekly")
    print(f"   Filtering by created_at >= {SINCE_DATE}")
    print(f"   Fetching all open issues...")
    print()

    all_issues_dict = {}  # Use dict to dedupe by issue number
    page = 1

    while True:
        sys.stdout.write(f"\r   Fetching page {page}...")
        sys.stdout.flush()

        issues_data, resp_headers = fetch_page(page, headers)

        if not issues_data:
            break

        # Filter out pull requests (GitHub API returns PRs as issues too)
        issues_data = [i for i in issues_data if "pull_request" not in i]

        for raw in issues_data:
            # Filter by created_at locally
            created_at = raw.get("created_at", "")
            if created_at:
                try:
                    issue_dt = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
                    if issue_dt < since_dt:
                        # Issue is before SINCE_DATE, skip it
                        continue
                except ValueError:
                    pass

            raw_body = raw.get("body") or ""
            category = categorize_title(raw["title"])
            subcategory = categorize_body(raw["title"], raw_body)

            issue = {
                "number": raw["number"],
                "title": raw["title"],
                "body": clean_body(raw_body),
                "created_at": raw["created_at"],
                "updated_at": raw["updated_at"],
                "user": {
                    "login": raw["user"]["login"],
                    "avatar_url": raw["user"]["avatar_url"],
                },
                "html_url": raw["html_url"],
                "labels": [l["name"] for l in raw.get("labels", [])],
                "reactions": raw.get("reactions", {}).get("total_count", 0),
                "comments": raw.get("comments", 0),
                "category": category,
                "subcategory": subcategory,
                "year_month": get_year_month(raw["created_at"]),
                "featured": "weekly" in [l["name"] for l in raw.get("labels", [])],
            }

            # Use dict to dedupe (same issue may appear in multiple pages)
            all_issues_dict[issue["number"]] = issue

        remaining, limit = check_rate_limit(resp_headers)
        sys.stdout.write(f"\r   Page {page}: {len(issues_data)} issues (API: {remaining}/{limit} remaining)   \n")

        # Check if we've reached issues before SINCE_DATE
        # Since we sort by created_at desc, once we see an old issue, we can stop
        if issues_data:
            last_created = issues_data[-1].get("created_at", "")
            if last_created:
                try:
                    last_dt = datetime.fromisoformat(last_created.replace("Z", "+00:00"))
                    if last_dt < since_dt:
                        print(f"\n   Reached issues before {SINCE_DATE}, stopping...")
                        break
                except ValueError:
                    pass

        if len(issues_data) < PER_PAGE:
            break

        page += 1
        time.sleep(0.5)

    # Convert to list
    all_issues = list(all_issues_dict.values())
    print(f"\n✅ Fetch complete: {len(all_issues)} open issues (created_at >= {SINCE_DATE})")

    # Sort by created_at descending
    all_issues = sorted(all_issues, key=lambda x: x["created_at"], reverse=True)

    # Build indices
    categories = build_category_index(all_issues)
    monthly = build_monthly_index(all_issues)
    stats = build_stats(all_issues)

    # Write output files
    write_output(all_issues, categories, monthly, stats)

    # Save state
    state = {"last_fetch": fetch_start, "total_fetched": len(all_issues)}
    save_state(state)

    print(f"\n📁 Output written to {DATA_DIR}/")
    print(f"   issues.json:     {len(all_issues)} issues")
    print(f"   categories.json: {len(categories)} categories")
    print(f"   monthly.json:    {len(monthly)} months")


def build_category_index(issues: list) -> dict:
    """Build category -> subcategory -> issue numbers index."""
    cats = {}
    for issue in issues:
        cat = issue["category"]
        subcat = issue["subcategory"]
        if cat not in cats:
            cats[cat] = {
                "name": cat,
                "count": 0,
                "color": CATEGORY_META.get(cat, {}).get("color", "#8b949e"),
                "icon": CATEGORY_META.get(cat, {}).get("icon", "📌"),
                "subcategories": {},
                "issues": [],
            }
        cats[cat]["count"] += 1
        cats[cat]["issues"].append(issue["number"])

        if subcat not in cats[cat]["subcategories"]:
            # Find subcategory meta
            sub_meta = next(
                (r for r in SUBCATEGORY_RULES if r["name"] == subcat),
                {"icon": DEFAULT_SUBCATEGORY_META["icon"], "color": DEFAULT_SUBCATEGORY_META["color"]},
            )
            cats[cat]["subcategories"][subcat] = {
                "name": subcat,
                "count": 0,
                "icon": sub_meta["icon"],
                "color": sub_meta["color"],
                "issues": [],
            }
        cats[cat]["subcategories"][subcat]["count"] += 1
        cats[cat]["subcategories"][subcat]["issues"].append(issue["number"])

    return cats


def build_monthly_index(issues: list) -> dict:
    """Build year-month -> issue numbers index."""
    monthly = {}
    for issue in issues:
        ym = issue["year_month"]
        if ym not in monthly:
            monthly[ym] = {"month": ym, "count": 0, "issues": []}
        monthly[ym]["count"] += 1
        monthly[ym]["issues"].append(issue["number"])
    return dict(sorted(monthly.items(), reverse=True))


def build_stats(issues: list) -> dict:
    """Build summary statistics."""
    now = datetime.now(timezone.utc)
    this_month = now.strftime("%Y-%m")
    from datetime import timedelta
    week_start = (now - timedelta(days=now.weekday())).replace(
        hour=0, minute=0, second=0, microsecond=0
    )
    week_start_str = week_start.isoformat()

    this_month_count = sum(1 for i in issues if i["year_month"] == this_month)
    this_week_count = sum(1 for i in issues if i["created_at"] >= week_start_str)
    featured_count = sum(1 for i in issues if i["featured"])

    cat_counts = {}
    subcat_counts = {}
    for i in issues:
        cat = i["category"]
        subcat = i["subcategory"]
        cat_counts[cat] = cat_counts.get(cat, 0) + 1
        key = f"{cat}|{subcat}"
        subcat_counts[key] = subcat_counts.get(key, 0) + 1

    # Build subcategory metadata for frontend
    subcat_meta = {}
    for rule in SUBCATEGORY_RULES:
        subcat_meta[rule["name"]] = {"icon": rule["icon"], "color": rule["color"]}
    subcat_meta[DEFAULT_SUBCATEGORY] = DEFAULT_SUBCATEGORY_META

    return {
        "total": len(issues),
        "this_month": this_month_count,
        "this_week": this_week_count,
        "featured": featured_count,
        "by_category": cat_counts,
        "by_subcategory": subcat_counts,
        "subcategory_meta": subcat_meta,
        "last_updated": now.isoformat(),
    }


def write_output(issues: list, categories: dict, monthly: dict, stats: dict):
    """Write all output JSON files."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    issues_output = {
        "meta": {
            "repo": REPO,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "total": len(issues),
            "categories": CATEGORY_META,
            "subcategory_meta": {r["name"]: {"icon": r["icon"], "color": r["color"]} for r in SUBCATEGORY_RULES},
        },
        "stats": stats,
        "issues": issues,
    }
    with open(DATA_DIR / "issues.json", "w", encoding="utf-8") as f:
        json.dump(issues_output, f, ensure_ascii=False, separators=(",", ":"))
    size_mb = os.path.getsize(DATA_DIR / "issues.json") / 1024 / 1024
    print(f"   → issues.json ({size_mb:.1f} MB)")

    with open(DATA_DIR / "categories.json", "w", encoding="utf-8") as f:
        json.dump(categories, f, ensure_ascii=False, indent=2)

    with open(DATA_DIR / "monthly.json", "w", encoding="utf-8") as f:
        json.dump(monthly, f, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    try:
        fetch_all_issues()
    except KeyboardInterrupt:
        print("\n\n⚠ Interrupted by user")
        sys.exit(1)
    except HTTPError as e:
        print(f"\n\n❌ HTTP Error {e.code}: {e.reason}")
        if e.code == 403:
            print("   Rate limit exceeded. Set GITHUB_TOKEN to increase limit.")
        sys.exit(1)
    except URLError as e:
        print(f"\n\n❌ Network Error: {e.reason}")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
