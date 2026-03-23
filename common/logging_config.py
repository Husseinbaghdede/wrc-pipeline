"""
Structured JSON logging configuration.

The test requires structured logs (JSON format) that include:
- Current partition being processed
- Body being scraped
- Number of records found vs. successfully scraped
- Any failed downloads with URLs and error codes
- Summary at the end of each run

This module provides:
- setup_logging(): configures JSON logging to both console and file
- ScrapeLogger: helper class to track stats and produce the summary
"""

import json
import logging
import os
from collections import defaultdict
from datetime import datetime, timezone

from common.config import LOG_PATH


class JSONFormatter(logging.Formatter):
    """
    Formats log records as JSON lines.

    Each log line is a valid JSON object, making logs easy to parse
    and analyze with tools like jq, ELK stack, etc.
    """

    def format(self, record):
        log_entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        # Include extra fields if present (partition, body, etc.)
        if hasattr(record, "extra_data"):
            log_entry.update(record.extra_data)
        return json.dumps(log_entry)


def setup_logging(log_name="wrc_pipeline"):
    """
    Configure logging to output JSON to both console and file.

    Args:
        log_name: Name for the log file (e.g. "wrc_pipeline")

    Returns:
        Logger instance
    """
    # Ensure log directory exists
    os.makedirs(LOG_PATH, exist_ok=True)

    # Create logger
    logger = logging.getLogger(log_name)
    logger.setLevel(logging.INFO)

    # Avoid duplicate handlers if called multiple times
    if logger.handlers:
        return logger

    formatter = JSONFormatter()

    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    # File handler — one log file per run
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_file = os.path.join(LOG_PATH, f"{log_name}_{timestamp}.json")
    file_handler = logging.FileHandler(log_file)
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    return logger


class ScrapeLogger:
    """
    Tracks scraping statistics and produces structured log entries.

    Designed for Scrapy's asynchronous execution model:
    - Uses per-(partition, body) keyed counters instead of mutable state
    - Safe when requests for different partitions/bodies are interleaved

    Usage:
        tracker = ScrapeLogger(logger)
        tracker.start_partition("2024-01", "Labour Court")
        tracker.record_found("2024-01", "Labour Court", count=10)
        tracker.record_scraped("2024-01", "Labour Court")
        tracker.record_failed("2024-01", "Labour Court", url, error_code, reason)
        ...
        tracker.summary()
    """

    def __init__(self, logger):
        self.logger = logger
        # Per-(partition, body) counters — safe for async interleaving
        self.found = defaultdict(int)
        self.scraped = defaultdict(int)
        self.failed = defaultdict(list)
        self.started = set()

    def start_partition(self, partition, body):
        """Log the start of processing a new partition + body combination."""
        key = (partition, body)
        self.started.add(key)

        self.logger.info(
            f"Starting partition={partition} body={body}",
            extra={"extra_data": {
                "event": "partition_start",
                "partition": partition,
                "body": body,
            }},
        )

    def record_found(self, partition, body, count=1):
        """Increment the number of records found on a search page."""
        self.found[(partition, body)] += count

    def record_scraped(self, partition=None, body=None):
        """Increment the number of successfully scraped records."""
        key = (partition, body)
        self.scraped[key] += 1

    def record_failed(self, partition, body, url, error_code, reason):
        """Log a failed download with details."""
        key = (partition, body)
        self.failed[key].append({
            "url": url,
            "error_code": error_code,
            "reason": reason,
        })
        self.logger.warning(
            f"Failed to download: {url}",
            extra={"extra_data": {
                "event": "download_failed",
                "partition": partition,
                "body": body,
                "url": url,
                "error_code": error_code,
                "reason": reason,
            }},
        )

    def summary(self):
        """
        Log per-partition summaries and a final run summary.

        Called once at spider close to report all accumulated stats.
        """
        total_found = 0
        total_scraped = 0
        total_failed = 0

        # Log per-partition summaries
        for key in sorted(self.started):
            partition, body = key
            found = self.found.get(key, 0)
            scraped = self.scraped.get(key, 0)
            failures = self.failed.get(key, [])

            total_found += found
            total_scraped += scraped
            total_failed += len(failures)

            self.logger.info(
                f"Partition complete: {partition} {body} "
                f"— found={found} scraped={scraped} failed={len(failures)}",
                extra={"extra_data": {
                    "event": "partition_end",
                    "partition": partition,
                    "body": body,
                    "records_found": found,
                    "records_scraped": scraped,
                    "records_failed": len(failures),
                    "failures": failures,
                }},
            )

        # Log overall summary
        self.logger.info(
            f"Run complete — partitions={len(self.started)} "
            f"found={total_found} scraped={total_scraped} "
            f"failed={total_failed}",
            extra={"extra_data": {
                "event": "run_summary",
                "partitions_processed": len(self.started),
                "total_records_found": total_found,
                "total_records_scraped": total_scraped,
                "total_records_failed": total_failed,
            }},
        )
