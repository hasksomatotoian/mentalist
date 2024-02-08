from datetime import datetime


class PostGroup:
    def __init__(self, title: str, summary: str, post_group_id: int = None, latest_post_published: datetime = None,
                 best_post_ai_rank: int = None):
        self.id = post_group_id
        self.title = title
        self.summary = summary
        self.latest_post_published = latest_post_published
        self.best_post_ai_rank = best_post_ai_rank

    def __str__(self):
        return f"[{self.id}] {self.title}"
