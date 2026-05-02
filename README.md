<p align="center">
  <img src="https://img.shields.io/badge/Python-3.12-blue?style=flat-square&logo=python" alt="Python">
  <img src="https://img.shields.io/badge/license-MIT-green?style=flat-square" alt="License">
  <img src="https://img.shields.io/badge/docker-ready-2496ED?style=flat-square&logo=docker" alt="Docker">
  <img src="https://github.com/malmjohn8422-tech/ai-daily-bot-p/actions/workflows/daily-bot.yml/badge.svg" alt="CI">
</p>

<h1 align="center">AI Daily Bot 📬</h1>

<p align="center">
  每日自动采集热点，AI 整理成简报，推送到你的手机。
  <br>插件化架构 · 趋势雷达 · 多端推送
</p>

---

## 简介

AI Daily Bot 是一个每日自动运行的简报机器人。每天定时采集 GitHub Trending 热门项目，交给 AI 生成带星级推荐的中文简报，并通过邮件或 Telegram 推送到你手机上。

内置 **趋势雷达** 模块，自动对比过去 7 天的数据，识别哪些项目是新上榜、哪些持续升温，让你不错过任何一个值得关注的方向。

## 功能特性

- **插件架构** — 采集器、处理器、通知器各自独立，加新数据源只需一个文件
- **AI 摘要** — 调用大模型生成中文简报，含星级推荐和一句话亮点
- **趋势雷达** — 对比 7 天历史数据，标记「新上榜」「连续在榜」「热度猛增」
- **报告归档** — AI 输出保存为 Markdown，通知失败重试时复用报告，避免重复调用模型
- **多端推送** — 支持邮件 / Telegram，每个任务可配一个通知器
- **定时调度** — APScheduler 驱动，cron 表达式精确到分钟，默认北京时间
- **自动重试** — 采集或 AI 调用失败时自动重试最多 3 次（指数退避）
- **配置校验** — 启动时检查所有配置项，环境变量缺失直接报错，避免带病运行
- **Docker 部署** — 一键启动，优雅关机，日志持久化

## 快速开始

本项目支持两种运行方式：

> 💡 **第一次上手**建议先走本地方式，调试方便。配好之后可以一直保持本地运行，不强制用 Docker。

### 方式一：本地运行（开发调试用）

需要 Python 3.12+ 环境。

```bash
# 克隆项目
git clone https://github.com/malmjohn8422-tech/ai-daily-bot-p
cd ai-daily-bot-p

# 安装依赖
pip install -r requirements.txt

# 配置环境变量
cp .env.example .env
# 然后用文本编辑器打开 .env，填上你的 API Key、邮箱密码等
```

环境变量配好后运行：

```bash
python -m src.main
```

终端会显示调度器已启动，到了设定的时间就会自动执行任务。

### 方式二：Docker 部署（VPS 长期运行用）

适合部署到云服务器上 7×24 小时跑，不用保持终端开着。需要先在机器上安装 Docker 和 Docker Compose。

```bash
# 克隆项目
git clone https://github.com/malmjohn8422-tech/ai-daily-bot-p
cd ai-daily-bot-p

# 配置环境变量
cp .env.example .env
# 编辑 .env，填入你的 API Key、邮箱密码等

# 启动（后台运行）
docker compose up -d

# 查看运行状态
docker compose logs -f
```

### 方式三：GitHub Actions（零成本 CI）

适合不想管服务器的场景。当前 workflow 配置为每天北京时间 08:17 自动运行，无需 VPS，无需保持终端。

> 注意：GitHub Actions 的 `schedule` 触发是 best-effort，不保证严格准点；平台高负载时可能延迟，极端情况下可能跳过某次定时触发。如果简报必须每天稳定送达，建议使用 VPS/Docker 长期运行，或用外部 cron 服务触发 GitHub Actions。

```bash
# 1. 把项目推送到 GitHub
# 2. 在 GitHub 仓库 → Settings → Secrets and variables → Actions 添加以下密钥：
#    AI_API_BASE    — AI API 地址
#    AI_API_KEY     — API Key
#    AI_MODEL       — 模型名
#    EMAIL_USERNAME — Gmail 地址（当前默认任务使用邮件，必填）
#    EMAIL_PASSWORD — Gmail 应用专用密码
#    EMAIL_RECIPIENT— 接收邮箱
#    TELEGRAM_BOT_TOKEN — Telegram Bot Token（仅当任务 notifier 改为 telegram 时需要）
#    TELEGRAM_CHAT_ID   — Telegram Chat ID（仅当任务 notifier 改为 telegram 时需要）
# 3. 启用 GitHub Actions，等待定时运行，或在 Actions 页面手动触发
```

也可在仓库 Actions 页面手动触发运行。手动触发成功只能证明代码、Secrets 和推送通道可用；如果定时运行没有出现记录，通常是 GitHub schedule 触发本身没有执行，而不是程序失败。

### 运行测试

```bash
pip install -r requirements-dev.txt
python -m pytest -q
```

## 配置说明

### 环境变量 (`.env`)

```ini
# AI API
AI_API_BASE=https://your-api.com/v1/chat/completions
AI_API_KEY=sk-xxxxx
AI_MODEL=gpt-5.5

# 邮件推送（Gmail SMTP）
EMAIL_USERNAME=your@gmail.com
EMAIL_PASSWORD=your-app-password
EMAIL_RECIPIENT=you@domain.com

# Telegram 推送（可选；仅当任务 notifier: "telegram" 时需要）
TELEGRAM_BOT_TOKEN=123456:abc
TELEGRAM_CHAT_ID=123456789
```

### 任务配置 (`config.yaml`)

```yaml
tasks:
  - name: "🐙 GitHub 开源早报"
    schedule: "0 8 * * *"       # 本地/Docker 模式：每天早上 8 点（北京时间）
    collector: "github_trending"
    processor: "summarizer"
    notifier: "email"
    params:
      language: ""              # 空 = 全部语言
      since: "daily"
      max_articles: 10

  - name: "📊 GitHub 一周趋势总结"
    schedule: "0 9 * * 0"       # 每周日早上 9 点（北京时间）
    collector: "none"           # 只读取历史数据，不重新采集
    processor: "weekly"
    notifier: "email"
    save_trends: false
    params:
      task_name: "🐙 GitHub 开源早报"
```

## 项目结构

```
├── src/
│   ├── collectors/        # 采集器插件
│   │   ├── github_trending.py
│   │   └── none.py
│   ├── processors/        # 处理器插件
│   │   ├── summarizer.py
│   │   └── weekly.py
│   ├── notifiers/         # 通知器插件
│   │   ├── telegram.py
│   │   └── email.py
│   ├── storage/           # SQLite 持久化
│   │   └── sqlite.py
│   ├── scheduler.py       # 任务调度器
│   ├── main.py            # 入口 + 配置校验
│   ├── reports.py         # 报告归档（原子写入、JSON 元数据）
│   ├── logger.py          # 日志模块
│   └── retry.py           # 重试工具
├── .github/workflows/     # GitHub Actions 自动调度
│   └── daily-bot.yml
├── tests/                 # 最小测试（配置校验、通知器、调度器）
│   ├── test_config.py
│   ├── test_notifiers.py
│   └── test_scheduler.py
├── config.yaml            # 任务配置
├── reports/               # 自动生成的 Markdown 报告（不入库）
├── requirements-dev.txt   # 开发依赖（pytest）
├── docker-compose.yml     # Docker 部署
└── .env                   # 密钥（不入库）
```

## 效果示例

每日推送的简报包含：

```
📡 数据来源: GitHub Trending

【1】warpdotdev/warp
链接: https://github.com/warpdotdev/warp
亮点：面向 Agent 的下一代终端，热度连续多日攀升。
标签：连续 4 天在榜 · 星级稳步上涨
推荐：★★★★★

【2】HunxByts/GhostTrack
链接: https://github.com/HunxByts/GhostTrack
亮点：手机号定位追踪工具，增长迅猛但需注意合规。
标签：新上榜 · 热度猛增
推荐：★★☆☆☆

...

今日趋势解读：本周 AI 编程工具持续主导热榜...
```

## 路线图

- [ ] Web 管理面板

## 许可证

[MIT](LICENSE)
