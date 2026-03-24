"""
Central configuration loaded from environment variables.
All connection strings, storage paths, partition sizes, and scraping
parameters are configurable here — no hardcoded values in the codebase.
"""

import os
from dotenv import load_dotenv

load_dotenv()


# --- MongoDB ---
MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")
MONGO_DB_NAME = os.getenv("MONGO_DB_NAME", "wrc_scraper")
MONGO_LANDING_COLLECTION = os.getenv("MONGO_LANDING_COLLECTION", "landing_metadata")
MONGO_TRANSFORMED_COLLECTION = os.getenv("MONGO_TRANSFORMED_COLLECTION", "transformed_metadata")

# --- MinIO ---
MINIO_ENDPOINT = os.getenv("MINIO_ENDPOINT", "localhost:9000")
MINIO_ACCESS_KEY = os.getenv("MINIO_ACCESS_KEY", "minioadmin")
MINIO_SECRET_KEY = os.getenv("MINIO_SECRET_KEY", "minioadmin")
MINIO_LANDING_BUCKET = os.getenv("MINIO_LANDING_BUCKET", "landing-zone")
MINIO_TRANSFORMED_BUCKET = os.getenv("MINIO_TRANSFORMED_BUCKET", "transformed-zone")

# --- Scraping ---
PARTITION_SIZE = os.getenv("PARTITION_SIZE", "monthly")
DOWNLOAD_DELAY = float(os.getenv("DOWNLOAD_DELAY", "1.0"))
CONCURRENT_REQUESTS = int(os.getenv("CONCURRENT_REQUESTS", "4"))
RETRY_TIMES = int(os.getenv("RETRY_TIMES", "3"))
AUTOTHROTTLE_MAX_DELAY = float(os.getenv("AUTOTHROTTLE_MAX_DELAY", "15"))
AUTOTHROTTLE_TARGET_CONCURRENCY = float(os.getenv("AUTOTHROTTLE_TARGET_CONCURRENCY", "2.0"))
DOWNLOAD_TIMEOUT = int(os.getenv("DOWNLOAD_TIMEOUT", "60"))
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")

# --- Paths ---
LOG_PATH = os.getenv("LOG_PATH", "./logs")

# --- WRC Website ---
WRC_BASE_URL = os.getenv("WRC_BASE_URL", "https://www.workplacerelations.ie")
WRC_SEARCH_URL = f"{WRC_BASE_URL}/en/search/"

# Body IDs on the WRC search page (override via comma-separated "name:id" pairs)
_default_bodies = "Employment Appeals Tribunal:2,Equality Tribunal:1,Labour Court:3,Workplace Relations Commission:15376"
WRC_BODIES = {
    pair.split(":")[0].strip(): pair.split(":")[1].strip()
    for pair in os.getenv("WRC_BODIES", _default_bodies).split(",")
}

RESULTS_PER_PAGE = int(os.getenv("RESULTS_PER_PAGE", "10"))
