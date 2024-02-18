from datetime import datetime

from model.rss_feed import RssFeed


class AreaWeb:
    def __init__(self, area_id: int, title: str, number_of_unread_topics: int):
        self.id = area_id
        self.title = title
        self.number_of_unread_topics = number_of_unread_topics

    def __str__(self):
        return f"[{self.id}] {self.title}"
