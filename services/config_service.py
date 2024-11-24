from dotenv import load_dotenv

import logging
import os


class ConfigService:
    def __init__(self):
        load_dotenv()

        self.logging_level = logging.INFO
        self.logging_format = '%(asctime)s - %(levelname)s - %(message)s'

        self.vector_db_path = ".\\chroma_db"
        self.vector_db_collection = "mentalist"

        self.database_filename = ".\\mentalist.sqlite3"
        self.areas_filename = ".\\areas.json"
        self.openai_api_key = os.environ.get('OPENAI_API_KEY')

        self.openai_posts_batch_size = 80
