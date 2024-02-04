from enum import Enum


class PostStatus(Enum):
    INIT = 0
    DOWNLOADED = 10
    UPLOADED = 20
    RANKED = 30
