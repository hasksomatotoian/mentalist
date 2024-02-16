from datetime import datetime


class Topic:
    def __init__(self, title: str, summary: str, topic_id: int = None, latest_post_published: datetime = None,
                 best_post_ai_rating: int = None):
        self.id = topic_id
        self.title = title
        self.summary = summary
        self.latest_post_published = latest_post_published
        self.best_post_ai_rating = best_post_ai_rating
        self.posts = []

    def __str__(self):
        return f"[{self.id}] {self.title}"
