from dotenv import load_dotenv

import logging
import os


class ConfigService:
    def __init__(self):
        load_dotenv()

        self.logging_level = logging.INFO
        self.logging_format = '%(asctime)s - %(levelname)s - %(message)s'

        self.database_filename = ".\\mentalist.sqlite3"
        self.post_files_folder = ".\\post_files"
        self.openai_api_key = os.environ.get('OPENAI_API_KEY')

        self.openai_posts_batch_size = 80
