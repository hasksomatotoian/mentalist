import hashlib
import json
import os
import time
from datetime import datetime, timezone
from openai import OpenAI

from model.post import Post
from model.post_status import PostStatus
from services.config_service import ConfigService
from services.database_service import DatabaseService
import feedparser
import logging
import pdfkit
import re


def create_valid_filename(text, default_name="default_file"):
    # Characters to keep, add more if needed
    valid_chars = "-_.() abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
    # Replace spaces with underscores
    text = text.replace(" ", "_")
    # Remove invalid characters
    clean_text = ''.join(c for c in text if c in valid_chars)
    # Limit length to 255 characters (common maximum for file systems)
    clean_text = clean_text[:255]
    # Remove leading and trailing special characters that can cause issues
    clean_text = re.sub(r'^[._-]+|[._-]+$', '', clean_text)
    # Ensure the filename is not empty, '.' or '..'
    if not clean_text or clean_text in {'.', '..'}:
        clean_text = default_name
    return clean_text


def get_latest_posts(database_service: DatabaseService):
    logging.debug("Getting list of RSS feeds")
    rss_feeds = database_service.get_all_rss_feeds()
    logging.info(f"Found {len(rss_feeds)} RSS feeds")
    for rss_feed in rss_feeds:
        try:
            rss_feed.last_update = datetime.now().astimezone(timezone.utc)

            feed = feedparser.parse(rss_feed.link)

            rss_feed.title = feed.feed.title

            logging.info(f"Processing new posts from \"{rss_feed}\"")

            # Iterate through entries and print their titles and links
            for entry in feed.entries:
                logging.debug(f"Processing post \"{entry.title}\"")

                if 'published_parsed' in entry:
                    published = datetime(
                        year=entry.published_parsed.tm_year,
                        month=entry.published_parsed.tm_mon,
                        day=entry.published_parsed.tm_mday,
                        hour=entry.published_parsed.tm_hour,
                        minute=entry.published_parsed.tm_min,
                        second=entry.published_parsed.tm_sec
                    )
                else:
                    published = None
                post = Post(entry.link, entry.title, entry.summary, published, rss_feed.id)
                database_service.add_post(post)

            rss_feed.last_error = None
        except Exception as e:
            rss_feed.last_error = f"{e}"
            logging.error(f"Error when parsing RSS feed \"{rss_feed}\": {e}")

        database_service.update_rss_feed(rss_feed)


def download_posts(database_service: DatabaseService, config_service: ConfigService):
    logging.debug("Getting list of posts to download")
    posts = database_service.get_posts_to_download()
    logging.info(f"Found {len(posts)} posts to download")
    for post in posts:
        logging.debug(f"Downloading post \"{post}\"")
        post_filename = (f"{config_service.post_files_folder}\\" +
                         f"{post.published.strftime('%Y%m%d_%H%M%S')}-" +
                         f"{create_valid_filename(post.title)}.pdf")

        try:
            if not os.path.exists(post_filename):
                pdfkit.from_url(post.link, post_filename)
            post.status = PostStatus.DOWNLOADED
            post.filename = post_filename
            post.last_error = None
            logging.info(f"Post \"{post}\" downloaded successfully")
        except Exception as e:
            post.last_error = f"{e}"
            logging.error(f"Error when downloading post \"{post}\": {e}")

        database_service.update_post(post)


def upload_posts(database_service: DatabaseService, config_service: ConfigService):
    logging.debug("Getting list of posts to upload")
    posts = database_service.get_posts_to_upload()
    logging.info(f"Found {len(posts)} posts to upload")

    client = OpenAI(
        api_key=config_service.openai_api_key
    )

    for post in posts:

        try:
            logging.debug(f"Uploading post \"{post}\"")
            file = client.files.create(
                file=open(post.filename, "rb"),
                purpose='assistants'
            )
            post.status = PostStatus.UPLOADED
            post.ai_fileid = file.id
            post.last_error = None

            if config_service.delete_local_post_file_after_its_uploaded:
                try:
                    os.remove(post.filename)
                    post.filename = None
                    logging.debug(f"File \"{post.filename}\" successfully deleted")
                except Exception as e:
                    logging.warning(f"Error when deleting file \"{post.filename}\": {e}")

            logging.info(f"Post \"{post}\" uploaded successfully")
        except Exception as e:
            post.last_error = f"{e}"
            logging.error(f"Error when uploading post \"{post}\": {e}")

        database_service.update_post(post)


def rank_posts(database_service: DatabaseService, config_service: ConfigService):
    logging.debug("Getting list of posts to rank")
    posts = database_service.get_posts_to_rank()
    logging.info(f"Found {len(posts)} posts to rank")

    client = OpenAI(
        api_key=config_service.openai_api_key
    )

    # TODO: Read assistant name from Post
    assistant_name = "F1 Assistant"

    assistant = database_service.get_assistant(assistant_name)
    with open(assistant.instructions_filename, 'r') as instructions_file:
        # Read the entire file content into a string
        instructions = instructions_file.read()

    current_checksum = hashlib.sha1((assistant.model + instructions).encode('utf-8')).hexdigest()

    if assistant.ai_id is None:
        ai_assistant = client.beta.assistants.create(
            name=assistant.name,
            description=assistant.description,
            instructions=instructions,
            model=assistant.model,
            tools=[{
                       "type": "retrieval" if assistant.needs_retrieval else "code_interpreter" if assistant.needs_code_interpreter else ""}]
        )

        assistant.created = datetime.now().astimezone(timezone.utc)
        assistant.last_update = assistant.created
        assistant.ai_id = ai_assistant.id
        assistant.checksum = current_checksum
        database_service.update_assistant(assistant)

    elif assistant.checksum != current_checksum:
        client.beta.assistants.update(
            assistant_id=assistant.ai_id,
            instructions=instructions,
            model=assistant.model
        )

        assistant.last_update = assistant.created
        assistant.checksum = current_checksum
        database_service.update_assistant(assistant)

    for post in posts:
        try:
            client.files.wait_for_processing(id=post.ai_fileid, poll_interval=5, max_wait_seconds=30)
            logging.debug(f"Ranking post \"{post}\"")

            ai_thread = client.beta.threads.create(
                messages=[
                    {
                        "role": "user",
                        "content": f"Use your instructions to evaluate the text in the attached file {post.ai_fileid}.",
                        "file_ids": [post.ai_fileid]
                    }
                ]
            )

            ai_run = client.beta.threads.runs.create(
                thread_id=ai_thread.id,
                assistant_id=assistant.ai_id
            )

            while True:
                ai_run_retrieved = client.beta.threads.runs.retrieve(run_id=ai_run.id, thread_id=ai_thread.id)
                if (ai_run_retrieved.status == 'completed' or
                        ai_run_retrieved.status == 'failed' or
                        ai_run_retrieved.status == 'expired' or
                        ai_run_retrieved.status == 'cancelled'):
                    break
                time.sleep(5)

            if ai_run_retrieved.status == 'completed':
                messages = client.beta.threads.messages.list(thread_id=ai_thread.id)
                response_json = messages.data[0].content[0].text.value
                response_json = response_json.replace("```json", "")
                response_json = response_json.replace("```", "")
                try:
                    response = json.loads(response_json)
                except Exception as e:
                    raise RuntimeError(f"Error when parsing response JSON: {response_json}")

                post.ai_rank = int(response["rating"])
                post.ai_summary = response["summary"]
                post.length = response["length"] # TODO: Save length to DB

                post.status = PostStatus.RANKED
                post.last_error = None
                if config_service.delete_uploaded_post_file_after_its_ranked:
                    try:
                        client.files.delete(post.ai_fileid)
                        post.ai_fileid = None
                        logging.debug(f"Uploaded file \"{post.ai_fileid}\" successfully deleted")
                    except Exception as e:
                        logging.warning(f"Error when deleting uploaded file \"{post.ai_fileid}\": {e}")
                logging.info(f"Post \"{post}\" ranked successfully")

            else:
                raise RuntimeError(f"OpenAI Run finished with status {ai_run_retrieved.status}")

        except Exception as e:
            post.last_error = f"{e}"
            logging.error(f"Error when ranking post \"{post}\": {e}")

        database_service.update_post(post)


if __name__ == '__main__':
    conf_service = ConfigService()
    logging.basicConfig(level=conf_service.logging_level, format=conf_service.logging_format)
    db_service = DatabaseService(conf_service)

    # get_latest_posts(db_service)
    # download_posts(db_service, conf_service)
    # upload_posts(db_service, conf_service)
    rank_posts(db_service, conf_service)
