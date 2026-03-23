# WRC Scraper Pipeline

A Scrapy-based pipeline to scrape legal decisions from Ireland's [Workplace Relations Commission](https://www.workplacerelations.ie) website, store metadata in MongoDB, files in MinIO, and orchestrate with Apache Airflow.

## Prerequisites

- [Docker Desktop](https://www.docker.com/products/docker-desktop/) installed and running
- Git

## Quick Start

### 1. Clone the repository
```bash
git clone <repo-url>
cd wrc-scraper
```

### 2. Create environment file
```bash
cp .env.example .env
```
Edit `.env` if you want to change any defaults (ports, credentials, etc.).

### 3. Start all services
```bash
docker-compose up -d
```
This starts: MongoDB, MinIO, PostgreSQL (Airflow DB), Airflow Webserver, and Airflow Scheduler.

Wait ~60 seconds for all services to initialize.

### 4. Access the UIs
- **Airflow**: http://localhost:8081 (login: `admin` / `admin`)
- **MinIO Console**: http://localhost:9001 (login: `minioadmin` / `minioadmin`)

### 5. Run the pipeline

**Option A — Via Airflow UI (recommended):**
1. Open http://localhost:8081
2. Find the `wrc_pipeline` DAG
3. Click "Trigger DAG w/ config"
4. Enter:
```json
{
    "start_date": "2024-01-01",
    "end_date": "2025-01-01"
}
```
5. Click "Trigger"
6. Watch the `scrape` task run, then `transform` will start automatically

**Option B — Via CLI:**
```bash
# Trigger from Airflow CLI
docker exec wrc-airflow-scheduler airflow dags trigger wrc_pipeline \
    --conf '{"start_date":"2024-01-01","end_date":"2025-01-01"}'
```

### 6. Verify results
- **MongoDB**: Check `wrc_scraper.landing_metadata` and `wrc_scraper.transformed_metadata` collections
- **MinIO**: Browse `landing-zone` and `transformed-zone` buckets at http://localhost:9001

### 7. Stop services
```bash
docker-compose down
```
To also remove stored data:
```bash
docker-compose down -v
```

## Project Structure

```
wrc-scraper/
├── docker-compose.yml          # All services (MongoDB, MinIO, Airflow)
├── .env.example                # Configuration template
├── requirements.txt            # Python dependencies
├── ARCHITECTURE.md             # Design decisions write-up
├── dags/
│   └── wrc_pipeline_dag.py     # Airflow DAG: scrape >> transform
├── scraper/
│   ├── scrapy.cfg
│   └── wrc_scraper/
│       ├── settings.py         # Scrapy settings (throttling, retries)
│       ├── items.py            # Data model for decisions
│       ├── spiders/
│       │   └── decisions_spider.py  # Main spider
│       └── pipelines.py        # MongoDB + MinIO storage
├── transform/
│   └── transform.py            # BeautifulSoup HTML cleaning
├── common/
│   ├── config.py               # Central config from env vars
│   ├── mongo_client.py         # MongoDB connection helper
│   ├── minio_client.py         # MinIO connection helper
│   └── logging_config.py       # Structured JSON logging
└── logs/                       # JSON log files
```

## Configuration

All settings are configurable via environment variables (`.env` file):

| Variable | Default | Description |
|---|---|---|
| `MONGO_URI` | `mongodb://localhost:27017` | MongoDB connection string |
| `MONGO_DB_NAME` | `wrc_scraper` | Database name |
| `MINIO_ENDPOINT` | `localhost:9000` | MinIO API endpoint |
| `MINIO_ACCESS_KEY` | `minioadmin` | MinIO access key |
| `MINIO_SECRET_KEY` | `minioadmin` | MinIO secret key |
| `DOWNLOAD_DELAY` | `1.5` | Seconds between requests |
| `CONCURRENT_REQUESTS` | `4` | Max parallel requests |
| `RETRY_TIMES` | `3` | Retry count for failed requests |
| `PARTITION_SIZE` | `monthly` | Date partition granularity |

## Key Features

- **Idempotent**: Re-running with the same date range won't create duplicates or re-download unchanged files
- **Structured JSON logs**: Every run produces detailed logs with partition, body, success/failure counts
- **Rate limiting**: AUTOTHROTTLE + configurable delay to avoid getting blocked
- **Two-zone architecture**: Landing zone (raw) and transformed zone (clean) kept separate
- **Fully containerized**: One `docker-compose up` starts everything
