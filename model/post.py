from datetime import datetime, timezone

from model.post_status import PostStatus


class Post:
    def __init__(self, link: str, title: str, summary: str, published: datetime, rss_feed_id: int, post_id: int = -1,
                 created: datetime = None, status: PostStatus = PostStatus.INIT, filename: str = None,
                 last_error: str = None, ai_fileid: str = None, ai_rating: int = 0, ai_summary: str = None,
                 read: bool = False, saved: bool = False):

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
        self.status = status
        self.filename = filename
        self.last_error = last_error
        self.ai_fileid = ai_fileid
        self.ai_rating = ai_rating
        self.ai_summary = ai_summary
        self.read = read
        self.saved = saved

        self.rss_feed = None

    def __str__(self):
        return f"[{self.id}] {self.title} ({self.ai_rating})"
