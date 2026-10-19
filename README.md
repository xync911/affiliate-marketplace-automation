# Affiliate Marketplace Live Automation System

## Overview
A microservices-based automation system for affiliate marketing that:
- Scrapes products from Indonesian marketplaces (Tokopedia, Shopee, Lazada) using rotating proxies
- Generates dynamic content using local AI models (Qwen 2.5/Kimi 2.7) via Ollama
- Distributes content to social platforms (X, Facebook, TikTok/Threads) with anti-ban measures
- Pushes all output to GitHub for version control and backup

## Architecture
```
┌─────────────────┐    ┌──────────────────┐    ┌────────────────────┐
│   Scraper       │───▶│    AI Engine     │───▶│   Task Queue       │
│ (Playwright+    │    │ (Ollama/Qwen)    │    │ (Celery+Redis)     │
│  Proxies)       │    │                  │    │                    │
└─────────────────┘    └──────────────────┘    └────────────────────┘
          │                         │                         │
          ▼                         ▼                         ▼
┌─────────────────┐    ┌──────────────────┐    ┌────────────────────┐
│ Anti-Banned     │    │   Distribution   │    │   GitHub Storage   │
│ (Cloaking,     │    │ (X/FB/TT/Threads)│    │  Integrator        │
│  Spintax,      │    │ + Auto-Visual)   │    │                    │
│  Human Delay)  │    │                  │    │                    │
└─────────────────┘    └──────────────────┘    └────────────────────┘
```

## Quick Start

### Prerequisites
- Docker and Docker Compose installed
- At least 4GB RAM available
- Optional: Twitter/X, Facebook, TikTok developer accounts for live posting

### Setup
1. Clone this repository (or copy the files to your machine)
2. Create `.env` file from `.env.example`:
   ```bash
   cp .env.example .env
   ```
3. The GitHub token is already configured in the task, but you can override it in `.env`:
   ```
   GITHUB_TOKEN=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
   ```

### Build and Run
```bash
docker-compose up --build
```

### Services
- **Scraper**: Extracts products using rotating proxies
- **AI Engine**: Generates copy via Ollama (Qwen 2.5:7b)
- **Task Queue**: Celery workers with Redis broker
- **Anti-Banned**: Link cloaking, spintax, humanized delays
- **Distribution**: Posts to X, Facebook, TikTok/Threads with auto-visual
- **GitHub Integrator**: Pushes content to specified repo
- **Trend Detector**: Monitors trending topics for instant triggers

## Configuration

### Working Hours
The system operates during:
- Shift 1: 07:00 - 18:00
- Shift 2: 22:00 - 07:00
Outside these hours, only essential maintenance tasks run.

### Humanized Delays
Between posts: 5-17 minutes randomized to mimic human behavior.

### Platform-Specific Output
- **X**: Thread format with image + threaded replies containing affiliate links
- **Facebook**: Grid format with detailed reviews in Groups/Fanpages
- **TikTok/Threads**: Vertical carousel with casual captions

## Components Detail

### Scraper (`services/scrapers/`)
- Uses Playwright for headless browser automation
- Implements rotating proxy middleware
- Handles marketplace-specific selectors

### AI Engine (`services/ai-engine/`)
- Connects to local Ollama instance
- Generates product captions, threads, and hashtags
- Integrates with spintax engine for variation

### Task Queue (`services/task-queue/`)
- Celery app with Redis broker
- Beat scheduler for time-based tasks
- Worker processes for background jobs

### Anti-Banned (`services/anti-banned/`)
- `link_cloak.py`: Creates intermediary landing pages
- `spintax.py`: Dynamic sentence/hashtag rotation
- Humanized delay logic in task queue

### Distribution (`services/distribution/`)
- Platform-specific posters (X, Facebook, TikTok/Threads)
- Auto-visual enhancer (Pillow-based image processing)
- Trend detector for real-time triggers

### Storage (`services/storage/`)
- GitHub integrator using provided token
- Saves all generated content to repo

## Monitoring
- RedisInsight available at http://localhost:8001
- Logs stored in `logs/` directory
- Health checks on all services via Docker

## Extending the System
1. Add new scrapers in `services/scrapers/` for other marketplaces
2. Extend AI prompts in `services/ai-engine/ai_engine.py`
3. Add new platforms in `services/distribution/distributor.py`
4. Modify scheduling in `services/task-queue/worker.py`

## Notes
- The system starts in simulation mode (no actual posting). To enable live posting:
  - Set `simulate_only: False` in `ContentDistributor` constructor
  - Configure API credentials in `.env` for each platform
- For production, replace the placeholder proxy list with a paid rotating proxy service
- The AI models (Qwen 2.5:7b) will be automatically pulled on first run via Ollama

## GitHub Integration
All generated content is pushed to:
- Repository: ayushafira/affiliate-marketplace-automation
- Author: Ayusha Shafira
- Token: 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 (provided in task)

Content is stored in:
- `content/` directory for text/captions
- `content/images/` for processed visuals
- Commit messages include product titles and timestamps

## Troubleshooting
- Check service logs: `docker-compose logs <service-name>`
- Verify Ollama is running: `docker-compose logs ollama`
- Check Redis connection: `docker-compose logs redis`
- For scraping issues, increase timeout in scraper or check proxy connectivity

---
System ready for deployment. Start with `docker-compose up --build` and monitor output.