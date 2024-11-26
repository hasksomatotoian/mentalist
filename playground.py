import uuid
from datetime import datetime, timezone

from model.post import Post
from services.config_service import ConfigService
import logging

from services.database_service import DatabaseService
from langchain_ollama import OllamaEmbeddings

cfg_service = ConfigService()
logging.basicConfig(level=cfg_service.logging_level, format=cfg_service.logging_format)

db_service = DatabaseService(cfg_service)


embeddings = OllamaEmbeddings(base_url=cfg_service.ollama_base_url,
                              model=cfg_service.embeddings_model)

post_embeddings = embeddings.embed_documents(["Title", "Short Summary", "Content"])

posts: list[Post] = [
    Post("http://" + str(uuid.uuid4()), "Title", "", datetime.now().astimezone(timezone.utc), 1,
         embeddings=[1,2,3])
]
db_service.add_posts(posts)

db_service.get_unread_posts()

