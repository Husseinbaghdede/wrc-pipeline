# Architecture Decisions

## Date Partition Size: Monthly

Monthly partitions provide a good balance between granularity and efficiency. The WRC website has ~62,000 decisions spanning 20+ years, averaging ~250 decisions per month. Monthly partitions keep each request's result set manageable (typically <500 records per body per month), which reduces the risk of timeouts and makes pagination predictable. Daily partitions would create excessive requests (365 per year × 4 bodies = 1,460 search requests), while yearly partitions could produce result sets too large for reliable scraping. Monthly also aligns naturally with how legal decisions are published and reported.

## Retries and Rate Limiting

We use a layered approach to avoid being blocked:

1. **Scrapy AUTOTHROTTLE**: Automatically adjusts request speed based on the server's response time. If the server slows down, we slow down too.
2. **DOWNLOAD_DELAY (1.5s)**: Minimum wait between requests, ensuring we never hammer the server.
3. **CONCURRENT_REQUESTS (4)**: Moderate parallelism — fast enough to be efficient, conservative enough to be polite.
4. **RETRY_TIMES (3)**: Failed requests are retried up to 3 times with backoff. HTTP 429 (Too Many Requests) and 5xx errors trigger retries.
5. **User-Agent rotation**: Requests use a standard browser User-Agent header to avoid bot detection.

All parameters are configurable via environment variables, allowing operators to tune for different network conditions or server tolerance.

## Deduplication Strategy

Idempotency is achieved through two mechanisms:

1. **File-level**: Before uploading to MinIO, we calculate the SHA256 hash of the file content and compare it against the hash stored in the object's metadata. If identical, the upload is skipped. This prevents re-downloading unchanged documents.
2. **Record-level**: MongoDB uses `identifier` as a unique index. We use `update_one` with `upsert=True`, which inserts new records and updates existing ones. Running the pipeline twice with the same date range produces no duplicates and only updates records whose content has changed.

This approach ensures that the pipeline can be safely re-run without data corruption or wasted bandwidth.

## Scaling to 50+ Sources

To support 50+ legal sources beyond WRC, the following changes would be needed:

1. **Source abstraction**: Extract the spider into a base class with configurable selectors, URL patterns, and body definitions. Each source gets its own spider subclass that overrides source-specific logic.
2. **Dynamic DAG generation**: Instead of one hardcoded DAG, generate DAGs dynamically from a source registry (YAML/JSON config), with each source as a separate DAG or task group.
3. **Distributed execution**: Replace Airflow's LocalExecutor with CeleryExecutor or KubernetesExecutor to run multiple spiders in parallel across workers.
4. **Shared infrastructure**: MongoDB and MinIO scale horizontally — MongoDB via replica sets/sharding, MinIO via distributed mode. Each source gets its own collections and bucket prefixes for isolation.
5. **Centralized configuration**: Move source definitions to a database or config service rather than code, allowing operators to add sources without code changes.
6. **Monitoring**: Add alerting on failure rates per source, scraping lag, and storage growth via Prometheus/Grafana dashboards.
