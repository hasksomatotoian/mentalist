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

        self.delete_local_post_file_after_its_uploaded = False
        self.delete_uploaded_post_file_after_its_ranked = False
