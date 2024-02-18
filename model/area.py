from datetime import datetime

from model.rss_feed import RssFeed


class Area:
    def __init__(self, name: str, title: str, instructions_filename: str, model: str, priority: int,
                 assistant_id: int = None, needs_code_interpreter: bool = False, needs_retrieval: bool = False,
                 ai_id: str = None, ai_created: datetime = None, ai_last_update: datetime = None, checksum: str = None,
                 enabled: bool = True):

        self.id = assistant_id
        self.name = name
        self.title = title
        self.instructions_filename = instructions_filename
        self.model = model
        self.needs_code_interpreter = needs_code_interpreter
        self.needs_retrieval = needs_retrieval
        self.ai_id = ai_id
        self.ai_created = ai_created
        self.ai_last_update = ai_last_update
        self.checksum = checksum
        self.priority = priority
        self.enabled = enabled
        self.rss_feeds = []

    def __str__(self):
        return f"[{self.id}] {self.title})"
