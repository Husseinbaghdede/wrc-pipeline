"""
Scrapy Pipelines — handles storing data after the spider yields an item.

How Scrapy pipelines work:
- The spider yields a DecisionItem
- Scrapy passes it through each pipeline in order (set in settings.py)
- MinIOPipeline runs first (order 300): uploads file, calculates hash
- MongoDBPipeline runs second (order 400): stores metadata in MongoDB

Pipeline order matters because MinIOPipeline sets file_path and file_hash
on the item, and MongoDBPipeline needs those values when storing metadata.
"""

import hashlib
import logging
from io import BytesIO

from scrapy.exceptions import DropItem
from minio.error import S3Error

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
from common.config import (
    MINIO_LANDING_BUCKET,
    MONGO_LANDING_COLLECTION,
)
from common.mongo_client import get_mongo_db
from common.minio_client import get_minio_client

logger = logging.getLogger(__name__)


class MinIOPipeline:
    """
    Uploads downloaded files (HTML/PDF/DOC) to MinIO object storage.

    What it does:
    1. Takes the raw file content from the spider
    2. Calculates SHA256 hash of the file
    3. Checks if a file with the same hash already exists (idempotency)
    4. If new or changed: uploads to MinIO
    5. Sets file_path and file_hash on the item for MongoDB to store
    """

    def open_spider(self, spider):
        """Called once when the spider starts. Sets up the MinIO client."""
        self.client = get_minio_client()
        self._ensure_bucket_exists(MINIO_LANDING_BUCKET)

    def _ensure_bucket_exists(self, bucket_name):
        """Create the bucket if it doesn't exist yet."""
        if not self.client.bucket_exists(bucket_name):
            self.client.make_bucket(bucket_name)
            logger.info(f"Created MinIO bucket: {bucket_name}")

    def process_item(self, item, spider):
        """
        Process each item: upload file to MinIO.

        The file content was attached to the item by the spider as
        item._response_body (raw bytes from the HTTP response).
        """
        # Get the raw file content from the spider
        file_content = getattr(item, '_response_body', None)
        if not file_content:
            raise DropItem(f"No file content for {item['identifier']}")

        # Calculate SHA256 hash of the file content
        # This is used for:
        # 1. Deduplication: skip upload if file hasn't changed
        # 2. Stored in MongoDB so we can detect changes on re-runs
        file_hash = hashlib.sha256(file_content).hexdigest()

        # Build the file path in MinIO
        # Format: identifier.ext (e.g. "ADJ-00054658.html")
        file_ext = item["file_type"]
        file_name = f"{item['identifier']}.{file_ext}"
        file_path = f"{MINIO_LANDING_BUCKET}/{file_name}"

        # Set values on the item (MongoDBPipeline needs these)
        item["file_hash"] = file_hash
        item["file_path"] = file_path

        # Check if this exact file already exists (idempotency)
        # We check by trying to get the object's metadata
        try:
            existing = self.client.stat_object(MINIO_LANDING_BUCKET, file_name)
            # File exists — check if content changed by comparing hash
            # We store the hash in the object's metadata
            existing_hash = existing.metadata.get("x-amz-meta-file_hash", "")
            if existing_hash == file_hash:
                logger.info(
                    f"File unchanged, skipping upload: {file_name} "
                    f"(hash={file_hash[:12]}...)"
                )
                return item
        except S3Error:
            # File doesn't exist yet — proceed with upload
            pass

        # Upload the file to MinIO
        data = BytesIO(file_content)
        self.client.put_object(
            bucket_name=MINIO_LANDING_BUCKET,
            object_name=file_name,
            data=data,
            length=len(file_content),
            content_type=self._get_content_type(file_ext),
            metadata={"file_hash": file_hash},
        )
        logger.info(f"Uploaded to MinIO: {file_name} ({len(file_content)} bytes)")

        return item

    def _get_content_type(self, file_ext):
        """Map file extension to MIME type for proper storage."""
        content_types = {
            "html": "text/html",
            "pdf": "application/pdf",
            "doc": "application/msword",
        }
        return content_types.get(file_ext, "application/octet-stream")


class MongoDBPipeline:
    """
    Stores decision metadata in MongoDB.

    What it does:
    1. Takes the DecisionItem with all metadata + file_path + file_hash
    2. Checks if a record with this identifier already exists (idempotency)
    3. If new: inserts the record
    4. If exists but file changed: updates the record
    5. If exists and unchanged: skips

    Uses 'identifier' as the unique key for deduplication.
    """

    def open_spider(self, spider):
        """Called once when the spider starts. Sets up MongoDB connection."""
        self.db = get_mongo_db()
        self.collection = self.db[MONGO_LANDING_COLLECTION]

        # Create an index on 'identifier' for fast lookups and uniqueness
        self.collection.create_index("identifier", unique=True)
        logger.info(f"MongoDB connected, collection: {MONGO_LANDING_COLLECTION}")

    def process_item(self, item, spider):
        """
        Process each item: store or update metadata in MongoDB.

        Uses update_one with upsert=True:
        - If identifier doesn't exist → insert new document
        - If identifier exists → update with new data
        This makes the pipeline idempotent.
        """
        # Build the document to store
        doc = {
            "identifier": item["identifier"],
            "description": item["description"],
            "published_date": item["published_date"],
            "ref_no": item["ref_no"],
            "doc_url": item["doc_url"],
            "body": item["body"],
            "partition_date": item["partition_date"],
            "file_path": item["file_path"],
            "file_hash": item["file_hash"],
            "file_type": item["file_type"],
        }

        # Upsert: insert if new, update if exists
        result = self.collection.update_one(
            {"identifier": item["identifier"]},  # Find by identifier
            {"$set": doc},                        # Set all fields
            upsert=True,                          # Insert if not found
        )

        if result.upserted_id:
            logger.info(f"Inserted new record: {item['identifier']}")
        elif result.modified_count > 0:
            logger.info(f"Updated existing record: {item['identifier']}")
        else:
            logger.info(f"Record unchanged, skipped: {item['identifier']}")

        return item
