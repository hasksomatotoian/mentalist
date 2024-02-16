import sqlite3

from datetime import datetime

from model.assistant import Assistant
from model.post import Post
from model.topic import Topic
from model.post_status import PostStatus
from model.rss_feed import RssFeed
from services.config_service import ConfigService


# region Helper Methods

def _datetime_to_text(datetime_value: datetime):
    if datetime_value is None:
        return None
    else:
        return datetime_value.strftime('%Y-%m-%dT%H:%M:%S')


def _text_to_datetime(text_value: str):
    if text_value is None:
        return None
    else:
        return datetime.strptime(text_value, '%Y-%m-%dT%H:%M:%S')


def _bool_to_int(bool_value: bool):
    if bool_value is None:
        return None
    else:
        return 1 if bool_value else 0


def _int_to_bool(int_value: int):
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
        self._create_data()

    def __del__(self):
        self.connection.close()

    def _create_db(self):
        self._execute_sql("""
            CREATE TABLE IF NOT EXISTS rss_feeds (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                link TEXT NOT NULL UNIQUE,
                title TEXT,
                last_update TEXT,
                last_error TEXT
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
                best_post_ai_rating INTEGER
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
        self._execute_sql("""
            CREATE TABLE IF NOT EXISTS assistants (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                description TEXT,
                instructions_filename TEXT NOT NULL,
                model TEXT NOT NULL,
                needs_code_interpreter INTEGER NOT NULL,
                needs_retrieval INTEGER NOT NULL,
                ai_id TEXT,
                created TEXT,
                last_update TEXT,
                checksum TEXT
            );
        """)

    def _create_data(self):
        self.add_rss_feed(RssFeed(link="https://www.formula1.com/content/fom-website/en/latest/all.xml"))
        self.add_rss_feed(RssFeed(link="http://www1.skysports.com/feeds/12433/news.xml"))
        self.add_rss_feed(RssFeed(link="http://formulaspy.com/feed"))
        # self.add_rss_feed(RssFeed(link="http://www.f1-fansite.com/feed/"))
        # self.add_rss_feed(RssFeed(link="http://gpf1.cz/feed/"))

        self.add_assistant(Assistant(name="F1 Assistant", description="",
                                     instructions_filename="./instructions/F1_EXPERT.md", model="gpt-4-turbo-preview",
                                     needs_code_interpreter=False, needs_retrieval=False))
        self.add_assistant(Assistant(name="F1 - Topics", description="",
                                     instructions_filename="./instructions/F1_TOPICS.md", model="gpt-4-turbo-preview",
                                     needs_code_interpreter=False, needs_retrieval=False))

    def _execute_sql(self, sql, data=None):
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

    # region Assistant

    def add_assistant(self, assistant: Assistant):
        sql = """
            INSERT OR IGNORE INTO assistants
                (name, description, instructions_filename, model, needs_code_interpreter, needs_retrieval, 
                ai_id, created, last_update, checksum)
            VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        data = (assistant.name, assistant.description, assistant.instructions_filename, assistant.model,
                _bool_to_int(assistant.needs_code_interpreter), _bool_to_int(assistant.needs_retrieval),
                assistant.ai_id, _datetime_to_text(assistant.created), _datetime_to_text(assistant.last_update),
                assistant.checksum)
        cursor = self._execute_sql(sql, data)
        assistant.id = cursor.lastrowid

    def get_assistant(self, name: str):
        sql = """
            SELECT
                id, name, description, instructions_filename, model, needs_code_interpreter, needs_retrieval, 
                ai_id, created, last_update, checksum
            FROM assistants
            WHERE
                name=
        """ + f"\"{name}\""
        self.cursor.execute(sql)
        rows = self.cursor.fetchall()
        if len(rows) > 0:
            row = rows[0]
            assistant = Assistant(assistant_id=row[0], name=row[1], description=row[2], instructions_filename=row[3],
                                  model=row[4], needs_code_interpreter=_int_to_bool(row[5]),
                                  needs_retrieval=_int_to_bool(row[6]), ai_id=row[7],
                                  created=_text_to_datetime(row[8]), last_update=_text_to_datetime(row[9]),
                                  checksum=row[10])
            return assistant
        return None

    def update_assistant(self, assistant):
        sql = """
            UPDATE assistants SET 
                name=?, description=?, instructions_filename=?, model=?, needs_code_interpreter=?, needs_retrieval=?, 
                ai_id=?, created=?, last_update=?, checksum=?
            WHERE id=?
        """
        data = (assistant.name, assistant.description, assistant.instructions_filename, assistant.model,
                _bool_to_int(assistant.needs_code_interpreter), _bool_to_int(assistant.needs_retrieval),
                assistant.ai_id, _datetime_to_text(assistant.created), _datetime_to_text(assistant.last_update),
                assistant.checksum, assistant.id)
        self._execute_sql(sql, data)

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

    def get_post_by_id(self, post_id: int):
        posts = self._get_posts(f"id = {post_id}")
        if len(posts) > 0:
            return posts[0]
        return None

    def get_posts_by_topic_id(self, topic_id: int):
        return self._get_posts(f"""
              posts.id IN (SELECT posts_x_topics.post_id FROM posts_x_topics WHERE posts_x_topics.topic_id = {topic_id})
          """)

    def get_posts_to_download(self):
        return self._get_posts(f"status = {PostStatus.INIT.value} AND last_error IS NULL")

    def get_posts_to_upload(self):
        return self._get_posts(f"status = {PostStatus.DOWNLOADED.value}")

    def get_posts_to_rate(self):
        return self._get_posts(f"status = {PostStatus.UPLOADED.value}")

    def get_posts_without_rating(self):
        return self._get_posts("ai_rating = 0")

    def get_posts_without_topic(self):
        return self._get_posts("""
            (SELECT COUNT(*) FROM posts_x_topics WHERE posts_x_topics.post_id = posts.id) = 0
        """)

    def _get_posts(self, where: str, order_by: str = "id"):
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
                (title, summary, latest_post_published, best_post_ai_rating)
            VALUES(?, ?, ?, ?)
        """
        data = (topic.title, topic.summary, _datetime_to_text(topic.latest_post_published),
                topic.best_post_ai_rating)
        cursor = self._execute_sql(sql, data)
        topic.id = cursor.lastrowid

    def get_topic_by_id(self, topic_id: int):
        topics = self._get_topics(f"id={topic_id}", "id")
        if len(topics) > 0:
            return topics[0]
        return None

    def get_topics(self):
        return self._get_topics("1=1", "id DESC")

    def get_topics_for_view(self):
        topics = self._get_topics("best_post_ai_rating > 0", "best_post_ai_rating, latest_post_published DESC")
        for topic in topics:
            topic.posts = self._get_posts(f"""
                posts.id IN (
                    SELECT posts_x_topics.post_id 
                    FROM posts_x_topics 
                    WHERE posts_x_topics.topic_id = {topic.id}
                )
            """, "ai_rating, published DESC")
        return topics

    def update_topic(self, topic: Topic):
        sql = """
            UPDATE topics SET 
                title=?, summary=?, latest_post_published=?, best_post_ai_rating=?
            WHERE id=?
        """
        data = (topic.title, topic.summary, _datetime_to_text(topic.latest_post_published),
                topic.best_post_ai_rating, topic.id)
        self._execute_sql(sql, data)

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
                        AND posts.ai_rating > 0
                        AND posts.read = 0
                )
        """
        self._execute_sql(sql)

    def _get_topics(self, where: str, order_by):
        sql = f"""
            SELECT
                id, title, summary, latest_post_published, best_post_ai_rating
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
                          best_post_ai_rating=row[4])
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
            INSERT OR IGNORE INTO rss_feeds(link, title, last_update, last_error)
            VALUES(?, ?, ?, ?)
        """
        data = (rss_feed.link, rss_feed.title, _datetime_to_text(rss_feed.last_update), rss_feed.last_error)
        cursor = self._execute_sql(sql, data)
        rss_feed.id = cursor.lastrowid

    def update_rss_feed(self, rss_feed: RssFeed):
        sql = """
            UPDATE rss_feeds 
            SET link=?, title=?, last_update=?, last_error=?
            WHERE id=?
        """
        data = (rss_feed.link, rss_feed.title, _datetime_to_text(rss_feed.last_update), rss_feed.last_error,
                rss_feed.id)
        self._execute_sql(sql, data)

    def get_all_rss_feeds(self):
        self.cursor.execute("SELECT id, link, title, last_update, last_error FROM rss_feeds")
        rows = self.cursor.fetchall()
        rss_feeds = []
        for row in rows:
            rss_feed = RssFeed(rss_feed_id=row[0], link=row[1], title=row[2], last_update=_text_to_datetime(row[3]),
                               last_error=row[4])
            rss_feeds.append(rss_feed)
        return rss_feeds

    # endregion
