<p align="center">
  <img src="https://img.shields.io/badge/Python-3.12-blue?style=flat-square&logo=python" alt="Python">
  <img src="https://img.shields.io/badge/license-MIT-green?style=flat-square" alt="License">
  <img src="https://img.shields.io/badge/docker-ready-2496ED?style=flat-square&logo=docker" alt="Docker">
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
- **多端推送** — 支持邮件 / Telegram，一个任务可配多个通知器
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
git clone https://github.com/malmjohn8422-tech/ai-daily-bot
cd ai-daily-bot

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
git clone https://github.com/malmjohn8422-tech/ai-daily-bot
cd ai-daily-bot

# 配置环境变量
cp .env.example .env
# 编辑 .env，填入你的 API Key、邮箱密码等

# 启动（后台运行）
docker compose up -d

# 查看运行状态
docker compose logs -f
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
```

### 任务配置 (`config.yaml`)

```yaml
tasks:
  - name: "🐙 GitHub 开源早报"
    schedule: "0 8 * * *"       # 每天早上 8 点（北京时间）
    collector: "github_trending"
    processor: "summarizer"
    notifier: "email"
    params:
      language: ""              # 空 = 全部语言
      since: "daily"
      max_articles: 10
```

## 项目结构

```
├── src/
│   ├── collectors/        # 采集器插件
│   │   ├── github_trending.py
│   │   └── hacker_news.py
│   ├── processors/        # 处理器插件
│   │   └── summarizer.py
│   ├── notifiers/         # 通知器插件
│   │   ├── telegram.py
│   │   └── email.py
│   ├── storage/           # SQLite 持久化
│   │   └── sqlite.py
│   ├── scheduler.py       # 任务调度器
│   ├── main.py            # 入口 + 配置校验
│   ├── logger.py          # 日志模块
│   └── retry.py           # 重试工具
├── config.yaml            # 任务配置
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

- [ ] Hacker News 采集器完善
- [ ] 多语言摘要支持
- [ ] Web 管理面板

## 许可证

[MIT](LICENSE)
