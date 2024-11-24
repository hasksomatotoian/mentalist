import uuid
from datetime import datetime, timezone
from model.post import Post


class Topic:
    def __init__(self, area_id: int, title: str, summary: str, update_summary: str = '', ai_rating: int = -1,
                 created: datetime = None, topic_id: uuid = None, my_rating: int = -1,
                 read: bool = False, saved: bool = False, embeddings: list[float] = [], parent_id: uuid = None):

        if topic_id is None:
            topic_id = uuid.uuid4()

        if created is None:
            created = datetime.now().astimezone(timezone.utc)

        self.id = topic_id
        self.area_id = area_id
        self.title = title
        self.summary = summary
        self.update_summary = update_summary
        self.created = created
        self.my_rating = my_rating
        self.ai_rating = ai_rating
        self.read = read
        self.saved = saved
        self.embeddings = embeddings
        self.parent_id = parent_id
        self.parent_topic = None
        self.posts: list[Post] = []

    def __str__(self):
        return f"[{self.id}] {self.title}"
