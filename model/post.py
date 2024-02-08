from datetime import datetime, timezone

from model.post_status import PostStatus


class Post:
    def __init__(self, link: str, title: str, summary: str, published: datetime, rss_feed_id: int, post_id: int = -1,
                 created: datetime = None, status: PostStatus = PostStatus.INIT, filename: str = None,
                 last_error: str = None, ai_fileid: str = None, ai_rank: int = 0, ai_summary: str = None,
                 post_group_id: int = None):

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
        self.ai_rank = ai_rank
        self.ai_summary = ai_summary
        self.post_group_id = post_group_id

    def __str__(self):
        return f"[{self.id}] {self.title} ({self.ai_rank})"
