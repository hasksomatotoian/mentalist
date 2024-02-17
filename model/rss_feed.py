from datetime import datetime


class RssFeed:
    def __init__(self, link: str, rss_feed_id: int = -1, web_link: str = None, title: str = None,
                 last_update: datetime = None, last_error: str = None):
        self.id = rss_feed_id
        self.link = link
        self.web_link = web_link
        self.title = title
        self.last_update = last_update
        self.last_error = last_error

    def __str__(self):
        return f"[{self.id}] {self.title}"
