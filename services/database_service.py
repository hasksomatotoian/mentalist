import sqlite3

from datetime import datetime
from sqlite3 import Cursor

from model.area import Area
from model.post import Post
from model.topic import Topic
from model.post_status import PostStatus
from model.rss_feed import RssFeed
from services.config_service import ConfigService


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


# endregion

class DatabaseService:

    # region _Private Methods

    def __init__(self, config_service: ConfigService):
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
            CREATE TABLE IF NOT EXISTS posts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                link TEXT NOT NULL UNIQUE,
                title TEXT NOT NULL,
                summary TEXT NOT NULL,
                published TEXT NOT NULL,
                created TEXT NOT NULL,
                rss_feed_id INTEGER,
                status INTEGER NOT NULL,
                filename TEXT,
                last_error TEXT,
                ai_fileid TEXT,
                ai_rating INTEGER NOT NULL,
                ai_summary TEXT,
                read INTEGER,
                saved INTEGER
            );
        """)
        self._execute_sql("""
            CREATE TABLE IF NOT EXISTS topics (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                summary TEXT NOT NULL,
                latest_post_published TEXT,
                best_post_ai_rating INTEGER,
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
        sql = """
            SELECT
                id, name, title, instructions_filename, model, needs_code_interpreter, needs_retrieval, 
                ai_id, ai_created, ai_last_update, checksum, priority, enabled
            FROM areas
            WHERE
                name=
        """ + f"\"{name}\""
        self.cursor.execute(sql)
        rows = self.cursor.fetchall()
        if len(rows) > 0:
            row = rows[0]
            assistant = Area(assistant_id=row[0], name=row[1], title=row[2], instructions_filename=row[3],
                             model=row[4], needs_code_interpreter=_int_to_bool(row[5]),
                             needs_retrieval=_int_to_bool(row[6]), ai_id=row[7],
                             ai_created=_text_to_datetime(row[8]), ai_last_update=_text_to_datetime(row[9]),
                             checksum=row[10], priority=row[11], enabled=_int_to_bool(row[12]))
            return assistant
        return None

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

    def add_post(self, post: Post):
        sql = """
            INSERT OR IGNORE INTO posts
                (link, title, summary, published, created, rss_feed_id, status, filename, last_error, 
                ai_fileid, ai_rating, ai_summary, read, saved)
            VALUES
                (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?) 
        """
        data = (post.link, post.title, post.summary, _datetime_to_text(post.published),
                _datetime_to_text(post.created), post.rss_feed_id, post.status.value, post.filename,
                post.last_error, post.ai_fileid, post.ai_rating, post.ai_summary,
                _bool_to_int(post.read), _bool_to_int(post.saved))
        cursor = self._execute_sql(sql, data)
        post.id = cursor.lastrowid

    def update_post(self, post: Post):
        sql = """
            UPDATE posts
            SET
                link=?, title=?, summary=?, published=?, created=?, rss_feed_id=?, status=?, filename=?, last_error=?,
                ai_fileid=?, ai_rating=?, ai_summary=?, read=?, saved=?
            WHERE id = ?
        """
        data = (post.link, post.title, post.summary, _datetime_to_text(post.published),
                _datetime_to_text(post.created), post.rss_feed_id, post.status.value, post.filename,
                post.last_error, post.ai_fileid, post.ai_rating, post.ai_summary, _bool_to_int(post.read),
                _bool_to_int(post.saved), post.id)
        self._execute_sql(sql, data)

    def get_post_by_id(self, post_id: int) -> Post | None:
        posts = self._get_posts(f"id = {post_id}")
        if len(posts) > 0:
            return posts[0]
        return None

    def get_posts_without_topic(self) -> list[Post]:
        return self._get_posts("""
            (SELECT COUNT(*) FROM posts_x_topics WHERE posts_x_topics.post_id = posts.id) = 0
        """)

    def _get_posts(self, where: str, order_by: str = "id") -> list[Post]:
        self.cursor.execute(f"""
            SELECT 
                id, link, title, summary, published, created, rss_feed_id, status, filename, last_error, 
                ai_fileid, ai_rating, ai_summary, read, saved
            FROM posts
            WHERE {where}
            ORDER BY {order_by}
        """)
        rows = self.cursor.fetchall()
        posts = []
        for row in rows:
            post = Post(post_id=row[0], link=row[1], title=row[2], summary=row[3],
                        published=_text_to_datetime(row[4]), created=_text_to_datetime(row[5]),
                        rss_feed_id=row[6], status=PostStatus(row[7]), filename=row[8], last_error=row[9],
                        ai_fileid=row[10], ai_rating=row[11], ai_summary=row[12], read=_int_to_bool(row[13]),
                        saved=_int_to_bool(row[14]))
            posts.append(post)
        return posts

    # endregion

    # region Topic

    def add_topic(self, topic: Topic):
        sql = """
            INSERT INTO topics
                (title, summary, latest_post_published, best_post_ai_rating, my_rating, ai_rating, ai_analysis, read,
                 saved)
            VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        data = (topic.title, topic.summary, _datetime_to_text(topic.latest_post_published),
                topic.best_post_ai_rating, topic.my_rating, topic.ai_rating, topic.ai_analysis,
                _bool_to_int(topic.read), _bool_to_int(topic.saved))
        cursor = self._execute_sql(sql, data)
        topic.id = cursor.lastrowid

    def get_topic_by_id(self, topic_id: int) -> Topic | None:
        topics = self._get_topics(f"id={topic_id}", "id")
        if len(topics) > 0:
            return topics[0]
        return None

    def get_topics_for_view(self) -> list[Topic]:
        topics = self._get_topics("read = 0", "ai_rating, latest_post_published DESC")
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

    def update_topics_rating_and_published(self):
        sql = """
            UPDATE topics
            SET
                best_post_ai_rating = (
                    SELECT MIN(posts.ai_rating) 
                    FROM posts
                    JOIN posts_x_topics ON posts_x_topics.post_id = posts.id 
                    WHERE 
                        posts_x_topics.topic_id = topics.id
                        AND posts.ai_rating > 0
                        AND posts.read = 0
                ),
                latest_post_published = (
                    SELECT MAX(posts.published) 
                    FROM posts
                    JOIN posts_x_topics ON posts_x_topics.post_id = posts.id 
                    WHERE 
                        posts_x_topics.topic_id = topics.id
                )
        """
        self._execute_sql(sql)

    def toggle_topic_saved(self, topic_id):
        sql = f"UPDATE topics SET saved = (1 - saved) WHERE id = {topic_id}"
        self._execute_sql(sql)

    def toggle_topic_read(self, topic_id):
        sql = f"UPDATE topics SET read = (1 - read) WHERE id = {topic_id}"
        self._execute_sql(sql)

    def _get_topics(self, where: str, order_by) -> list[Topic]:
        sql = f"""
            SELECT
                id, title, summary, latest_post_published, best_post_ai_rating, my_rating, ai_rating, ai_analysis, read,
                saved
            FROM topics
            WHERE {where}
            ORDER BY {order_by}
            """
        self.cursor.execute(sql)
        rows = self.cursor.fetchall()
        topics = []
        for row in rows:
            topic = Topic(topic_id=row[0], title=row[1], summary=row[2],
                          latest_post_published=_text_to_datetime(row[3]),
                          best_post_ai_rating=row[4], my_rating=row[5], ai_rating=row[6], ai_analysis=row[7],
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

    def get_all_rss_feeds(self) -> list[RssFeed]:
        return self._get_rss_feeds("1=1")

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
