"""
Scrapy settings for WRC scraper.

Key decisions:
- AUTOTHROTTLE enabled: automatically adjusts request speed based on server
  response times, so we don't get blocked
- DOWNLOAD_DELAY=1.5: minimum 1.5 seconds between requests to be polite
- CONCURRENT_REQUESTS=4: moderate parallelism, enough to be fast but not aggressive
- RETRY_TIMES=3: retry failed requests up to 3 times before giving up
- User-Agent rotation: appear as a normal browser, not a bot
"""

import os
import sys

# Add project root to path for config imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
from common.config import DOWNLOAD_DELAY, CONCURRENT_REQUESTS, RETRY_TIMES, LOG_LEVEL

BOT_NAME = "wrc_scraper"
SPIDER_MODULES = ["wrc_scraper.spiders"]
NEWSPIDER_MODULE = "wrc_scraper.spiders"

# --- Politeness: Don't get blocked ---
# Obey robots.txt (good practice, shows respect for site rules)
ROBOTSTXT_OBEY = True

# Delay between consecutive requests to the same domain
DOWNLOAD_DELAY = DOWNLOAD_DELAY

# Max concurrent requests (total and per domain)
CONCURRENT_REQUESTS = CONCURRENT_REQUESTS
CONCURRENT_REQUESTS_PER_DOMAIN = CONCURRENT_REQUESTS

# --- AutoThrottle: Automatically adjusts speed ---
# This is the smartest way to avoid getting blocked.
# It monitors server response times and slows down if the server is struggling.
AUTOTHROTTLE_ENABLED = True
AUTOTHROTTLE_START_DELAY = DOWNLOAD_DELAY
AUTOTHROTTLE_MAX_DELAY = 10
AUTOTHROTTLE_TARGET_CONCURRENCY = 2.0

# --- Retries ---
RETRY_TIMES = RETRY_TIMES
RETRY_HTTP_CODES = [500, 502, 503, 504, 408, 429]

# --- User Agent ---
# Appear as a normal browser to avoid being flagged as a bot
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/120.0.0.0 Safari/537.36"
)

# --- Output encoding ---
FEED_EXPORT_ENCODING = "utf-8"

# --- Logging ---
LOG_LEVEL = LOG_LEVEL

# --- Pipelines ---
# These will be enabled once we build them in the next step.
# The number (300, 400) is the execution order — lower runs first.
ITEM_PIPELINES = {
    "wrc_scraper.pipelines.MinIOPipeline": 300,
    "wrc_scraper.pipelines.MongoDBPipeline": 400,
}

# --- Request settings ---
# Timeout for downloading a page (seconds)
DOWNLOAD_TIMEOUT = 30

# Don't cache (we want fresh data each time)
HTTPCACHE_ENABLED = False

# Set the request fingerprinting implementation
REQUEST_FINGERPRINTER_IMPLEMENTATION = "2.7"
TWISTED_REACTOR = "twisted.internet.asyncioreactor.AsyncioSelectorReactor"
