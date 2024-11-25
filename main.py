import json

from model.area import Area
from model.post import Post
from model.rss_feed import RssFeed
from services.config_service import ConfigService
from services.database_service import DatabaseService
from services.openai_service import OpenAiService
from services.rss_feed_service import RssFeedService
import logging
from langchain_ollama import OllamaEmbeddings


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


def store_posts(posts: list[Post], db_service: DatabaseService):
    logging.info(f"Connecting to {cfg_service.ollama_base_url}...")

    embeddings = OllamaEmbeddings(base_url=cfg_service.ollama_base_url,
                                  model=cfg_service.embeddings_model)

    batch_start = 0
    BATCH_SIZE = 10

    while batch_start < len(posts):
        batch_end = batch_start + BATCH_SIZE
        if batch_end > len(posts):
            batch_end = len(posts)

        logging.info(f"Batch: {batch_start}..{batch_end - 1}")

        documents = []
        for index in range(batch_start, batch_end):
            documents.append(f"Title: {posts[index].title}\n\n{posts[index].summary}")

        logging.info(f"Calculating embeddings for {len(documents)} posts...")
        post_embeddings = embeddings.embed_documents(documents)
        batch_posts = []
        for index in range(len(documents)):
            posts[batch_start + index].embeddings = post_embeddings[index]
            batch_posts.append(posts[batch_start + index])

        logging.info(f"Storing {len(batch_posts)} to vector DB...")
        db_service.add_posts(batch_posts)

        batch_start = batch_end


if __name__ == '__main__':
    cfg_service = ConfigService()
    logging.basicConfig(level=cfg_service.logging_level, format=cfg_service.logging_format)

    db_service = DatabaseService(cfg_service)
    db_service.import_areas(load_areas_json())

    # rss_feed_service = RssFeedService(db_service)
    # latest_posts = rss_feed_service.get_latest_posts()
    #
    # store_posts(latest_posts, db_service)

    stored_posts = db_service.get_posts()
    for post in stored_posts:
        print(post.title)
        db_service.get_posts_by_embeddings(post.embeddings)
        logging.info(post)

    # openai_service = OpenAiService(database_service=db_service, config_service=cfg_service)
    # openai_service.create_topics()
