import logging

from flask import Flask, render_template, redirect, url_for
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


@app.route('/topic_read/<topic_id>')
def topic_read(topic_id: int):
    db_service = DatabaseService(cfg_service)
    db_service.toggle_topic_read(topic_id)
    return redirect(url_for('index'))


@app.route('/topic_save/<topic_id>')
def topic_save(topic_id: int):
    db_service = DatabaseService(cfg_service)
    db_service.toggle_topic_saved(topic_id)
    return redirect(url_for('index'))


if __name__ == '__main__':
    app.run(debug=True)
