import sqlite3

from datetime import datetime

from model.assistant import Assistant
from model.post import Post
from model.post_status import PostStatus
from model.rss_feed import RssFeed
from services.config_service import ConfigService


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


class DatabaseService:
    def __init__(self, config_service: ConfigService):
        self.connection = sqlite3.connect(config_service.database_filename)
        self.cursor = self.connection.cursor()
        self.create_db()
        self.create_data()

    def create_db(self):
        self._execute_sql("""
            CREATE TABLE IF NOT EXISTS rss_feeds (
                id INTEGER PRIMARY KEY,
                link TEXT NOT NULL UNIQUE,
                title TEXT,
                last_update TEXT,
                last_error TEXT
            );
        """)
        self._execute_sql("""
            CREATE TABLE IF NOT EXISTS posts (
                id INTEGER PRIMARY KEY,
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
                ai_rank INTEGER NOT NULL,
                ai_summary TEXT
            );
        """)
        self._execute_sql("""
            CREATE TABLE IF NOT EXISTS assistants (
                id INTEGER PRIMARY KEY,
                name TEXT NOT NULL UNIQUE,
                description TEXT,
                instructions_filename TEXT NOT NULL,
                model TEXT NOT NULL,
                needs_code_interpreter INTEGER NOT NULL,
                needs_retrieval INTEGER NOT NULL,
                ai_id TEXT,
                created TEXT NOT NULL,
                last_update TEXT NOT NULL,
                checksum TEXT
            );
        """)

    def create_data(self):
        self.add_rss_feed(RssFeed(link="https://www.formula1.com/content/fom-website/en/latest/all.xml"))
        # self.add_rss_feed(RssFeed(link="http://www1.skysports.com/feeds/12433/news.xml"))
        # self.add_rss_feed(RssFeed(link="http://www.f1-fansite.com/feed/"))
        # self.add_rss_feed(RssFeed(link="http://gpf1.cz/feed/"))
        # self.add_rss_feed(RssFeed(link="http://formulaspy.com/feed"))

        self.add_assistant(Assistant(name="F1 Assistant", description="",
                                     instructions_filename="./instructions/F1_EXPERT.md", model="gpt-4-1106-preview",
                                     needs_code_interpreter=False, needs_retrieval=True))

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
        self._execute_sql(sql, data)

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

    def add_rss_feed(self, rss_feed: RssFeed):
        sql = """
            INSERT OR IGNORE INTO rss_feeds(link, title, last_update, last_error)
            VALUES(?, ?, ?, ?)
        """
        data = (rss_feed.link, rss_feed.title, _datetime_to_text(rss_feed.last_update), rss_feed.last_error)
        self._execute_sql(sql, data)

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

    def add_post(self, post: Post):
        sql = """
            INSERT OR IGNORE INTO posts
                (link, title, summary, published, created, rss_feed_id, status, filename, last_error, 
                ai_fileid, ai_rank, ai_summary)
            VALUES
                (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?) 
        """
        data = (post.link, post.title, post.summary, _datetime_to_text(post.published),
                _datetime_to_text(post.created), post.rss_feed_id, post.status.value, post.filename,
                post.last_error, post.ai_fileid, post.ai_rank, post.ai_summary)
        self._execute_sql(sql, data)

    def get_posts_to_download(self):
        return self._get_posts(f"status = {PostStatus.INIT.value} AND last_error IS NULL")

    def get_posts_to_upload(self):
        return self._get_posts(f"status = {PostStatus.DOWNLOADED.value}")

    def get_posts_to_rank(self):
        return self._get_posts(f"status = {PostStatus.UPLOADED.value}")

    def _get_posts(self, where: str):
        self.cursor.execute("""
            SELECT 
                id, link, title, summary, published, created, rss_feed_id, status, filename, last_error, 
                ai_fileid, ai_rank, ai_summary
            FROM posts
            WHERE
        """ + where)
        rows = self.cursor.fetchall()
        posts = []
        for row in rows:
            post = Post(post_id=row[0], link=row[1], title=row[2], summary=row[3],
                        published=_text_to_datetime(row[4]), created=_text_to_datetime(row[5]),
                        rss_feed_id=row[6], status=PostStatus(row[7]), filename=row[8], last_error=row[9],
                        ai_fileid=row[10], ai_rank=row[11], ai_summary=row[12])
            posts.append(post)
        return posts

    def update_post(self, post):
        sql = """
            UPDATE posts
            SET
                link=?, title=?, summary=?, published=?, created=?, rss_feed_id=?, status=?, filename=?, last_error=?,
                ai_fileid=?, ai_rank=?, ai_summary=?
            WHERE id = ?
        """
        data = (post.link, post.title, post.summary, _datetime_to_text(post.published),
                _datetime_to_text(post.created), post.rss_feed_id, post.status.value, post.filename,
                post.last_error, post.ai_fileid, post.ai_rank, post.ai_summary, post.id)
        self._execute_sql(sql, data)

    def _execute_sql(self, sql, data=None):
        try:
            if data is None:
                self.cursor.execute(sql)
            else:
                self.cursor.execute(sql, data)
            self.connection.commit()
        except sqlite3.Error as e:
            print(f"Database error: {e}\nSQL:{sql}")
            self.connection.rollback()
        except Exception as e:
            print(f"Exception in _query: {e}\nSQL:{sql}")
            self.connection.rollback()

    def __del__(self):
        self.connection.close()
