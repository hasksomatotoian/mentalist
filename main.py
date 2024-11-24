import logging
import json

from model.area import Area
from model.post import Post
from model.rss_feed import RssFeed
from model.topic import Topic
from services.config_service import ConfigService
from services.database_service import DatabaseService
from services.rss_feed_service import RssFeedService
from services.llm_proxy import LlmProxy


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
                area.rss_feeds.append(RssFeed(area_id=area.id, link=rss_feed_json))
            areas.append(area)
    return areas


def create_topics_from_unread_posts(unread_posts: list[Post], db_service: DatabaseService, llm_proxy: LlmProxy) -> list[Topic]:
    grouped_posts = {}

    logging.info(f"Grouping {len(unread_posts)} unread posts...")
    for post in unread_posts:
        grouped_posts[post] = db_service.get_similar_unread_posts(post)

    logging.info(f"Sorting {len(grouped_posts)} unread post groups...")
    sorted_posts = dict(sorted(grouped_posts.items(), key=lambda item: len(item[1]) if item[1] is not None else 0, reverse=True))

    logging.info(f"Creating topics from {len(grouped_posts)} posts...")
    topics = []

    for post in sorted_posts:
        # Find topic that already contains this post
        post_topic = next((topic for topic in topics if any(p.id == post.id for p in topic.posts)), None)
        if not post_topic:
            post_topic = Topic(post.area_id, post.title, post.summary)
            post_topic.posts.append(post)
            topics.append(post_topic)

        for sub_post in sorted_posts[post]:
            sub_post_topic = next((topic for topic in topics if any(p.id == sub_post.id for p in topic.posts)), None)
            if not sub_post_topic:
                post_topic.posts.append(sub_post)

    logging.info(f"Getting title and summary for {len(topics)} topics...")
    for topic in topics:
        if len(topic.posts) > 1:
            topic_title, topic_summary = llm_proxy.get_topic_title_and_summary(topic.posts)
        else:
            post = topic.posts[0]
            topic_title = post.title
            topic_summary = post.summary
        if topic_title and topic_summary:
            topic.title = topic_title
            topic.summary = topic_summary

    return topics


def process_new_posts(rss_feed_service: RssFeedService, llm_proxy: LlmProxy, db_service: DatabaseService):
    new_posts = rss_feed_service.get_new_posts()
    new_posts_with_embeddings = llm_proxy.add_embeddings_to_posts(new_posts)

    if len(new_posts) > 0:
        logging.info(f"Storing {len(new_posts_with_embeddings)} new posts to DB...")
        db_service.add_posts(new_posts_with_embeddings)

    unread_posts = db_service.get_unread_posts()

    new_topics = create_topics_from_unread_posts(unread_posts, db_service, llm_proxy)
    new_topics_with_embeddings = llm_proxy.add_embeddings_to_topics(new_topics)

    db_service.delete_unread_topics()
    db_service.add_topics(new_topics_with_embeddings)

    # update_unread_topics_with_parent_topic(llm_proxy, db_service)
    add_ai_rating_to_unread_topics(db_service)


def update_unread_topics_with_parent_topic(llm_proxy: LlmProxy, db_service: DatabaseService):
    unread_topics = db_service.get_unread_topics(True)
    for topic in unread_topics:
        similar_read_topic = db_service.get_similar_read_topic(topic)
        if similar_read_topic:
            topic.parent_id = similar_read_topic.id
            topic_title, topic_summary, topic_update_summary = llm_proxy.get_topic_title_and_summaries(topic.posts, similar_read_topic.posts)
            if topic_title and topic_summary and topic_update_summary:
                topic.title = topic_title
                topic.summary = topic_summary
                topic.update_summary = topic_update_summary
                db_service.update_topic(topic)
                print(f"{topic.title}\n{topic.update_summary}\n\t{similar_read_topic.title}\n{similar_read_topic.summary}\n")
        elif topic.parent_id:
            topic.parent_id = None
            db_service.update_topic(topic)


def add_ai_rating_to_unread_topics(db_service: DatabaseService):
    unread_topics = db_service.get_unread_topics(True)
    logging.info(f"Adding AI rating to {len(unread_topics)} unread topics...")
    for topic in unread_topics:
        ai_rating = db_service.get_rating_from_similar_read_topics(topic)
        if ai_rating is None:
            ai_rating = min(len(topic.posts) * 5 + 25, 60)
        if topic.ai_rating != ai_rating:
            topic.ai_rating = ai_rating
            db_service.update_topic(topic)


def display_unread_topics(db_service: DatabaseService):
    unread_topics = db_service.get_unread_topics(True)
    for topic in unread_topics:
        print(f"{topic.title}\n{topic.summary}")
        for post in topic.posts:
            print(f"\t{post.title}")


if __name__ == '__main__':
    cfg_service = ConfigService()

    db_service = DatabaseService(cfg_service)
    db_service.import_areas(load_areas_json())

    llm_proxy = LlmProxy(cfg_service)

    rss_feed_service = RssFeedService(db_service)

    # db_service.delete_unread_posts()

    process_new_posts(rss_feed_service, llm_proxy, db_service)

    # update_unread_topics_with_parent_topic(llm_proxy, db_service)

    # add_ai_rating_to_unread_topics(db_service)
    # display_unread_topics(db_service)


    # db_service.update_topic_rating_and_mark_as_read(uuid.UUID('babc6833-7e41-44f6-9167-8567d760f972'), 40)
    # db_service.update_topic_rating_and_mark_as_read(uuid.UUID('935d9460-a200-4078-bcee-e0aaf019370f'), 40)
    # db_service.update_topic_rating_and_mark_as_read(uuid.UUID('af5723bf-d66f-4042-b7ec-5c4684b08db8'), 50)

    # topics = db_service.get_unread_topics(True)
    # for topic in topics:
    #     # db_service.update_topic_rating_and_mark_as_read(topic.id, 60)
    #     print(f"{topic.id}\t{topic.title}\n{topic.summary}")

