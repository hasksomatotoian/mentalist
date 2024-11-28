import json

from model.area import Area
from model.post import Post
from model.rss_feed import RssFeed
from model.topic import Topic
from services.config_service import ConfigService
from services.database_service import DatabaseService
from services.openai_service import OpenAiService
from services.rss_feed_service import RssFeedService
import logging
from langchain_ollama import OllamaEmbeddings, OllamaLLM
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import OpenAIEmbeddings

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

    embeddings = OllamaEmbeddings(base_url=cfg_service.ollama_base_url, model=cfg_service.embeddings_model)
    # embeddings = OpenAIEmbeddings()

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

def get_topic_title_and_summary(posts: list[Post]) -> (str, str):
    template = """Summaries: {summaries}

    Answer: Create a title and an overall summary from the list of summaries which you got.
    The title should be on the first line of the response. Title should be as short as possible, ideally between 3 and 5 words.
    The overall summary should be one paragraph long, and should be also as short as possible, with at most five sentences.
    Focus on facts, not on opinions or sentiment.
    The response must not contain anything else than the title and the summary."""
    prompt = ChatPromptTemplate.from_template(template)
    keywords_model = OllamaLLM(base_url=cfg_service.ollama_base_url, model=cfg_service.keywords_model)
    chain = prompt | keywords_model

    summaries = ""
    for post in posts:
        summaries += f"{post.title}\n{post.summary}\n\n"

    result = chain.invoke({"summaries": f"{summaries}"}).splitlines()

    return result[0], result[-1]


def store_new_posts(db_service: DatabaseService):
    rss_feed_service = RssFeedService(db_service)
    latest_posts = rss_feed_service.get_latest_posts()

    new_posts = []
    for post in latest_posts:
        if db_service.get_post_id_by_link(post.link) is None:
            new_posts.append(post)

    store_posts(new_posts, db_service)


def create_topics_from_unread_posts(db_service: DatabaseService) -> list[Topic]:
    grouped_posts = {}

    unread_posts = db_service.get_unread_posts()
    logging.info(f"Grouping {len(unread_posts)} unread posts...")
    for post in unread_posts:
        grouped_posts[post] = db_service.get_similar_unread_posts(post)

    logging.info(f"Sorting {len(grouped_posts)} unread post groups...")
    sorted_posts = dict(sorted(grouped_posts.items(), key=lambda item: len(item[1]) if item[1] is not None else 0, reverse=True))

    logging.info(f"Creating topics...")
    posts_x_topics = {}
    topics_x_posts = []

    for post in sorted_posts.keys():
        if post.id in posts_x_topics:
            topics_x_posts_index = posts_x_topics[post.id]
        else:
            topics_x_posts.append({})
            topics_x_posts_index = len(topics_x_posts) - 1
            posts_x_topics[post.id] = topics_x_posts_index

        for sub_post in sorted_posts[post]:
            topics_x_posts[topics_x_posts_index][sub_post.id] = sub_post
            posts_x_topics[sub_post.id] = topics_x_posts_index

    topics = []
    for topic_x_posts in topics_x_posts:
        if len(topic_x_posts) < 0:
            continue
        if len(topic_x_posts) > 1:
            topic_title, topic_summary = get_topic_title_and_summary(topic_x_posts.values())
        else:
            post = topic_x_posts
            topic_title = topic_x_posts[0].title
            topic_summary = topic_x_posts[0].summary

        topic = Topic(-1, topic_title, topic_summary)
        topics.append(topic)

        print(f"{topic.title}\n{topic.summary}")
        for post in topic_x_posts.values():
            print(f"\t{post.title}")

    return topics

if __name__ == '__main__':
    cfg_service = ConfigService()

    db_service = DatabaseService(cfg_service)
    db_service.import_areas(load_areas_json())

    store_new_posts(db_service)
    topics = create_topics_from_unread_posts(db_service)

    logging.info(f"Displaying {len(topics)} topics...")
    for topic in topics:
        if len(topic.values()) > 1:
            print(get_topic_title_and_summary(topic.values()))
            prefix = "\t"
        else:
            prefix = ''
        for post in topic.values():
            print(f"{prefix}{post.title}")
            prefix = "\t"

    # openai_service = OpenAiService(database_service=db_service, config_service=cfg_service)
    # openai_service.create_topics()
