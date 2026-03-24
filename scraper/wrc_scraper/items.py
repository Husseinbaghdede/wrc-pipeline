"""
Scrapy Item definition for WRC decisions.

Each field maps directly to a piece of data we extract from the search
results page or the document page itself. These fields end up as a
document in MongoDB.
"""

import scrapy


class DecisionItem(scrapy.Item):
    # --- From the search results page ---
    identifier = scrapy.Field()       # e.g. "ADJ-00054658" or "LCR23235"
    title = scrapy.Field()            # Display title from the result card heading
    description = scrapy.Field()      # e.g. "Employee v Health Service"
    published_date = scrapy.Field()   # e.g. "17/07/2025"
    ref_no = scrapy.Field()           # e.g. "ADJ-00054658"
    doc_url = scrapy.Field()          # Full URL to the document page
    body = scrapy.Field()             # e.g. "Labour Court"

    # --- Added by our partitioning logic ---
    partition_date = scrapy.Field()   # e.g. "2024-01" (year-month of the partition)

    # --- Added after downloading the document ---
    file_path = scrapy.Field()        # Path in MinIO, e.g. "landing-zone/LCR23235.html"
    file_hash = scrapy.Field()        # SHA256 hash of the downloaded file
    file_type = scrapy.Field()        # "html" or "pdf" or "doc"
