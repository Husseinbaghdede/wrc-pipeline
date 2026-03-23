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
DOWNLOAD_DELAY = float(os.getenv("DOWNLOAD_DELAY", "1.5"))
CONCURRENT_REQUESTS = int(os.getenv("CONCURRENT_REQUESTS", "4"))
RETRY_TIMES = int(os.getenv("RETRY_TIMES", "3"))
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")

# --- Paths ---
LOG_PATH = os.getenv("LOG_PATH", "./logs")

# --- WRC Website ---
WRC_BASE_URL = "https://www.workplacerelations.ie"
WRC_SEARCH_URL = f"{WRC_BASE_URL}/en/search/"

# Body IDs on the WRC search page
WRC_BODIES = {
    "Employment Appeals Tribunal": "2",
    "Equality Tribunal": "1",
    "Labour Court": "3",
    "Workplace Relations Commission": "15376",
}

RESULTS_PER_PAGE = 10
