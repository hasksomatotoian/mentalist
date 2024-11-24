import os
import sqlite3
import uuid

from datetime import datetime
from sqlite3 import Cursor

from chromadb.api.types import IncludeEnum

from model.area import Area
from model.area_web import AreaWeb
from model.post import Post
from model.topic import Topic
from model.rss_feed import RssFeed
from services.config_service import ConfigService
import chromadb
from typing import Mapping, Union, List


# region Helper Methods

def _datetime_to_text(datetime_value: datetime) -> str | None:
    if datetime_value is None:
        return None
    else:
        return datetime_value.strftime('%Y-%m-%dT%H:%M:%S')


def _text_to_datetime(text_value: str) -> datetime | None:
    if text_value is None:
        return None
    else:
        return datetime.strptime(text_value, '%Y-%m-%dT%H:%M:%S')


def _bool_to_int(bool_value: bool) -> int | None:
    if bool_value is None:
        return None
    else:
        return 1 if bool_value else 0


def _int_to_bool(int_value: int) -> bool | None:
    if int_value is None:
        return None
    else:
        return int_value != 0


def _post_to_metadata(post: Post) -> Mapping[str, Union[str, int, float, bool]]:
    return {
        "table": "post",
        "link": post.link,
        "title": post.title,
        "published": _datetime_to_text(post.published),
        "created": _datetime_to_text(post.created),
        "rss_feed_id": post.rss_feed_id,
        "read": post.read,
        "saved": post.saved,
        "topic_id": str(post.topic_id) if post.topic_id else '',
        "area_id": post.area_id
    }


def _metadata_to_post(post_id: uuid, summary: str, embeddings: List[float],
                      metadata: Mapping[str, Union[str, int, float, bool]]) -> Post:
    post = Post(link=metadata["link"],
                title=metadata["title"],
                summary=summary,
                published=_text_to_datetime(metadata["published"]),
                rss_feed_id=metadata["rss_feed_id"],
                post_id=post_id,
                created=_text_to_datetime(metadata["created"]),
                read=metadata["read"],
                saved=metadata["saved"],
                embeddings=embeddings,
                topic_id=uuid.UUID(metadata["topic_id"]) if metadata["topic_id"] != '' else None,
                area_id=metadata["area_id"])
    return post


def _topic_to_metadata(topic: Topic) -> Mapping[str, Union[str, int, float, bool]]:
    return {
        "table": "topic",
        "area_id": int(topic.area_id),
        "title": topic.title,
        "update_summary": topic.update_summary,
        "created": _datetime_to_text(topic.created),
        "my_rating": int(topic.my_rating),
        "ai_rating": int(topic.ai_rating),
        "read": bool(topic.read),
        "saved": bool(topic.saved),
        "parent_id": str(topic.parent_id) if topic.parent_id else ''
    }

def _metadata_to_topic(topic_id: uuid, summary: str, embeddings: List[float],
                      metadata: Mapping[str, Union[str, int, float, bool]]) -> Topic:
    topic = Topic(area_id=metadata["area_id"],
                 title=metadata["title"], 
                 summary=summary, 
                 update_summary=metadata["update_summary"],
                 created=_text_to_datetime(metadata["created"]), 
                 my_rating=int(metadata["my_rating"]),
                 ai_rating=int(metadata["ai_rating"]),
                 read=bool(metadata["read"]), 
                 saved=bool(metadata["saved"]),
                 topic_id=topic_id,
                 parent_id=uuid.UUID(metadata["parent_id"]) if "parent_id" in metadata.keys() and metadata["parent_id"] != '' else None)
    topic.embeddings = embeddings
    return topic

# endregion

class DatabaseService:

    # region _Private Methods

    def __init__(self, config_service: ConfigService):
        self.config_service = config_service

        if not os.path.exists(config_service.vector_db_path):
            os.makedirs(config_service.vector_db_path)
        self.vector_db = chromadb.PersistentClient(path=self.config_service.vector_db_path)
        self.vector_db_collection = self.vector_db.get_or_create_collection(self.config_service.vector_db_collection)

        self.connection = sqlite3.connect(self.config_service.database_filename)
        self.cursor = self.connection.cursor()
        self._create_db()

    def __del__(self):
        self.connection.close()

    def _create_db(self):
        self._execute_sql("""
            CREATE TABLE IF NOT EXISTS areas (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                title TEXT NOT NULL,
                instructions_filename TEXT NOT NULL,
                model TEXT NOT NULL,
                needs_code_interpreter INTEGER NOT NULL,
                needs_retrieval INTEGER NOT NULL,
                ai_id TEXT,
                ai_created TEXT,
                ai_last_update TEXT,
                checksum TEXT,
                priority INTEGER NOT NULL,
                enabled INTEGER NOT NULL
            );
        """)
        self._execute_sql("""
            CREATE TABLE IF NOT EXISTS rss_feeds (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                area_id INTEGER NOT NULL,
                link TEXT NOT NULL UNIQUE,
                web_link TEXT,
                title TEXT,
                last_update TEXT,
                last_error TEXT,
                enabled INTEGER NOT NULL
            );
        """)

    def _execute_sql(self, sql, data=None) -> Cursor:
        cursor = None
        try:
            if data is None:
                cursor = self.cursor.execute(sql)
            else:
                cursor = self.cursor.execute(sql, data)
            self.connection.commit()
        except sqlite3.Error as e:
            print(f"Database error: {e}\nSQL:{sql}")
            self.connection.rollback()
        except Exception as e:
            print(f"Exception in _query: {e}\nSQL:{sql}")
            self.connection.rollback()
        return cursor

    # endregion

    # region Area

    def import_areas(self, areas: list[Area]):
        self.disable_all_areas()
        self.disable_all_rss_feeds()

        for area in areas:
            existing_area = self.get_area_by_name(area.name)
            if existing_area is None:
                self.add_area(area)
                area_id = area.id
            else:
                existing_area.name = area.name
                existing_area.title = area.title
                existing_area.instructions_filename = area.instructions_filename
                existing_area.model = area.model
                existing_area.priority = area.priority
                existing_area.enabled = area.enabled
                self.update_area(existing_area)
                area_id = existing_area.id

            for rss_feed in area.rss_feeds:
                existing_rss_feed = self.get_rss_feed_by_link(rss_feed.link)
                if existing_rss_feed is None:
                    rss_feed.area_id = area_id
                    self.add_rss_feed(rss_feed)
                else:
                    existing_rss_feed.area_id = area_id
                    existing_rss_feed.enabled = True
                    self.update_rss_feed(existing_rss_feed)


    def add_area(self, area: Area):
        sql = """
            INSERT INTO areas
                (name, title, instructions_filename, model, needs_code_interpreter, needs_retrieval, 
                ai_id, ai_created, ai_last_update, checksum, priority, enabled)
            VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        data = (area.name, area.title, area.instructions_filename, area.model,
                _bool_to_int(area.needs_code_interpreter), _bool_to_int(area.needs_retrieval),
                area.ai_id, _datetime_to_text(area.ai_created), _datetime_to_text(area.ai_last_update),
                area.checksum, area.priority, _bool_to_int(area.enabled))
        cursor = self._execute_sql(sql, data)
        area.id = cursor.lastrowid


    def get_area_by_name(self, name: str) -> Area | None:
        areas = self._get_areas(f"name = '{name}'")
        if len(areas) > 0:
            return areas[0]
        return None


    def get_enabled_areas(self) -> list[Area]:
        return self._get_areas(f"enabled = {_bool_to_int(True)}", "priority, id")


    def get_areas_for_web(self) -> list[AreaWeb]:
        areas_for_web = [AreaWeb(area_id=0, title="All",
                                 number_of_unread_topics=0)]
        areas = self.get_enabled_areas()
        for area in areas:
            number_of_unread_topics = self.get_number_of_unread_topics(area.id)
            areas_for_web.append(AreaWeb(area_id=area.id, title=area.title,
                                         number_of_unread_topics=number_of_unread_topics))
            areas_for_web[0].number_of_unread_topics += number_of_unread_topics

        return areas_for_web


    def _get_areas(self, where: str, order_by: str = "priority, id") -> list[Area]:
        sql = f"""
            SELECT
                id, name, title, instructions_filename, model, needs_code_interpreter, needs_retrieval, 
                ai_id, ai_created, ai_last_update, checksum, priority, enabled
            FROM areas
            WHERE {where}
            ORDER BY {order_by}
        """
        self.cursor.execute(sql)
        rows = self.cursor.fetchall()

        areas = []
        for row in rows:
            areas.append(Area(area_id=row[0], name=row[1], title=row[2], instructions_filename=row[3],
                              model=row[4], needs_code_interpreter=_int_to_bool(row[5]),
                              needs_retrieval=_int_to_bool(row[6]), ai_id=row[7],
                              ai_created=_text_to_datetime(row[8]), ai_last_update=_text_to_datetime(row[9]),
                              checksum=row[10], priority=row[11], enabled=_int_to_bool(row[12])))
        return areas


    def update_area(self, area: Area):
        sql = """
            UPDATE areas SET 
                name=?, title=?, instructions_filename=?, model=?, needs_code_interpreter=?, needs_retrieval=?, 
                ai_id=?, ai_created=?, ai_last_update=?, checksum=?, priority=?, enabled=?
            WHERE id=?
        """
        data = (area.name, area.title, area.instructions_filename, area.model,
                _bool_to_int(area.needs_code_interpreter), _bool_to_int(area.needs_retrieval),
                area.ai_id, _datetime_to_text(area.ai_created), _datetime_to_text(area.ai_last_update),
                area.checksum, area.priority, _bool_to_int(area.enabled), area.id)
        self._execute_sql(sql, data)


    def disable_all_areas(self):
        sql = "UPDATE areas SET enabled=0"
        self._execute_sql(sql)

    # endregion

    # region Post

    def add_posts(self, posts: list[Post]):
        if not posts:
            return

        ids = []
        documents = []
        metadata: List[Mapping[str, Union[str, int, float, bool]]] = []
        embeddings: list[List[float]] = []

        for post in posts:
            ids.append(str(post.id))
            documents.append(post.summary)
            metadata.append(_post_to_metadata(post))
            embeddings.append(post.embeddings)

        self.vector_db_collection.add(
            ids=ids,
            embeddings=embeddings,
            documents=documents,
            metadatas=metadata
        )

        return


    def update_posts(self, posts: list[Post]):
        """Updates existing posts in the vector database in a single batch operation"""
        if not posts:
            return
            
        ids = []
        documents = []
        metadata = []
        embeddings = []

        for post in posts:
            ids.append(str(post.id))
            documents.append(post.summary)
            metadata.append(_post_to_metadata(post))
            embeddings.append(post.embeddings)

        self.vector_db_collection.update(
            ids=ids,
            embeddings=embeddings,
            documents=documents,
            metadatas=metadata
        )


    def delete_unread_posts(self):
        self.vector_db_collection.delete(
            where={"$and": [{"read": False}, {"table": "post"}]}
        )


    def get_unread_posts(self) -> list[Post]:
        return self._get_posts(
            {"$and": [{"read": False}, {"table": "post"}]})
    

    def get_posts_by_topic_id(self, topic_id: uuid, include_rss_feed: bool = False) -> list[Post]:
        return self._get_posts(
            {"$and": [{"topic_id": str(topic_id)}, {"table": "post"}]}, 
            include_rss_feed)


    def get_post_by_link(self, link: str) -> Post | None:
        posts = self._get_posts(
            where={"$and": [{"link": link}, {"table": "post"}]})
        
        if len(posts) < 1:
            return None

        return posts[0]
    

    def _get_posts(self, where: dict, include_rss_feed: bool = False) -> list[Post]:
        db_posts = self.vector_db_collection.get(
            where=where,
            include=[IncludeEnum.documents, IncludeEnum.metadatas, IncludeEnum.embeddings]
        )

        ids = db_posts["ids"]
        documents = db_posts["documents"]
        metadatas = db_posts["metadatas"]
        embeddings = db_posts["embeddings"]

        rss_feeds_cache = {}
        posts = []
        for index in range(len(ids)):
            post = _metadata_to_post(ids[index], documents[index], embeddings[index], metadatas[index])
            if include_rss_feed:
                if post.rss_feed_id not in rss_feeds_cache:
                    rss_feeds_cache[post.rss_feed_id] = self.get_rss_feed_by_id(post.rss_feed_id)
                post.rss_feed = rss_feeds_cache[post.rss_feed_id]
            posts.append(post)

        return posts


    def get_similar_unread_posts(self, post: Post) -> list[Post]:
        db_posts = self.vector_db_collection.query(
            where={"$and": [{"read": False}, {"table": "post"}, {"area_id": post.area_id}]},
            include=[IncludeEnum.documents, IncludeEnum.metadatas, IncludeEnum.embeddings, IncludeEnum.distances],
            query_embeddings=[post.embeddings],
            n_results=self.config_service.similar_posts_max_number
        )

        ids = db_posts["ids"][0]
        documents = db_posts["documents"][0]
        metadatas = db_posts["metadatas"][0]
        embeddings = db_posts["embeddings"][0]
        distances = db_posts["distances"][0]

        posts = []
        for index in range(len(ids)):
            if distances[index] <= self.config_service.similar_posts_max_distance:
                posts.append(_metadata_to_post(ids[index], documents[index], embeddings[index], metadatas[index]))

        return posts


    # endregion

    # region Topic

    def add_topics(self, topics: list[Topic]):
        documents = []
        ids = []
        metadata: List[Mapping[str, Union[str, int, float, bool]]] = []
        embeddings: list[List[float]] = []

        for topic in topics:
            ids.append(str(topic.id))
            documents.append(topic.summary)
            metadata.append(_topic_to_metadata(topic))

            embeddings.append(topic.embeddings)

        self.vector_db_collection.add(
            ids=ids,
            embeddings=embeddings,
            documents=documents,
            metadatas=metadata
        )

        posts = []
        for topic in topics:
            if topic.posts:
                for post in topic.posts:
                    post.topic_id = topic.id
                    posts.append(post)

        self.update_posts(posts)

        return


    def delete_unread_topics(self):
        self.vector_db_collection.delete(
            where={"$and": [{"read": False}, {"table": "topic"}]}
        )


    def get_unread_topics(self, include_posts: bool = False) -> list[Topic]:
        return self._get_topics(
            where={"$and": [{"read": False}, {"table": "topic"}]},
            include_posts=include_posts)
    

    def get_similar_read_topic(self, topic: Topic) -> Topic:
        db_posts = self.vector_db_collection.query(
            where={"$and": [{"read": True}, {"table": "topic"}, {"area_id": topic.area_id}]},
            include=[IncludeEnum.documents, IncludeEnum.metadatas, IncludeEnum.embeddings, IncludeEnum.distances],
            query_embeddings=[topic.embeddings],
            n_results=1,
        )

        ids = db_posts["ids"][0]
        documents = db_posts["documents"][0]
        metadatas = db_posts["metadatas"][0]
        embeddings = db_posts["embeddings"][0]
        distances = db_posts["distances"][0]

        for index in range(len(ids)):
            if distances[index] <= self.config_service.similar_topics_max_distance:
                topic = _metadata_to_topic(ids[index], documents[index], embeddings[index], metadatas[index])
                topic.posts = sorted(self.get_posts_by_topic_id(topic.id), key=lambda x: x.published, reverse=True)
                return topic

        return None


    def get_rating_from_similar_read_topics(self, topic: Topic) -> int:
        db_posts = self.vector_db_collection.query(
            where={"$and": [{"read": True}, {"table": "topic"}, {"area_id": topic.area_id}]},
            include=[IncludeEnum.metadatas, IncludeEnum.distances],
            query_embeddings=[topic.embeddings],
            n_results=self.config_service.similar_topics_for_rating_max_number,
        )

        metadatas = db_posts["metadatas"][0]
        distances = db_posts["distances"][0]

        total_rating = 0
        total_distance = 0
        for index in range(len(metadatas)):
            distance = distances[index]
            if distance < self.config_service.similar_topics_for_rating_max_distance:
                similar_topic = _metadata_to_topic(None, None, None, metadatas[index])
                if similar_topic.my_rating >= 0:
                    distance_weight = self.config_service.similar_topics_for_rating_max_distance - distance
                    total_rating += similar_topic.my_rating * distance_weight
                    total_distance += distance_weight

        return int(total_rating / total_distance) if total_distance > 0 else None


    def update_topic_rating_and_mark_as_read(self, topic_id: uuid, my_rating: int):
        db_topic = self.vector_db_collection.get(
            where={"table": "topic"},
            ids=[str(topic_id)],
            include=[IncludeEnum.documents, IncludeEnum.metadatas, IncludeEnum.embeddings]
        )
        
        if len(db_topic["ids"]) == 0:
            return
        
        topic = _metadata_to_topic(
            topic_id,
            db_topic["documents"][0],
            db_topic["embeddings"][0],
            db_topic["metadatas"][0]
        )
        
        topic.my_rating = my_rating
        topic.read = True
        
        # Update the topic
        self.vector_db_collection.update(
            ids=[str(topic_id)],
            embeddings=[topic.embeddings],
            documents=[topic.summary],
            metadatas=[_topic_to_metadata(topic)]
        )
        
        # Get and update all associated posts
        posts = self.get_posts_by_topic_id(topic_id)
        for post in posts:
            post.read = True
        
        self.update_posts(posts)


    def update_topic(self, topic: Topic):
        self.vector_db_collection.update(
            ids=[str(topic.id)],
            embeddings=[topic.embeddings],
            documents=[topic.summary],
            metadatas=[_topic_to_metadata(topic)]
        )


    def get_number_of_unread_topics(self, area_id: int) -> int:
        db_topics = self.vector_db_collection.get(
            where={"$and": [{"read": False}, {"table": "topic"}, {"area_id": area_id}]},
            include=[])
        return len(db_topics["ids"])
    

    def get_topics_for_view(self, area_id: int) -> list[Topic]:
        if area_id == 0:
            where = {"$and": [{"table": "topic"}, {"read": False}]}
        else:
            where = {"$and": [{"table": "topic"}, {"read": False}, {"area_id": area_id}]}

        topics = self._get_topics(where, include_posts=True, include_parent_topic=True)

        return sorted(topics, key=lambda x: x.ai_rating, reverse=True)
    
    def get_topic_by_id(self, topic_id: uuid) -> Topic:
        db_topic = self.vector_db_collection.get(
            where={"table": "topic"},
            ids=[str(topic_id)],
            include=[IncludeEnum.documents, IncludeEnum.metadatas, IncludeEnum.embeddings])
        return _metadata_to_topic(db_topic["ids"][0], db_topic["documents"][0], db_topic["embeddings"][0], db_topic["metadatas"][0])
    
    def _get_topics(self, where: dict, include_posts: bool = False, include_parent_topic: bool = False) -> list[Topic]:
        db_topics = self.vector_db_collection.get(
            where=where,
            include=[IncludeEnum.documents, IncludeEnum.metadatas, IncludeEnum.embeddings])
        
        topics = []
        for i in range(len(db_topics["ids"])):
            topic = _metadata_to_topic(
                db_topics["ids"][i], 
                db_topics["documents"][i], 
                db_topics["embeddings"][i],
                db_topics["metadatas"][i])
            
            if include_posts:
                topic.posts = sorted(self.get_posts_by_topic_id(topic.id, include_rss_feed=True), key=lambda x: x.published, reverse=True)
            if include_parent_topic and topic.parent_id:
                topic.parent_topic = self.get_topic_by_id(topic.parent_id)
            topics.append(topic)

        return topics

    # endregion

    # region RssFeed

    def add_rss_feed(self, rss_feed: RssFeed):
        sql = """
            INSERT OR IGNORE INTO rss_feeds(area_id, link, web_link, title, last_update, last_error, enabled)
            VALUES(?, ?, ?, ?, ?, ?, ?)
        """
        data = (rss_feed.area_id, rss_feed.link, rss_feed.web_link, rss_feed.title, _datetime_to_text(rss_feed.last_update),
                rss_feed.last_error, _bool_to_int(rss_feed.enabled))
        cursor = self._execute_sql(sql, data)
        rss_feed.id = cursor.lastrowid

    def update_rss_feed(self, rss_feed: RssFeed):
        sql = """
            UPDATE rss_feeds 
            SET area_id=?, link=?, web_link=?, title=?, last_update=?, last_error=?, enabled=?
            WHERE id=?
        """
        data = (
            rss_feed.area_id, rss_feed.link, rss_feed.web_link, rss_feed.title, _datetime_to_text(rss_feed.last_update),
            rss_feed.last_error, _bool_to_int(rss_feed.enabled), rss_feed.id)
        self._execute_sql(sql, data)

    def get_enabled_rss_feeds(self) -> list[RssFeed]:
        return self._get_rss_feeds(f"enabled = {_bool_to_int(True)}")

    def get_rss_feed_by_id(self, rss_feed_id: int) -> RssFeed | None:
        rss_feeds = self._get_rss_feeds(f"id={rss_feed_id}")
        if len(rss_feeds) < 1:
            return None
        return rss_feeds[0]

    def get_rss_feed_by_link(self, link: str) -> RssFeed | None:
        rss_feeds = self._get_rss_feeds(f"link='{link}'")
        if len(rss_feeds) < 1:
            return None
        return rss_feeds[0]

    def _get_rss_feeds(self, where: str) -> list[RssFeed]:
        self.cursor.execute(f"""
            SELECT id, area_id, link, web_link, title, last_update, last_error, enabled
            FROM rss_feeds 
            WHERE {where}
        """)
        rows = self.cursor.fetchall()
        rss_feeds = []
        for row in rows:
            rss_feed = RssFeed(area_id=row[1], rss_feed_id=row[0], link=row[2], web_link=row[3], title=row[4],
                               last_update=_text_to_datetime(row[5]), last_error=row[6], enabled=_int_to_bool(row[7]))
            rss_feeds.append(rss_feed)
        return rss_feeds

    def disable_all_rss_feeds(self):
        sql = "UPDATE rss_feeds SET enabled = 0"
        self._execute_sql(sql)

    # endregion
