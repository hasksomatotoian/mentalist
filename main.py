import json

from model.area import Area
from model.rss_feed import RssFeed
from services.config_service import ConfigService
from services.database_service import DatabaseService
from services.openai_service import OpenAiService
from services.rss_feed_service import RssFeedService
import logging


def load_areas_json() -> list[Area]:
    areas = []
    with open(cfg_service.areas_filename, 'r') as areas_file:
        areas_json = json.load(areas_file)
        area_priority = 0
        for area_json in areas_json["areas"]:
            area_priority += 1
            area = Area(name=area_json["name"],
                        title=area_json["title"],
                        instructions_filename=area_json["instructions_filename"],
                        model=area_json["model"],
                        priority=area_priority)
            for rss_feed_json in area_json["rss_feeds"]:
                area.rss_feeds.append(RssFeed(link=rss_feed_json))
            areas.append(area)
    return areas


if __name__ == '__main__':
    cfg_service = ConfigService()
    logging.basicConfig(level=cfg_service.logging_level, format=cfg_service.logging_format)

    db_service = DatabaseService(cfg_service)
    db_service.import_areas(load_areas_json())

    rss_feed_service = RssFeedService(db_service)
    rss_feed_service.add_latest_posts()

    openai_service = OpenAiService(database_service=db_service, config_service=cfg_service)
    openai_service.create_topics()
