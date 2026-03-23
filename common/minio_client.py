"""
MinIO connection helper.

Provides a reusable function to get a MinIO client.
Used by both the Scrapy pipeline (uploading files) and the
transformation script (reading/writing files).
"""

from minio import Minio
from common.config import MINIO_ENDPOINT, MINIO_ACCESS_KEY, MINIO_SECRET_KEY


def get_minio_client():
    """
    Returns a MinIO client instance.

    secure=False because we're connecting to a local Docker container
    over HTTP, not HTTPS. In production you'd set this to True.

    Usage:
        client = get_minio_client()
        client.put_object("landing-zone", "ADJ-00054658.html", data, length)
    """
    return Minio(
        MINIO_ENDPOINT,
        access_key=MINIO_ACCESS_KEY,
        secret_key=MINIO_SECRET_KEY,
        secure=False,
    )
