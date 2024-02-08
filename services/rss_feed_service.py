import feedparser
import html
import logging

from datetime import datetime, timezone
from model.post import Post
from services.database_service import DatabaseService


class RssFeedService:
    def __init__(self, database_service: DatabaseService):
        self.database_service = database_service

    def get_latest_posts(self):
        logging.debug("Getting list of RSS feeds")
        rss_feeds = self.database_service.get_all_rss_feeds()
        logging.info(f"Found {len(rss_feeds)} RSS feeds")
        for rss_feed in rss_feeds:
            try:
                rss_feed.last_update = datetime.now().astimezone(timezone.utc)

                feed = feedparser.parse(rss_feed.link)

                rss_feed.title = feed.feed.title

                logging.info(f"Processing new posts from \"{rss_feed}\"")

                # Iterate through entries and print their titles and links
                for entry in feed.entries:
                    logging.debug(f"Processing post \"{entry.title}\"")

                    if 'published_parsed' in entry:
                        published = datetime(
                            year=entry.published_parsed.tm_year,
                            month=entry.published_parsed.tm_mon,
                            day=entry.published_parsed.tm_mday,
                            hour=entry.published_parsed.tm_hour,
                            minute=entry.published_parsed.tm_min,
                            second=entry.published_parsed.tm_sec
                        )
                    else:
                        published = None
                    post = Post(entry.link, html.unescape(entry.title), html.unescape(entry.summary),
                                published, rss_feed.id)
                    self.database_service.add_post(post)

                rss_feed.last_error = None
            except Exception as e:
                rss_feed.last_error = f"{e}"
                logging.error(f"Error when parsing RSS feed \"{rss_feed}\": {e}")

            self.database_service.update_rss_feed(rss_feed)
