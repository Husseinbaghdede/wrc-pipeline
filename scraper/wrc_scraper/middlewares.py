"""
Custom Scrapy downloader middlewares.

RotateUserAgentMiddleware: picks a random User-Agent from the list in
settings.py for each outgoing request. This prevents the server from
fingerprinting all requests as coming from the same browser session,
which is a common bot-detection signal.
"""

import random


class RotateUserAgentMiddleware:
    """Rotate User-Agent header on every request."""

    def __init__(self, user_agents):
        self.user_agents = user_agents

    @classmethod
    def from_crawler(cls, crawler):
        user_agents = crawler.settings.getlist("ROTATING_USER_AGENTS", [])
        if not user_agents:
            # Fallback to default USER_AGENT if list not configured
            user_agents = [crawler.settings.get("USER_AGENT")]
        return cls(user_agents)

    def process_request(self, request, spider):
        request.headers["User-Agent"] = random.choice(self.user_agents)
