import logging
import uuid

from flask import Flask, render_template, redirect, url_for
from services.config_service import ConfigService
from services.database_service import DatabaseService

app = Flask(__name__)

cfg_service = ConfigService()
logging.basicConfig(level=cfg_service.logging_level, format=cfg_service.logging_format)


@app.route('/')
def index():
    return redirect(url_for('display_list', area_id=0))


@app.route('/list/<area_id>')
def display_list(area_id: int):
    db_service = DatabaseService(cfg_service)
    areas = db_service.get_areas_for_web()
    topics = db_service.get_topics_for_view(int(area_id))
    return render_template('index.html', areas=areas, topics=topics)


@app.route('/topic_read/<area_id>/<topic_id>/<my_rating>')
def topic_read(area_id: int, topic_id: uuid.UUID, my_rating: int):
    db_service = DatabaseService(cfg_service)
    db_service.update_topic_rating_and_mark_as_read(topic_id, int(my_rating))
    return redirect(url_for('display_list', area_id=int(area_id)))


@app.route('/topic_save/<area_id>/<topic_id>')
def topic_save(area_id: int, topic_id: uuid.UUID):
    db_service = DatabaseService(cfg_service)
    db_service.toggle_topic_saved(topic_id)
    return redirect(url_for('display_list', area_id=area_id))


if __name__ == '__main__':
    app.run(debug=True)
