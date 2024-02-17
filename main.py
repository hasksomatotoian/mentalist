from services.config_service import ConfigService
from services.database_service import DatabaseService
from services.openai_service import OpenAiService
from services.rss_feed_service import RssFeedService
import logging

if __name__ == '__main__':
    cfg_service = ConfigService()
    logging.basicConfig(level=cfg_service.logging_level, format=cfg_service.logging_format)

    db_service = DatabaseService(cfg_service)

    rss_feed_service = RssFeedService(db_service)
    rss_feed_service.add_latest_posts()

    openai_service = OpenAiService(database_service=db_service, config_service=cfg_service)
    openai_service.create_topics()
