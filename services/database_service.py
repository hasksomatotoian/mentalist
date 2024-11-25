import os
import sqlite3
import uuid

from datetime import datetime
from sqlite3 import Cursor

from chromadb.api.types import IncludeEnum
from openai.types import Embedding
from pyasn1.type.univ import Sequence

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
                "link": post.link,
                "title": post.title,
                "published": _datetime_to_text(post.published),
                "created": _datetime_to_text(post.created),
                "rss_feed_id": post.rss_feed_id,
                "read": post.read,
                "saved": post.saved
            }

def _metadata_to_post(post_id: uuid, summary: str, embeddings: List[float],
                      metadata: Mapping[str, Union[str, int, float, bool]]) -> Post:
    post = Post(metadata["link"],
                metadata["title"],
                summary,
                _text_to_datetime(metadata["published"]),
                metadata["rss_feed_id"],
                post_id,
                _text_to_datetime(metadata["created"]),
                metadata["read"],
                metadata["saved"],
                embeddings)
    post.embeddings = embeddings
    return post


# endregion

class DatabaseService:

    # region _Private Methods

    def __init__(self, config_service: ConfigService):
        if not os.path.exists(config_service.vector_db_path):
            os.makedirs(config_service.vector_db_path)
        self.vector_db = chromadb.PersistentClient(path=config_service.vector_db_path)
        self.vector_db_collection = self.vector_db.get_or_create_collection(config_service.vector_db_collection)

        self.connection = sqlite3.connect(config_service.database_filename)
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
                link TEXT NOT NULL UNIQUE,
                web_link TEXT,
                title TEXT,
                last_update TEXT,
                last_error TEXT
            );
        """)
        self._execute_sql("""
            CREATE TABLE IF NOT EXISTS areas_x_rss_feeds (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                area_id INTEGER NOT NULL,
                rss_feed_id INTEGER NOT NULL,
                priority INTEGER NOT NULL,
                enabled INTEGER NOT NULL
            );
        """)

        self._execute_sql("""
            CREATE TABLE IF NOT EXISTS topics (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                area_id INTEGER NOT NULL,
                title TEXT NOT NULL,
                summary TEXT NOT NULL,
                created TEXT,
                my_rating INTEGER,
                ai_rating INTEGER,
                ai_analysis TEXT,
                read INTEGER,
                saved INTEGER
            );
        """)
        self._execute_sql("""
            CREATE TABLE IF NOT EXISTS posts_x_topics (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                post_id INTEGER NOT NULL,
                topic_id INTEGER NOT NULL
            );
        """)
        self._execute_sql("""
            CREATE UNIQUE INDEX IF NOT EXISTS posts_x_topics_unique 
            ON posts_x_topics(post_id, topic_id);
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

            rss_feed_priority = 0
            for rss_feed in area.rss_feeds:
                existing_rss_feed = self.get_rss_feed_by_link(rss_feed.link)
                if existing_rss_feed is None:
                    self.add_rss_feed(rss_feed)
                    rss_feed_id = rss_feed.id
                else:
                    rss_feed_id = existing_rss_feed.id

                rss_feed_priority += 1
                self.add_or_update_areas_x_rss_feeds(area_id=area_id, rss_feed_id=rss_feed_id,
                                                     priority=rss_feed_priority)

    # region Area

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
        documents = []
        ids = []
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

    def get_posts(self) -> list[Post]:
        posts: list[Post] = []

        include = [IncludeEnum.documents, IncludeEnum.metadatas, IncludeEnum.embeddings]
        db_posts = self.vector_db_collection.get(include=include)
        ids = db_posts["ids"]
        documents = db_posts["documents"]
        metadatas = db_posts["metadatas"]
        embeddings = db_posts["embeddings"]
        for index in range(len(ids)):
            post = _metadata_to_post(ids[index], documents[index], embeddings[index], metadatas[index])
            posts.append(post)

        return posts


    def get_posts_by_embeddings(self, embeddings: list[float]) -> list[Post]:
        include = [IncludeEnum.documents, IncludeEnum.metadatas, IncludeEnum.embeddings, IncludeEnum.distances]
        db_posts = self.vector_db_collection.query(
            query_embeddings=[embeddings],
            n_results=10,
            include=include
        )
        ids = db_posts["ids"][0]
        documents = db_posts["documents"][0]
        metadatas = db_posts["metadatas"][0]
        embeddings = db_posts["embeddings"][0]
        distances = db_posts["distances"][0]
        for index in range(len(ids)):
            post = _metadata_to_post(ids[index], documents[index], embeddings[index], metadatas[index])
            print(f"\t{post.title}", distances[index])

    def update_post(self, post: Post):
        return

    # def add_post(self, post: Post):
    #     sql = """
    #         INSERT OR IGNORE INTO posts
    #             (link, title, summary, published, created, rss_feed_id, ai_fileid, saved)
    #         VALUES
    #             (?, ?, ?, ?, ?, ?, ?, ?)
    #     """
    #     data = (post.link, post.title, post.summary, _datetime_to_text(post.published),
    #             _datetime_to_text(post.created), post.rss_feed_id, post.ai_fileid, _bool_to_int(post.saved))
    #     cursor = self._execute_sql(sql, data)
    #     post.id = cursor.lastrowid
    #
    # def update_post(self, post: Post):
    #     sql = """
    #         UPDATE posts
    #         SET
    #             link=?, title=?, summary=?, published=?, created=?, rss_feed_id=?, ai_fileid=?, saved=?
    #         WHERE id = ?
    #     """
    #     data = (post.link, post.title, post.summary, _datetime_to_text(post.published),
    #             _datetime_to_text(post.created), post.rss_feed_id, post.ai_fileid, _bool_to_int(post.saved), post.id)
    #     self._execute_sql(sql, data)
    #
    # def get_posts_by_area_without_topic(self, area_id: int) -> list[Post]:
    #     return self._get_posts(f"""
    #         posts.rss_feed_id IN (
    #             SELECT areas_x_rss_feeds.rss_feed_id
    #             FROM areas_x_rss_feeds
    #             WHERE areas_x_rss_feeds.area_id = {area_id}
    #         )
    #         AND
    #         (
    #             SELECT COUNT(*)
    #             FROM posts_x_topics
    #             JOIN topics ON topics.id = posts_x_topics.topic_id
    #             WHERE
    #                 posts_x_topics.post_id = posts.id
    #                 AND topics.area_id = {area_id}
    #         ) = 0
    #     """)
    #
    # def _get_posts(self, where: str, order_by: str = "id") -> list[Post]:
    #     self.cursor.execute(f"""
    #         SELECT
    #             id, link, title, summary, published, created, rss_feed_id, ai_fileid, saved
    #         FROM posts
    #         WHERE {where}
    #         ORDER BY {order_by}
    #     """)
    #     rows = self.cursor.fetchall()
    #     posts = []
    #     for row in rows:
    #         post = Post(post_id=row[0], link=row[1], title=row[2], summary=row[3],
    #                     published=_text_to_datetime(row[4]), created=_text_to_datetime(row[5]),
    #                     rss_feed_id=row[6], ai_fileid=row[7], saved=_int_to_bool(row[8]))
    #         posts.append(post)
    #     return posts
    #
    # # endregion

    # region Topic

    def add_topic(self, topic: Topic):
        sql = """
            INSERT INTO topics
                (area_id, title, summary, created, my_rating, ai_rating, ai_analysis, read, saved)
            VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        data = (topic.area_id, topic.title, topic.summary, _datetime_to_text(topic.created),
                topic.my_rating, topic.ai_rating, topic.ai_analysis,
                _bool_to_int(topic.read), _bool_to_int(topic.saved))
        cursor = self._execute_sql(sql, data)
        topic.id = cursor.lastrowid

    def get_topic_by_id(self, topic_id: int) -> Topic | None:
        topics = self._get_topics(f"id={topic_id}", "id")
        if len(topics) > 0:
            return topics[0]
        return None

    def get_topics_for_view(self, area_id: int) -> list[Topic]:
        topics = self._get_topics(where=f"read = {_bool_to_int(False)} AND {area_id} IN (area_id, 0)",
                                  order_by="ai_rating, created DESC")
        for topic in topics:
            topic.posts = self._get_posts(f"""
                posts.id IN (
                    SELECT posts_x_topics.post_id 
                    FROM posts_x_topics 
                    WHERE posts_x_topics.topic_id = {topic.id}
                )
            """, "rss_feed_id, published ASC")
            for post in topic.posts:
                post.rss_feed = self.get_rss_feed_by_id(post.rss_feed_id)
        return topics

    def toggle_topic_saved(self, topic_id):
        sql = f"UPDATE topics SET saved = (1 - saved) WHERE id = {topic_id}"
        self._execute_sql(sql)

    def toggle_topic_read(self, topic_id):
        sql = f"UPDATE topics SET read = (1 - read) WHERE id = {topic_id}"
        self._execute_sql(sql)

    def get_number_of_unread_topics(self, area_id: int) -> int:
        sql = f"""
            SELECT COUNT(*) FROM topics WHERE area_id = {area_id} AND read = {_bool_to_int(False)}
        """
        self.cursor.execute(sql)
        return self.cursor.fetchone()[0]

    def _get_topics(self, where: str, order_by) -> list[Topic]:
        sql = f"""
            SELECT
                id, area_id, title, summary, created, my_rating, ai_rating, ai_analysis, read, saved
            FROM topics
            WHERE {where}
            ORDER BY {order_by}
            """
        self.cursor.execute(sql)
        rows = self.cursor.fetchall()
        topics = []
        for row in rows:
            topic = Topic(topic_id=row[0], area_id=row[1], title=row[2], summary=row[3],
                          created=_text_to_datetime(row[4]), my_rating=row[5], ai_rating=row[6], ai_analysis=row[7],
                          read=_int_to_bool(row[8]), saved=_int_to_bool(row[9]))
            topics.append(topic)
        return topics

    # endregion

    # region Posts_x_Topics

    def add_post_x_topic(self, post_id: int, topic_id: int):
        sql = """
            INSERT OR IGNORE INTO posts_x_topics
                (post_id, topic_id)
            VALUES
                (?, ?) 
        """
        data = (post_id, topic_id)
        self._execute_sql(sql, data)

    # endregion

    # region RssFeed
    def add_rss_feed(self, rss_feed: RssFeed):
        sql = """
            INSERT OR IGNORE INTO rss_feeds(link, web_link, title, last_update, last_error)
            VALUES(?, ?, ?, ?, ?)
        """
        data = (rss_feed.link, rss_feed.web_link, rss_feed.title, _datetime_to_text(rss_feed.last_update),
                rss_feed.last_error)
        cursor = self._execute_sql(sql, data)
        rss_feed.id = cursor.lastrowid

    def update_rss_feed(self, rss_feed: RssFeed):
        sql = """
            UPDATE rss_feeds 
            SET link=?, web_link=?, title=?, last_update=?, last_error=?
            WHERE id=?
        """
        data = (
            rss_feed.link, rss_feed.web_link, rss_feed.title, _datetime_to_text(rss_feed.last_update),
            rss_feed.last_error,
            rss_feed.id)
        self._execute_sql(sql, data)

    def get_enabled_rss_feeds(self) -> list[RssFeed]:
        return self._get_rss_feeds(f"""
            rss_feeds.id IN (
                SELECT areas_x_rss_feeds.rss_feed_id 
                FROM areas_x_rss_feeds
                WHERE areas_x_rss_feeds.enabled = {_bool_to_int(True)}
            )
        """)

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
            SELECT id, link, web_link, title, last_update, last_error
            FROM rss_feeds 
            WHERE {where}
        """)
        rows = self.cursor.fetchall()
        rss_feeds = []
        for row in rows:
            rss_feed = RssFeed(rss_feed_id=row[0], link=row[1], web_link=row[2], title=row[3],
                               last_update=_text_to_datetime(row[4]), last_error=row[5])
            rss_feeds.append(rss_feed)
        return rss_feeds

    def disable_all_rss_feeds(self):
        sql = "UPDATE areas_x_rss_feeds SET enabled = 0"
        self._execute_sql(sql)

    def add_or_update_areas_x_rss_feeds(self, area_id: int, rss_feed_id: int, priority: int):
        sql = f"""
            UPDATE areas_x_rss_feeds 
            SET priority = {priority}, enabled = 1 
            WHERE area_id = {area_id} AND rss_feed_id = {rss_feed_id}
            """
        cursor = self._execute_sql(sql)
        if cursor.rowcount < 1:
            sql = """
                INSERT INTO areas_x_rss_feeds(area_id, rss_feed_id, priority, enabled)
                VALUES(?, ?, ?, ?)
            """
            data = (area_id, rss_feed_id, priority, _bool_to_int(True))
            self._execute_sql(sql, data)

    # endregion
