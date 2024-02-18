from datetime import datetime, timezone


class Post:
    def __init__(self, link: str, title: str, summary: str, published: datetime, rss_feed_id: int, post_id: int = -1,
                 created: datetime = None, ai_fileid: str = None, saved: bool = False):

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
        self.ai_fileid = ai_fileid
        self.saved = saved

        self.rss_feed = None

    def __str__(self):
        return f"[{self.id}] {self.title}"
