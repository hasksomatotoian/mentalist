import feedparser
import html
import logging

from datetime import datetime, timezone

from bs4 import BeautifulSoup

from model.post import Post
from services.database_service import DatabaseService


def _remove_self_promotion(summary: str) -> str:
    start = summary.find("\n<p>The post <a href=\"https://formulaspy.com")
    if start < 0:
        return summary
    return summary[:start]


def _remove_html(summary: str) -> str:
    soup = BeautifulSoup(summary, 'html.parser')
    return soup.get_text(separator=' ', strip=True)


class RssFeedService:
    def __init__(self, database_service: DatabaseService):
        self.database_service = database_service

    def get_latest_posts(self) -> list[Post]:
        posts = []
        logging.debug("Getting list of RSS feeds")
        rss_feeds = self.database_service.get_enabled_rss_feeds()
        logging.info(f"Found {len(rss_feeds)} RSS feeds")
        for rss_feed in rss_feeds:
            try:
                rss_feed.last_update = datetime.now().astimezone(timezone.utc)

                feed = feedparser.parse(rss_feed.link)

                rss_feed.title = feed.feed.title
                rss_feed.web_link = feed.feed.link

                logging.info(f"Processing {len(feed.entries)} post(s) from \"{rss_feed}\"")

                # Iterate through entries and print their titles and links
                for entry in feed.entries:
                    logging.debug(f"Processing post \"{entry.title}\"")

                    try:
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
                        post = Post(link=entry.link, title=html.unescape(entry.title),
                                    summary=_remove_html(_remove_self_promotion(html.unescape(entry.summary))),
                                    published=published, rss_feed_id=rss_feed.id, area_id=rss_feed.area_id, rss_feed=rss_feed)
                        posts.append(post)
                    except Exception as e:
                        logging.error(f"Error when parsing post \"{entry.title}\": {e}")

                rss_feed.last_error = None
            except Exception as e:
                rss_feed.last_error = f"{e}"
                logging.error(f"Error when parsing RSS feed \"{rss_feed}\": {e}")

            self.database_service.update_rss_feed(rss_feed)

        return posts
    
    def get_new_posts(self) -> list[Post]:
        posts = self.get_latest_posts()
        
        new_posts = []
        for post in posts:
            if self.database_service.get_post_by_link(post.link) is None:
                new_posts.append(post)

        logging.info(f"There are {len(new_posts)} new posts.")

        return new_posts
