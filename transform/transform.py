"""
Transformation script for WRC Landing Zone data.

What this script does:
1. Takes start_date and end_date as arguments
2. Fetches metadata from MongoDB (landing_metadata collection)
3. Downloads files from MinIO (landing-zone bucket)
4. For each file:
   - PDF/DOC: no transformation, just copy as-is
   - HTML: clean with BeautifulSoup (remove nav, header, footer, scripts)
5. Rename all files to identifier.ext (e.g. ADJ-00054658.html)
6. Calculate new file_hash for cleaned files
7. Upload to new MinIO bucket (transformed-zone)
8. Store updated metadata in new MongoDB collection (transformed_metadata)

This script does NOT modify the landing zone data.
It creates a separate "transformed zone" with clean data.
"""

import argparse
import hashlib
import logging
import sys
import os
from io import BytesIO

from bs4 import BeautifulSoup

# Add project root to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from common.config import (
    MONGO_LANDING_COLLECTION,
    MONGO_TRANSFORMED_COLLECTION,
    MINIO_LANDING_BUCKET,
    MINIO_TRANSFORMED_BUCKET,
)
from common.mongo_client import get_mongo_db
from common.minio_client import get_minio_client

logger = logging.getLogger(__name__)


def parse_args():
    """Parse command line arguments: start_date and end_date."""
    parser = argparse.ArgumentParser(description="Transform WRC Landing Zone data")
    parser.add_argument("--start-date", required=True, help="Start date (YYYY-MM-DD)")
    parser.add_argument("--end-date", required=True, help="End date (YYYY-MM-DD)")
    return parser.parse_args()


def fetch_landing_metadata(db, start_date, end_date):
    """
    Fetch metadata records from MongoDB landing collection
    that fall within the given date range.

    We query by partition_date which is in "YYYY-MM" format.
    start_date="2024-01-01" → start_partition="2024-01"
    end_date="2025-01-01"   → end_partition="2025-01"
    """
    start_partition = start_date[:7]  # "2024-01-01" → "2024-01"
    end_partition = end_date[:7]      # "2025-01-01" → "2025-01"

    collection = db[MONGO_LANDING_COLLECTION]
    query = {
        "partition_date": {
            "$gte": start_partition,
            "$lte": end_partition,
        }
    }
    records = list(collection.find(query))
    logger.info(f"Found {len(records)} records for partitions {start_partition} to {end_partition}")
    return records


def download_file_from_minio(minio_client, file_path):
    """
    Download a file from MinIO landing-zone bucket.

    file_path is stored as "landing-zone/ADJ-00054658.html"
    We extract just the file name part to use as the object name.
    """
    # file_path = "landing-zone/ADJ-00054658.html" → object_name = "ADJ-00054658.html"
    object_name = file_path.split("/", 1)[-1]

    try:
        response = minio_client.get_object(MINIO_LANDING_BUCKET, object_name)
        content = response.read()
        response.close()
        response.release_conn()
        return content
    except Exception as e:
        logger.error(f"Failed to download {object_name} from MinIO: {e}")
        return None


def clean_html(html_content):
    """
    Clean HTML using BeautifulSoup.

    Strategy: extract only the decision content container (div.content),
    which holds the legal decision text, tables, and headings.
    This removes all site chrome: navigation, headers, footers, scripts,
    banners, sidebars, and other non-content elements.

    Fallback: if div.content is not found, strip non-content elements
    individually (for pages with different structure).
    """
    soup = BeautifulSoup(html_content, "lxml")

    # Primary strategy: extract the decision content container directly.
    # The WRC site wraps all decision text in <div class="content">.
    content_div = soup.find("div", class_="content")

    if content_div:
        # Remove any scripts/styles that may be inside the content div
        for tag in content_div.find_all(["script", "style", "noscript"]):
            tag.decompose()

        # Remove "Return to Search" links inside content
        for tag in content_div.find_all(
            "a", string=lambda s: s and "Return to Search" in s
        ):
            tag.decompose()

        # Return just the content div as a clean HTML document
        cleaned = str(content_div)
        return cleaned

    # Fallback: strip non-content elements individually
    # (for pages that don't use the div.content structure)
    for tag in soup.find_all("nav"):
        tag.decompose()
    for tag in soup.find_all("header"):
        tag.decompose()
    for tag in soup.find_all("footer"):
        tag.decompose()
    for tag in soup.find_all(["script", "style", "noscript"]):
        tag.decompose()

    for element_id in ["globalCookieBar", "asideNav", "google_translate_element"]:
        el = soup.find(id=element_id)
        if el:
            el.decompose()

    for tag in soup.find_all(class_=lambda c: c and "navbar" in c):
        tag.decompose()
    for tag in soup.find_all("a", string=lambda s: s and "Return to Search" in s):
        tag.decompose()
    for class_name in ["firstLetter", "secondLetter", "lastLetter"]:
        for tag in soup.find_all(class_=class_name):
            tag.decompose()

    cleaned = str(soup)
    return cleaned


def transform_file(record, file_content):
    """
    Transform a single file based on its type.

    - PDF/DOC: return as-is (no transformation)
    - HTML: clean with BeautifulSoup

    Returns: (transformed_content, new_file_hash)
    """
    file_type = record.get("file_type", "html")

    if file_type in ("pdf", "doc"):
        # No transformation for PDF/DOC files
        # Just recalculate hash (will be the same)
        file_hash = hashlib.sha256(file_content).hexdigest()
        return file_content, file_hash

    # HTML file: clean it
    cleaned_html = clean_html(file_content)
    cleaned_bytes = cleaned_html.encode("utf-8")

    # Calculate new hash of the cleaned content
    file_hash = hashlib.sha256(cleaned_bytes).hexdigest()

    return cleaned_bytes, file_hash


def upload_to_transformed_zone(minio_client, file_name, content, file_type):
    """Upload a file to the transformed-zone bucket in MinIO."""
    content_types = {
        "html": "text/html",
        "pdf": "application/pdf",
        "doc": "application/msword",
    }
    content_type = content_types.get(file_type, "application/octet-stream")

    data = BytesIO(content)
    minio_client.put_object(
        bucket_name=MINIO_TRANSFORMED_BUCKET,
        object_name=file_name,
        data=data,
        length=len(content),
        content_type=content_type,
    )
    logger.info(f"Uploaded to transformed zone: {file_name}")


def store_transformed_metadata(collection, record, new_file_path, new_file_hash):
    """
    Store updated metadata in the transformed_metadata collection.

    Copies all fields from the landing record but updates:
    - file_path: points to the transformed-zone bucket
    - file_hash: hash of the cleaned content
    """
    doc = {
        "identifier": record["identifier"],
        "description": record["description"],
        "published_date": record["published_date"],
        "ref_no": record["ref_no"],
        "doc_url": record["doc_url"],
        "body": record["body"],
        "partition_date": record["partition_date"],
        "file_type": record["file_type"],
        "file_path": new_file_path,
        "file_hash": new_file_hash,
        "source_hash": record.get("file_hash", ""),
    }

    collection.update_one(
        {"identifier": record["identifier"]},
        {"$set": doc},
        upsert=True,
    )


def run_transformation(start_date, end_date):
    """
    Main transformation logic.

    1. Connect to MongoDB and MinIO
    2. Fetch landing metadata for the date range
    3. For each record: download, transform, upload, store metadata
    """
    # Connect to services
    db = get_mongo_db()
    minio_client = get_minio_client()

    # Ensure transformed bucket exists
    if not minio_client.bucket_exists(MINIO_TRANSFORMED_BUCKET):
        minio_client.make_bucket(MINIO_TRANSFORMED_BUCKET)
        logger.info(f"Created MinIO bucket: {MINIO_TRANSFORMED_BUCKET}")

    # Get the transformed metadata collection
    transformed_collection = db[MONGO_TRANSFORMED_COLLECTION]
    transformed_collection.create_index("identifier", unique=True)

    # Fetch landing zone records
    records = fetch_landing_metadata(db, start_date, end_date)

    if not records:
        logger.warning("No records found for the given date range")
        return

    success_count = 0
    skip_count = 0
    error_count = 0

    for record in records:
        identifier = record.get("identifier", "unknown")

        try:
            # Step 1: Build file info
            file_ext = record.get("file_type", "html")
            new_file_name = f"{identifier}.{file_ext}"
            new_file_path = f"{MINIO_TRANSFORMED_BUCKET}/{new_file_name}"

            # Step 2: Check if already transformed with same landing hash (idempotency)
            # Do this BEFORE downloading to avoid wasting bandwidth on re-runs
            existing = transformed_collection.find_one({"identifier": identifier})
            if existing and existing.get("source_hash") == record.get("file_hash"):
                logger.info(f"Already transformed, skipping: {identifier}")
                skip_count += 1
                continue

            # Step 3: Download file from landing zone
            file_content = download_file_from_minio(minio_client, record["file_path"])
            if file_content is None:
                error_count += 1
                continue

            # Step 4: Transform the file (clean HTML or pass-through PDF)
            transformed_content, new_file_hash = transform_file(record, file_content)

            # Step 5: Upload to transformed zone
            upload_to_transformed_zone(
                minio_client, new_file_name, transformed_content, file_ext
            )

            # Step 6: Store metadata in transformed collection
            store_transformed_metadata(
                transformed_collection, record, new_file_path, new_file_hash
            )

            success_count += 1
            logger.info(f"Transformed: {identifier}")

        except Exception as e:
            error_count += 1
            logger.error(f"Error transforming {identifier}: {e}")

    # Summary
    logger.info(
        f"Transformation complete: {success_count} transformed, "
        f"{skip_count} skipped, {error_count} errors, "
        f"{len(records)} total records"
    )


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    args = parse_args()
    run_transformation(args.start_date, args.end_date)
