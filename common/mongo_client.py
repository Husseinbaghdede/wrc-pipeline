"""
MongoDB connection helper.

Provides a reusable function to get a MongoDB client and database.
Used by both the Scrapy pipeline (storing metadata) and the
transformation script (reading/writing metadata).
"""

from pymongo import MongoClient
from common.config import MONGO_URI, MONGO_DB_NAME


def get_mongo_db():
    """
    Returns a MongoDB database instance.

    Usage:
        db = get_mongo_db()
        db["landing_metadata"].insert_one({...})
    """
    client = MongoClient(MONGO_URI)
    return client[MONGO_DB_NAME]
