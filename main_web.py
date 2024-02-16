import logging

from flask import Flask, render_template
from services.config_service import ConfigService
from services.database_service import DatabaseService

app = Flask(__name__)

cfg_service = ConfigService()
logging.basicConfig(level=cfg_service.logging_level, format=cfg_service.logging_format)


@app.route('/')
def index():
    db_service = DatabaseService(cfg_service)
    topics = db_service.get_topics_for_view()
    return render_template('index.html', topics=topics)


@app.route('/post_read/<post_id>')
def post_read(post_id: int):
    db_service = DatabaseService(cfg_service)
    post = db_service.get_post_by_id(post_id)
    if post is not None:
        post.read = not post.read
        db_service.update_post(post)
        db_service.update_topics_rating_and_published()

    return index()


@app.route('/topic_read/<topic_id>')
def topic_read(topic_id: int):
    db_service = DatabaseService(cfg_service)
    posts = db_service.get_posts_by_topic_id(topic_id)
    for post in posts:
        if not post.read:
            post.read = True
            db_service.update_post(post)
    db_service.update_topics_rating_and_published()

    return index()


if __name__ == '__main__':
    app.run(debug=True)
