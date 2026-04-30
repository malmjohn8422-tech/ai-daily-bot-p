# AI Daily Bot 📬

Plugin-based automated briefing system that collects hot repositories daily, generates AI-powered summaries with trend analysis, and pushes them to your phone.

## Features

- **Multi-source collectors** — GitHub Trending (with more sources easily pluggable)
- **AI summarization** — GPT-powered briefing with star ratings and highlights
- **Trend radar** — 7-day historical comparison to identify surging projects, sustained hot topics, and new entries
- **Multi-channel notification** — Telegram / Email (extensible notifier interface)
- **Graceful failure handling** — Automatic retry with exponential backoff, comprehensive logging, config validation at startup
- **Docker-ready** — One-command deployment via docker-compose

## Architecture

```
Collector (fetch) → Processor (summarize + trend analysis) → Notifier (push)
```

Each stage is plugin-based. Add a new data source by creating a file in `src/collectors/` and registering it in `__init__.py`.

## Quick Start

```bash
cp .env.example .env   # Fill in your API keys
pip install -r requirements.txt
python -m src.main
```

### Docker

```bash
docker compose up -d
```

### Configuration

Edit `config.yaml`:

```yaml
ai:
  api_base: ${AI_API_BASE}
  api_key: ${AI_API_KEY}
  model: gpt-5.5

notifiers:
  email:
    smtp_server: smtp.gmail.com
    smtp_port: 587
    username: ${EMAIL_USERNAME}
    password: ${EMAIL_PASSWORD}
    recipient: ${EMAIL_RECIPIENT}

tasks:
  - name: "🐙 GitHub 早报"
    schedule: "0 8 * * *"    # Cron expression (Asia/Shanghai)
    collector: "github_trending"
    processor: "summarizer"
    notifier: "email"
    params:
      language: ""
      since: "daily"
      max_articles: 10
```

## Project Structure

```
├── src/
│   ├── collectors/       # Data source plugins
│   │   ├── github_trending.py
│   │   └── hacker_news.py
│   ├── processors/       # AI processing plugins
│   │   └── summarizer.py
│   ├── notifiers/        # Notification plugins
│   │   ├── telegram.py
│   │   └── email.py
│   ├── storage/          # SQLite persistence
│   ├── scheduler.py      # APScheduler-based task runner
│   ├── main.py           # Entry point with config validation
│   ├── logger.py         # Logging with file rotation
│   └── retry.py          # Retry decorator with backoff
├── data/                 # SQLite database
├── logs/                 # Daily log files
├── config.yaml           # Task configuration
├── docker-compose.yml    # Deployment
└── .env                  # Secrets (gitignored)
```

## License

MIT
