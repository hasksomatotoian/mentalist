import hashlib
import json
import logging
import time
from datetime import datetime, timezone

from openai import OpenAI

from model.post_status import PostStatus
from services.config_service import ConfigService
from services.database_service import DatabaseService


class OpenAiService:
    def __init__(self, database_service: DatabaseService, config_service: ConfigService):
        self.database_service = database_service
        self.config_service = config_service
        self.client = OpenAI(
            api_key=config_service.openai_api_key
        )

    def rank_posts_by_title_and_summary(self):
        # TODO: Read assistant name from Post
        ai_assistant_id = self._get_assistant_id("F1 Assistant")

        logging.debug("Getting list of posts to rank")
        posts = self.database_service.get_posts_without_rank()
        logging.info(f"Found {len(posts)} posts to rank")

        for post in posts:
            try:
                logging.debug(f"Ranking post \"{post}\"")

                user_message = ("Use your instructions for this post:\n" +
                                f"Title: \"{post.title}\"\n" +
                                f"Summary: \"{post.summary}\"")

                response_json = self._get_response(ai_assistant_id, user_message)
                response_json = response_json.replace("```json", "")
                response_json = response_json.replace("```", "")
                try:
                    response = json.loads(response_json)
                except Exception as e:
                    raise RuntimeError(f"Error when parsing response JSON: {response_json}")

                post.ai_rank = int(response["rating"])
                post.ai_summary = response["summary"]

                post.status = PostStatus.RANKED
                post.last_error = None

                logging.info(f"Post \"{post}\" ranked successfully")

            except Exception as e:
                post.last_error = f"{e}"
                logging.error(f"Error when ranking post \"{post}\": {e}")

            self.database_service.update_post(post)

    def _get_assistant_id(self, assistant_name: str):

        assistant = self.database_service.get_assistant(assistant_name)
        with open(assistant.instructions_filename, 'r') as instructions_file:
            # Read the entire file content into a string
            instructions = instructions_file.read()

        current_checksum = hashlib.sha1((assistant.model + instructions).encode('utf-8')).hexdigest()

        if assistant.ai_id is None:
            ai_assistant = self.client.beta.assistants.create(
                name=assistant.name,
                description=assistant.description,
                instructions=instructions,
                model=assistant.model
                # TODO: Handle tools
                # tools=[{ "type": "retrieval" if assistant.needs_retrieval else "code_interpreter" if assistant.needs_code_interpreter else ""}]
            )

            assistant.created = datetime.now().astimezone(timezone.utc)
            assistant.last_update = assistant.created
            assistant.ai_id = ai_assistant.id
            assistant.checksum = current_checksum
            self.database_service.update_assistant(assistant)

        elif assistant.checksum != current_checksum:
            self.client.beta.assistants.update(
                assistant_id=assistant.ai_id,
                instructions=instructions,
                model=assistant.model
            )

            assistant.last_update = assistant.created
            assistant.checksum = current_checksum
            self.database_service.update_assistant(assistant)

        return assistant.ai_id

    def _get_response(self, ai_assistant_id: str, user_message: str):
        ai_thread = self.client.beta.threads.create(
            messages=[
                {
                    "role": "user",
                    "content": user_message
                }
            ]
        )

        ai_run = self.client.beta.threads.runs.create(
            thread_id=ai_thread.id,
            assistant_id=ai_assistant_id
        )

        while True:
            ai_run_retrieved = self.client.beta.threads.runs.retrieve(run_id=ai_run.id, thread_id=ai_thread.id)
            if (ai_run_retrieved.status == 'completed' or
                    ai_run_retrieved.status == 'failed' or
                    ai_run_retrieved.status == 'expired' or
                    ai_run_retrieved.status == 'cancelled'):
                break
            time.sleep(5)

        if ai_run_retrieved.status == 'completed':
            messages = self.client.beta.threads.messages.list(thread_id=ai_thread.id)
            return messages.data[0].content[0].text.value
        else:
            raise RuntimeError(f"OpenAI Run finished with status {ai_run_retrieved.status}")


'''
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
'''
