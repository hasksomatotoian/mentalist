from datetime import datetime


class Topic:
    def __init__(self, area_id: int, title: str, summary: str, ai_rating: int, ai_analysis: str,
                 created: datetime, topic_id: int = None, my_rating: int = 0,
                 read: bool = False, saved: bool = False):
        self.id = topic_id
        self.area_id = area_id
        self.title = title
        self.summary = summary
        self.created = created
        self.my_rating = my_rating
        self.ai_rating = ai_rating
        self.ai_analysis = ai_analysis
        self.read = read
        self.saved = saved
        self.posts = []

    def __str__(self):
        return f"[{self.id}] {self.title}"
