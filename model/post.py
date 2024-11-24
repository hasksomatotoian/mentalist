import uuid
from datetime import datetime, timezone

from model.rss_feed import RssFeed


class Post:
    def __init__(self, link: str, title: str, summary: str, published: datetime, rss_feed_id: int, area_id: int, post_id: uuid = None,
                 created: datetime = None, read: bool = False, saved: bool = False, embeddings: list[float] = [],
                 rss_feed: RssFeed = None, topic_id: uuid = None):

        if post_id is None:
            post_id = uuid.uuid4()

        if created is None:
            created = datetime.now().astimezone(timezone.utc)

        if published is None:
            published = created

        self.id = post_id
        self.link = link
        self.title = title
        self.summary = summary
        self.published = published
        self.created = created
        self.rss_feed_id = rss_feed_id
        self.area_id = area_id
        self.read = read
        self.saved = saved
        self.embeddings = embeddings

        self.rss_feed = rss_feed
        self.topic_id = topic_id

    def __str__(self):
        return f"[{self.id}] {self.title}"

    def get_published_ago(self):
        time_diff = (datetime.now().astimezone(timezone.utc) - self.published.astimezone(timezone.utc)).total_seconds()
        if time_diff < 3600:
            return f"{int(time_diff / 60)} minutes ago"
        elif time_diff < 86400:
            return f"{int(time_diff / 3600)} hours ago"
        else:
            return f"{int(time_diff / 86400)} days ago"

