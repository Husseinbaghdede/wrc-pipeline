"""
Airflow DAG for the WRC Scraper Pipeline.

This DAG orchestrates two tasks:
1. scrape: Runs the Scrapy spider to scrape decisions and store raw data
2. transform: Runs the transformation script to clean HTML files

The user triggers this DAG manually with two parameters:
    - start_date: e.g. "2024-01-01"
    - end_date:   e.g. "2025-01-01"

Task dependency: scrape >> transform
(transform only runs after scrape finishes successfully)
"""

from airflow import DAG
from airflow.operators.bash import BashOperator
from datetime import datetime

# Default args applied to all tasks in the DAG
default_args = {
    "owner": "wrc-pipeline",
    "retries": 1,                    # Retry once if a task fails
}

with DAG(
    dag_id="wrc_pipeline",
    default_args=default_args,
    description="Scrape WRC decisions and transform HTML files",
    # schedule=None means manual trigger only (no automatic scheduling)
    schedule=None,
    start_date=datetime(2024, 1, 1),
    catchup=False,
    # These are the parameters the user provides when triggering the DAG
    params={
        "start_date": "2024-01-01",
        "end_date": "2025-01-01",
    },
    tags=["wrc", "scraper"],
) as dag:

    # -------------------------------------------------------------------------
    # Task 1: Scrape
    #
    # Runs the Scrapy spider with the user-provided date range.
    # The spider scrapes all 4 bodies, handles pagination, downloads docs,
    # and stores everything in MongoDB + MinIO (landing zone).
    #
    # cd /opt/airflow/scraper: navigate to where scrapy.cfg lives
    # PYTHONPATH: so the spider can import from common.config
    # -------------------------------------------------------------------------
    scrape = BashOperator(
        task_id="scrape",
        bash_command=(
            "cd /opt/airflow/scraper && "
            "PYTHONPATH=/opt/airflow "
            "scrapy crawl decisions "
            "-a start_date={{ params.start_date }} "
            "-a end_date={{ params.end_date }}"
        ),
    )

    # -------------------------------------------------------------------------
    # Task 2: Transform
    #
    # Runs the transformation script on the landing zone data.
    # Cleans HTML files (BeautifulSoup), renames to identifier.ext,
    # uploads to transformed-zone bucket, stores in transformed_metadata.
    #
    # Only runs AFTER scrape finishes successfully.
    # -------------------------------------------------------------------------
    transform = BashOperator(
        task_id="transform",
        bash_command=(
            "cd /opt/airflow && "
            "PYTHONPATH=/opt/airflow "
            "python transform/transform.py "
            "--start-date {{ params.start_date }} "
            "--end-date {{ params.end_date }}"
        ),
    )

    # Define dependency: transform runs only after scrape succeeds
    scrape >> transform
