# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

FeatherFlow is a Python-based web scraping system for collecting agricultural market prices from 惠农网 (cnhnb.com). It's designed for unattended operation with built-in anti-scraping countermeasures, scheduling, and MySQL data persistence.

## Key Commands

### Development Setup
```bash
# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Install Playwright browsers (optional, for fallback mode)
python -m playwright install chromium
```

### Running the Application
```bash
# Start the main scheduled crawler service
python -m app.main
```

### Testing
```bash
# Run unit tests
pytest -q

# Run with verbose output
pytest -v
```

### Docker Deployment
```bash
# Build and run with Docker Compose
docker-compose up --build

# Build with Playwright dependencies
docker-compose build --build-arg INSTALL_PLAYWRIGHT_DEPS=true
```

## Architecture

### Core Components

**Entry Point (`app/main.py`)**
- Main service entry point with signal handling
- Initializes database schema and scheduler
- Manages graceful shutdown

**Scheduler (`app/scheduler.py`)**
- Uses APScheduler for cron-based scheduling
- Configured via `CRON` environment variable (5-segment format)
- Supports immediate execution on start via `RUN_ON_START`

**Crawler Engine (`app/crawler/hn_crawler.py`)**
- Multi-layer fetching: HTTP requests → Playwright fallback
- Anti-scraping features: UA rotation, exponential backoff, block detection
- Pagination handling with automatic URL pattern detection
- Implements daily deduplication to skip already processed keywords

**Parser (`app/parser/hn_parser.py`)**
- BeautifulSoup-based HTML parsing for market listings
- Extracts structured data: date, product, place, price
- Price value/unit parsing with fallback for non-numeric prices
- Total pages extraction from pagination controls

**Database Layer (`app/db/mysql.py`)**
- Custom MySQL connection pool using PyMySQL
- Idempotent upsert operations to prevent duplicates
- Schema initialization and daily existence checks

**Configuration (`app/config.py`)**
- Pydantic-based settings from environment variables
- Supports `.env` file for local development
- Comprehensive configuration for MySQL, HTTP, scheduling, and anti-scraping

### Data Flow
1. **Scheduler** triggers crawling job at configured intervals
2. **Crawler** checks if keyword already processed today → skips if exists
3. **Fetch HTML** via HTTP requests, fallback to Playwright if blocked
4. **Parse** market listings from HTML to extract price data
5. **Store** in MySQL using idempotent upserts
6. **Retry** with exponential backoff if anti-scraping detected

### Anti-Scraping Strategy
- **Dual fetching**: HTTP requests (primary) + Playwright browser automation (fallback)
- **User-Agent rotation**: Multiple realistic browser UAs with randomization
- **Block detection**: Heuristic detection of captchas, rate limits, and access controls
- **Exponential backoff**: Progressive delays with configurable limits
- **Browser restart**: Automatic Playwright instance restart on detection

### Database Schema
- **Table**: `hn_market_price`
- **Unique constraint**: `(keyword, price_date, product, place, price_raw)` for idempotency
- **Indexing**: Optimized for daily keyword existence checks
- **Encoding**: utf8mb4 for full Chinese character support

## Configuration

### Environment Variables
Key configuration via `.env` file or environment variables:

```bash
# Database
MYSQL_HOST=127.0.0.1
MYSQL_PORT=3306
MYSQL_USER=root
MYSQL_PASSWORD=your_password
MYSQL_DATABASE=hn_market

# Business Logic
KEYWORDS=鹅,玉米,豆粕
CRON=30 8 * * *  # Daily at 08:30
RUN_ON_START=1

# HTTP/Scraping
HTTP_TIMEOUT_SECONDS=20
HTTP_RETRY_TIMES=2
ENABLE_PLAYWRIGHT_FALLBACK=1
PLAYWRIGHT_HEADLESS=1

# Anti-Scraping
BACKOFF_BASE_SECONDS=10
BACKOFF_MAX_SECONDS=600
BLOCKED_MAX_RETRY=2

# Logging
LOG_LEVEL=INFO
```

## File Structure Notes

- **`app/`**: Main application code
- **`tests/`**: Unit tests for parser components
- **`requirements.txt`**: Python dependencies (includes duplicate entries, clean if needed)
- **`Dockerfile`**: Multi-stage build with optional Playwright support
- **`docker-compose.yml`**: Container orchestration with environment injection
- **`app/db/schema.sql`**: MySQL table definition

## Development Guidelines

- **Testing**: Parser components have comprehensive unit tests using sample HTML files
- **Logging**: Structured logging with configurable levels, all in Chinese for user-facing messages
- **Error Handling**: Graceful degradation with detailed logging, service continues on individual keyword failures
- **Idempotency**: All operations designed to be safe for repeated execution