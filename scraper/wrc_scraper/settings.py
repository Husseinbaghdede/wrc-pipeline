"""
Scrapy settings for WRC scraper.

Key decisions:
- AUTOTHROTTLE enabled: dynamically adjusts request rate based on server
  response latency — backs off when the server is slow, speeds up when it's fast.
  This is the fastest safe approach because it maximizes throughput without
  hammering the server.
- DOWNLOAD_DELAY=1.0: moderate floor — the WRC site is slow, going below 1s
  causes timeouts when too many requests queue up server-side
- CONCURRENT_REQUESTS=4: moderate parallelism tuned to what the WRC server
  can handle; AutoThrottle adapts within this ceiling
- RETRY_TIMES=5: retry failed requests up to 5 times before giving up — the WRC
  server can be flaky under sustained load, extra retries improve completion rate
- User-Agent rotation via scrapy-user-agents or DOWNLOADER_MIDDLEWARES:
  rotates across real browser UAs to avoid fingerprint-based blocking
"""

import os
import sys

# Add project root to path for config imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
from common.config import (
    DOWNLOAD_DELAY, CONCURRENT_REQUESTS, RETRY_TIMES, LOG_LEVEL,
    RETRY_PRIORITY_ADJUST as _RETRY_PRIORITY_ADJUST,
    AUTOTHROTTLE_MAX_DELAY as _AUTOTHROTTLE_MAX_DELAY,
    AUTOTHROTTLE_TARGET_CONCURRENCY as _AUTOTHROTTLE_TARGET_CONCURRENCY,
    DOWNLOAD_TIMEOUT as _DOWNLOAD_TIMEOUT,
)

BOT_NAME = "wrc_scraper"
SPIDER_MODULES = ["wrc_scraper.spiders"]
NEWSPIDER_MODULE = "wrc_scraper.spiders"

# --- Politeness: Don't get blocked ---
# Obey robots.txt (good practice, shows respect for site rules)
ROBOTSTXT_OBEY = True

# Delay between consecutive requests to the same domain.
# This is the MINIMUM floor — AutoThrottle adjusts upward from here.
# Kept low so AutoThrottle can find the optimal speed.
DOWNLOAD_DELAY = DOWNLOAD_DELAY

# Max concurrent requests (total and per domain).
# Higher concurrency = more throughput. AutoThrottle will scale back
# if the server responds slowly, so setting this higher is safe.
CONCURRENT_REQUESTS = CONCURRENT_REQUESTS
CONCURRENT_REQUESTS_PER_DOMAIN = CONCURRENT_REQUESTS

# --- AutoThrottle: Automatically adjusts speed ---
# This is the key to "fastest without getting blocked":
# - Starts at DOWNLOAD_DELAY, then adapts based on actual server latency
# - If the server responds in 200ms, it speeds up; if 2s, it slows down
# - TARGET_CONCURRENCY=2.0 means it tries to keep ~2 requests in-flight
#   at all times — tuned to the WRC server's capacity
AUTOTHROTTLE_ENABLED = True
AUTOTHROTTLE_START_DELAY = DOWNLOAD_DELAY
AUTOTHROTTLE_MAX_DELAY = _AUTOTHROTTLE_MAX_DELAY
AUTOTHROTTLE_TARGET_CONCURRENCY = _AUTOTHROTTLE_TARGET_CONCURRENCY

# --- Retries ---
RETRY_TIMES = RETRY_TIMES
RETRY_HTTP_CODES = [500, 502, 503, 504, 408, 429]
# Push retried requests to the back of the queue so fresh requests
# go first and the server has time to recover before retries arrive.
RETRY_PRIORITY_ADJUST = _RETRY_PRIORITY_ADJUST

# --- User-Agent Rotation ---
# Rotate across real browser user agents to avoid fingerprint-based blocking.
# A single static UA makes all requests look like one bot session.
# Rotating makes each request appear to come from a different browser.
ROTATING_USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:125.0) Gecko/20100101 Firefox/125.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
]

# Default UA (Scrapy uses this for robots.txt fetch)
USER_AGENT = ROTATING_USER_AGENTS[0]

# Custom downloader middleware to rotate user agents per request
DOWNLOADER_MIDDLEWARES = {
    "wrc_scraper.middlewares.RotateUserAgentMiddleware": 400,
    "scrapy.downloadermiddlewares.useragent.UserAgentMiddleware": None,
}

# --- Output encoding ---
FEED_EXPORT_ENCODING = "utf-8"

# --- Logging ---
LOG_LEVEL = LOG_LEVEL

# --- Pipelines ---
# The number (300, 400) is the execution order — lower runs first.
# MinIO first (stores file, sets file_path + file_hash), then MongoDB (stores metadata).
ITEM_PIPELINES = {
    "wrc_scraper.pipelines.MinIOPipeline": 300,
    "wrc_scraper.pipelines.MongoDBPipeline": 400,
}

# --- Request settings ---
# Timeout for downloading a page (seconds).
# The WRC site is slow — search queries often take 10-20s to respond.
# 90s gives enough headroom for slow responses during large crawls (500-1000+ docs)
# where the server degrades under sustained load.
DOWNLOAD_TIMEOUT = _DOWNLOAD_TIMEOUT

# Don't cache (we want fresh data each time)
HTTPCACHE_ENABLED = False

# Set the request fingerprinting implementation
REQUEST_FINGERPRINTER_IMPLEMENTATION = "2.7"
TWISTED_REACTOR = "twisted.internet.asyncioreactor.AsyncioSelectorReactor"
