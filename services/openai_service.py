import hashlib
import html
import json
import logging
import time
from datetime import datetime, timezone
from typing import Any

from openai import OpenAI

from model.area import Area
from model.topic import Topic
from services.config_service import ConfigService
from services.database_service import DatabaseService


class OpenAiService:
    def __init__(self, database_service: DatabaseService, config_service: ConfigService):
        self.database_service = database_service
        self.config_service = config_service
        self.client = OpenAI(
            api_key=config_service.openai_api_key
        )

    def create_topics(self):
        areas = self.database_service.get_enabled_areas()
        if areas is None:
            return

        for area in areas:
            logging.info(f"Creating topics for area \"{area}\"")

            while True:
                user_message = self._get_posts_by_area_without_topic_json(area.id)
                if user_message is None:
                    break

                logging.info(f"User message:\n{user_message}")

                self._create_or_update_ai_assistant(area)

                responses = self._get_responses_from_json(area.ai_id, user_message)
                if responses is None:
                    break

                for response in responses:
                    try:
                        topic = Topic(area_id=area.id, title=response["TOPIC_TITLE"], summary=response["TOPIC_SUMMARY"],
                                      ai_analysis=response["TOPIC_ANALYSIS"], ai_rating=int(response["TOPIC_RATING"]),
                                      created=datetime.now().astimezone(timezone.utc))
                        self.database_service.add_topic(topic)
                        logging.info(f"Topic \"{topic}\" created successfully")

                        post_ids = response["POST_IDs"].split(',')
                        for post_id_as_str in post_ids:
                            post_id = int(post_id_as_str)
                            self.database_service.add_post_x_topic(post_id, topic.id)
                            self.database_service.add_post_x_topic(post_id, topic.id)

                    except Exception as e:
                        logging.error(f"Error when assigning topic to response \"{response}\": {e}")

    def _create_or_update_ai_assistant(self, area: Area):

        with open(area.instructions_filename, 'r') as instructions_file:
            # Read the entire file content into a string
            instructions = instructions_file.read()

        current_checksum = hashlib.sha1((area.model + instructions).encode('utf-8')).hexdigest()

        if area.ai_id is None:
            ai_assistant = self.client.beta.assistants.create(
                name=area.name,
                description=area.title,
                instructions=instructions,
                model=area.model
                # TODO: Handle tools
                # tools=[{ "type": "retrieval" if assistant.needs_retrieval else "code_interpreter" if assistant.needs_code_interpreter else ""}]
            )

            area.ai_created = datetime.now().astimezone(timezone.utc)
            area.ai_last_update = area.ai_created
            area.ai_id = ai_assistant.id
            area.checksum = current_checksum
            self.database_service.update_area(area)

        elif area.checksum != current_checksum:
            ai_assistant = self.client.beta.assistants.update(
                assistant_id=area.ai_id,
                instructions=instructions,
                model=area.model
            )

            area.ai_id = ai_assistant.id
            area.ai_last_update = datetime.now().astimezone(timezone.utc)
            area.checksum = current_checksum
            self.database_service.update_area(area)

    def _get_responses_from_json(self, ai_assistant_id: str, user_message: str) -> Any | None:
        ai_thread = self.client.beta.threads.create()

        self.client.beta.threads.messages.create(
            thread_id=ai_thread.id,
            content=user_message,
            role="user")

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
            try:
                messages = self.client.beta.threads.messages.list(thread_id=ai_thread.id)
                response_json = messages.data[0].content[0].text.value.replace("```json", "")
                response_json = response_json.replace("```", "")
            except Exception as e:
                logging.error(f"Error when reading response text: {e}")
                return None
            try:
                return json.loads(response_json)
            except Exception as e:
                logging.error(f"Error when parsing response from \"{response_json}\": {e}")
        else:
            logging.error(f"OpenAI Run finished with status {ai_run_retrieved.status}")

        return None

    def _get_posts_by_area_without_topic_json(self, area_id: int) -> str | None:
        logging.debug("Getting list of posts to assign a topic")
        posts = self.database_service.get_posts_by_area_without_topic(area_id)
        logging.info(f"Found {len(posts)} posts without a topic")

        if len(posts) < 1:
            return None

        batch_index = 0
        formatted_posts = "{[\n"
        for post in posts:
            formatted_posts += "\t{"
            formatted_posts += f"\"ID\": \"{post.id}\", "
            formatted_posts += f"\"TITLE\": \"{html.escape(post.title)}\","
            formatted_posts += f"\"SUMMARY\": \"{html.escape(post.summary)}\""
            formatted_posts += "},\n"
            batch_index += 1
            if batch_index >= self.config_service.openai_posts_batch_size:
                break

        formatted_posts += "]}"
        return formatted_posts
