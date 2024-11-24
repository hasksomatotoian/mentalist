import uuid
from datetime import datetime, timezone

from model.post import Post
from services.config_service import ConfigService
import logging

from services.database_service import DatabaseService

cfg_service = ConfigService()
logging.basicConfig(level=cfg_service.logging_level, format=cfg_service.logging_format)

db_service = DatabaseService(cfg_service)

posts: list[Post] = [
    Post("http://" + str(uuid.uuid4()), "Title", "", datetime.now().astimezone(timezone.utc), 1)
]
# db_service.add_posts(posts)

db_service.get_posts()

