import uuid
from datetime import datetime, timezone


class Post:
    def __init__(self, link: str, title: str, summary: str, published: datetime, rss_feed_id: int, post_id: uuid = None,
                 created: datetime = None, read: bool = False, saved: bool = False, embeddings: list[float] = []):

        if post_id is None:
            post_id = uuid.uuid4()

        if created is None:
            created = datetime.now().astimezone(timezone.utc)

        self.id = post_id
        self.link = link
        self.title = title
        self.summary = summary
        self.published = published
        self.created = created
        self.rss_feed_id = rss_feed_id
        self.read = read
        self.saved = saved
        self.embeddings = embeddings

        self.rss_feed = None

    def __str__(self):
        return f"[{self.id}] {self.title}"
