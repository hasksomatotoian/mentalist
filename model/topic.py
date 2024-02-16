from datetime import datetime


class Topic:
    def __init__(self, title: str, summary: str, topic_id: int = None, latest_post_published: datetime = None,
                 best_post_ai_rating: int = None, my_rating: int = 0, ai_rating: int = 0, ai_analysis: str = None,
                 read: bool = False, saved: bool = False):
        self.id = topic_id
        self.title = title
        self.summary = summary
        self.latest_post_published = latest_post_published
        self.best_post_ai_rating = best_post_ai_rating
        self.my_rating = my_rating
        self.ai_rating = ai_rating
        self.ai_analysis = ai_analysis
        self.read = read
        self.saved = saved
        self.posts = []

    def __str__(self):
        return f"[{self.id}] {self.title}"
