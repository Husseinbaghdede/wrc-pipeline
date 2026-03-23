"""
Scrapy spider for WRC Decisions and Determinations.

How it works:
1. Receives start_date and end_date as arguments (e.g. "2024-01-01" to "2025-01-01")
2. Splits the date range into monthly partitions
3. For each month, queries each of the 4 bodies separately
4. Parses the paginated search results
5. Extracts metadata from each result card
6. Follows the "View Page" link to download the actual document
7. Yields a DecisionItem with all metadata + document content

Why scrape one body at a time?
- The test says "scrape from each of the bodies on the left side"
- It also lets us tag each record with which body it came from
- Smaller result sets per request = less chance of getting blocked

Why monthly partitions?
- The test says to "iterate on a time-period basis"
- Monthly is a good balance: not too many requests (daily), not too few (yearly)
- Each partition typically has a manageable number of results
"""

import scrapy
from scrapy.spidermiddlewares.httperror import HttpError
from datetime import datetime
from dateutil.relativedelta import relativedelta
from urllib.parse import urlencode

import sys
import os

# Add project root to path so we can import common.config
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..'))
from common.config import WRC_BASE_URL, WRC_SEARCH_URL, WRC_BODIES, RESULTS_PER_PAGE
from common.logging_config import setup_logging, ScrapeLogger

from wrc_scraper.items import DecisionItem


class DecisionsSpider(scrapy.Spider):
    name = "decisions"
    allowed_domains = ["www.workplacerelations.ie"]

    def __init__(self, start_date=None, end_date=None, *args, **kwargs):
        """
        Spider arguments (passed via -a flag):
            start_date: Start of date range, format YYYY-MM-DD
            end_date:   End of date range, format YYYY-MM-DD

        Example:
            scrapy crawl decisions -a start_date=2024-01-01 -a end_date=2025-01-01
        """
        super().__init__(*args, **kwargs)

        if not start_date or not end_date:
            raise ValueError("Both start_date and end_date are required. "
                             "Usage: scrapy crawl decisions -a start_date=2024-01-01 -a end_date=2025-01-01")

        self.start_date = datetime.strptime(start_date, "%Y-%m-%d")
        self.end_date = datetime.strptime(end_date, "%Y-%m-%d")

        # Set up structured JSON logging
        self.scrape_log = setup_logging("wrc_scraper")
        self.tracker = ScrapeLogger(self.scrape_log)

    def start_requests(self):
        """
        Generate initial requests for every (body, month) combination.

        For example, with start=2024-01-01, end=2024-04-01, and 4 bodies,
        this generates 4 bodies x 3 months = 12 initial search requests.
        """
        partitions = self._generate_monthly_partitions()

        for partition_start, partition_end, partition_label in partitions:
            for body_name, body_id in WRC_BODIES.items():
                # Log the start of each partition + body combination
                self.tracker.start_partition(partition_label, body_name)

                url = self._build_search_url(
                    from_date=partition_start,
                    to_date=partition_end,
                    body_id=body_id,
                    page=1,
                )
                yield scrapy.Request(
                    url=url,
                    callback=self.parse_search_results,
                    meta={
                        "body_name": body_name,
                        "body_id": body_id,
                        "partition_start": partition_start,
                        "partition_end": partition_end,
                        "partition_label": partition_label,
                        "page": 1,
                    },
                    dont_filter=True,
                )

    def parse_search_results(self, response):
        """
        Parse a single page of search results.

        Each result card is an <li class="each-item"> containing:
        - h2.title         → identifier (e.g. "ADJ-00054658")
        - span.date        → published date (e.g. "11/03/2026")
        - p.description    → case description
        - span.refNO       → reference number
        - a.btn-primary    → link to the document page

        After extracting metadata, we follow the doc link to download the
        actual document content (handled in parse_document).
        """
        body_name = response.meta["body_name"]
        partition_label = response.meta["partition_label"]

        # Select all result cards on this page
        results = response.css("li.each-item")

        if not results:
            self.logger.info(
                f"No results found for body={body_name}, "
                f"partition={partition_label}, page={response.meta['page']}"
            )
            return

        # Track how many records we found on this page
        self.tracker.record_found(partition_label, body_name, len(results))

        for card in results:
            # Extract metadata from the card using CSS selectors
            identifier = card.css("h2.title::attr(title)").get("").strip()
            published_date = card.css("span.date::text").get("").strip()
            description = card.css("p.description::attr(title)").get("").strip()
            ref_no = card.css("span.refNO::text").get("").strip()
            doc_link = card.css("a.btn-primary::attr(href)").get("")

            if not identifier or not doc_link:
                self.logger.warning(
                    f"Skipping card with missing data: identifier={identifier}, "
                    f"doc_link={doc_link}"
                )
                continue

            # Build full URL for the document
            doc_url = response.urljoin(doc_link)

            # Follow the document link to download the actual content
            yield scrapy.Request(
                url=doc_url,
                callback=self.parse_document,
                errback=self.handle_download_error,
                meta={
                    "item_data": {
                        "identifier": identifier,
                        "description": description,
                        "published_date": published_date,
                        "ref_no": ref_no,
                        "doc_url": doc_url,
                        "body": body_name,
                        "partition_date": partition_label,
                    }
                },
                dont_filter=True,
            )

        # --- Handle pagination ---
        # Check if there are more pages by looking for results count text
        # e.g. "Shows 1 to 10 of 562 results"
        yield from self._follow_next_page(response)

    def parse_document(self, response):
        """
        Handle the downloaded document.

        The response could be:
        - An HTML page (most WRC decisions) → save as .html
        - A PDF file → save as .pdf
        - A DOC file → save as .doc

        We detect the type from the Content-Type header, then yield the
        DecisionItem with the document body attached. The actual storage
        (MongoDB + MinIO) is handled by the Scrapy pipeline.
        """
        item_data = response.meta["item_data"]
        content_type = response.headers.get("Content-Type", b"").decode("utf-8", errors="ignore").lower()

        # Determine file type from Content-Type header
        if "pdf" in content_type:
            file_type = "pdf"
        elif "msword" in content_type or "officedocument" in content_type:
            file_type = "doc"
        else:
            file_type = "html"

        # Build the item with all metadata
        item = DecisionItem()
        item["identifier"] = item_data["identifier"]
        item["description"] = item_data["description"]
        item["published_date"] = item_data["published_date"]
        item["ref_no"] = item_data["ref_no"]
        item["doc_url"] = item_data["doc_url"]
        item["body"] = item_data["body"]
        item["partition_date"] = item_data["partition_date"]
        item["file_type"] = file_type

        # file_path and file_hash will be set by the pipeline
        # after storing the file in MinIO
        item["file_path"] = ""
        item["file_hash"] = ""

        # Attach the raw response body for the pipeline to store
        # We use meta instead of a field because binary data
        # shouldn't go into the Item (which gets serialized to MongoDB)
        item._response_body = response.body

        # Track successful scrape
        self.tracker.record_scraped(
            item_data["partition_date"], item_data["body"]
        )

        yield item

    def handle_download_error(self, failure):
        """
        Handle failed document downloads.

        Logs the failure with URL, error code, and reason so that every
        failed record is accounted for in the structured logs.
        """
        request = failure.request
        item_data = request.meta.get("item_data", {})
        url = request.url
        partition = item_data.get("partition_date", "unknown")
        body = item_data.get("body", "unknown")

        # Extract error details
        if failure.check(HttpError):
            response = failure.value.response
            error_code = response.status
            reason = f"HTTP {response.status}"
        else:
            error_code = 0
            reason = str(failure.value)

        self.tracker.record_failed(partition, body, url, error_code, reason)

    def closed(self, reason):
        """Called when the spider finishes. Produces the final summary log."""
        self.tracker.summary()

    def _follow_next_page(self, response):
        """
        Handle pagination by checking if more results exist.

        The page shows "Shows 1 to 10 of 562 results".
        We parse the total count and current page to decide if there's a next page.
        """
        # Extract the results count text, e.g. "Shows 1 to 10 of 562 results"
        # This text lives in <div class="searchhead"> above the results list
        count_text = response.css("div.searchhead").re_first(
            r"of\s+([\d,]+)\s+results"
        )

        if not count_text:
            # Fallback: search the entire page for the count text
            count_text = response.re_first(r"of\s+([\d,]+)\s+results")

        if count_text:
            total_results = int(count_text.replace(",", ""))
            current_page = response.meta["page"]
            total_pages = (total_results + RESULTS_PER_PAGE - 1) // RESULTS_PER_PAGE

            if current_page < total_pages:
                next_page = current_page + 1
                next_url = self._build_search_url(
                    from_date=response.meta["partition_start"],
                    to_date=response.meta["partition_end"],
                    body_id=response.meta["body_id"],
                    page=next_page,
                )
                yield scrapy.Request(
                    url=next_url,
                    callback=self.parse_search_results,
                    meta={
                        **response.meta,
                        "page": next_page,
                    },
                    dont_filter=True,
                )

    def _generate_monthly_partitions(self):
        """
        Split the date range into monthly partitions.

        Example: start=2024-01-01, end=2024-04-01 produces:
            ("1/1/2024", "31/1/2024", "2024-01")
            ("1/2/2024", "29/2/2024", "2024-02")
            ("1/3/2024", "31/3/2024", "2024-03")

        Why monthly?
        - Recommended in the test as an example
        - Good balance between granularity and number of requests
        - Each month typically has <500 results per body = manageable
        """
        partitions = []
        current = self.start_date.replace(day=1)  # Normalize to 1st of month

        while current < self.end_date:
            # Partition start: 1st of current month
            p_start = current

            # Partition end: last day of current month, or end_date if sooner
            p_end = current + relativedelta(months=1) - relativedelta(days=1)
            if p_end > self.end_date:
                p_end = self.end_date

            # Label for this partition: "2024-01", "2024-02", etc.
            label = current.strftime("%Y-%m")

            # Format dates as d/m/yyyy for the WRC URL
            # Using f-string with .day/.month instead of strftime("%-d")
            # because %-d is not supported on Windows
            from_str = f"{p_start.day}/{p_start.month}/{p_start.year}"
            to_str = f"{p_end.day}/{p_end.month}/{p_end.year}"

            partitions.append((from_str, to_str, label))

            # Move to next month
            current += relativedelta(months=1)

        self.logger.info(f"Generated {len(partitions)} monthly partitions")
        return partitions

    def _build_search_url(self, from_date, to_date, body_id, page=1):
        """
        Build the WRC search URL with query parameters.

        Example output:
        https://www.workplacerelations.ie/en/search/?decisions=1&from=1/1/2024&to=31/1/2024&body=3&pageNumber=2

        Parameters are NOT URL-encoded for dates because the site expects
        plain d/m/yyyy format (we verified this from the browser URL bar).
        """
        params = {
            "decisions": "1",
            "from": from_date,
            "to": to_date,
            "body": body_id,
        }
        if page > 1:
            params["pageNumber"] = str(page)

        return f"{WRC_SEARCH_URL}?{urlencode(params)}"
