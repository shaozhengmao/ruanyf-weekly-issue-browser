# 📰 阮一峰周刊 · Issue 浏览器

一个静态网站，用于分类浏览 [阮一峰科技爱好者周刊](https://github.com/ruanyf/weekly) 的 GitHub Issues（自荐/投稿区）。

> 数据范围：2025年1月至今的 open issues

## ✨ 功能

- **两级分类**：一级按标题前缀（开源自荐/工具/产品/项目/投稿推荐/讨论反馈），二级按内容关键词（AI·LLM / 前端·Web / 后端·服务 / DevOps / 移动端 / 数据·可视化 / 设计·创意 / 安全·隐私 / 学习·教程）
- **全文搜索**：前端构建倒排索引，支持中英文混合搜索
- **时间筛选**：按年月过滤
- **排序**：最新 / 最热（reactions + comments）
- **收录标记**：有 `weekly` label 的 issue 标记 ⭐
- **无限滚动**：懒加载，首次只渲染30条
- **响应式设计**：手机端友好
- **暗色主题**：护眼

## 🏗️ 技术栈

- **前端**：纯 HTML/CSS/JS，零依赖
- **数据**：Python 脚本调用 GitHub API
- **部署**：GitHub Actions + GitHub Pages，每天自动更新

## 🚀 快速开始

### 本地运行

```bash
# 1. 克隆仓库
git clone https://github.com/YOUR_USERNAME/ruanyf-weekly-issue-browser.git
cd ruanyf-weekly-issue-browser

# 2. 抓取数据（可选设置 token 提高限速）
export GITHUB_TOKEN=ghp_xxxx  # 可选
python scripts/fetch_issues.py

# 3. 启动本地服务
python -m http.server 8000
# 访问 http://localhost:8000
```

### 部署到自己的 GitHub

1. Fork 本仓库
2. 进入 Settings → Pages → Source 选择 GitHub Actions
3. 手动触发一次 Actions（或等待每天自动运行）
4. 访问 `https://YOUR_USERNAME.github.io/ruanyf-weekly-issue-browser/`

## 📁 文件结构

```
ruanyf-weekly-issue-browser/
├── .github/workflows/deploy.yml   # CI/CD
├── scripts/fetch_issues.py        # 数据抓取脚本
├── data/                          # 生成的 JSON 数据
│   ├── issues.json                # 全量 issue 数据
│   ├── categories.json            # 分类索引（含二级）
│   └── monthly.json               # 月度索引
├── css/style.css                  # 样式
├── js/app.js                      # 前端逻辑
├── index.html                     # 入口页
└── README.md
```

## 📊 分类规则

### 一级分类（标题前缀）

| 前缀 | 分类 |
|------|------|
| `【开源自荐】` `[开源自荐]` | 📦 开源项目 |
| `【工具自荐】` | 🔧 工具 |
| `【产品自荐】` | 🚀 产品 |
| `【项目自荐】` | 💡 项目 |
| `【投稿】` `【推荐】` | 📮 投稿推荐 |
| 其他 | 💬 讨论/反馈 |

### 二级分类（内容关键词）

| 子分类 | 匹配关键词示例 |
|--------|---------------|
| 🤖 AI/LLM | AI, LLM, GPT, Agent, 大模型 |
| 🌐 前端/Web | React, Vue, CSS, JavaScript |
| ⚙️ 后端/服务 | API, Docker, 数据库, Go, Rust |
| 🔨 DevOps/效率 | CI/CD, CLI, 自动化, 部署 |
| 📱 移动端 | iOS, Android, Flutter, 小程序 |
| 📊 数据/可视化 | 图表, BI, 爬虫, 数据分析 |
| 🎨 设计/创意 | UI, 视频, 3D, Figma |
| 🔒 安全/隐私 | VPN, 加密, 代理, 防火墙 |
| 📚 学习/教程 | 教程, 面试, LeetCode, 电子书 |

## 📝 License

MIT
