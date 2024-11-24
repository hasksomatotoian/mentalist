from typing import List
import instructor
from langchain_ollama import OllamaEmbeddings
from services.config_service import ConfigService
from model.topic import Topic
from model.post import Post
import logging
from openai import OpenAI
from pydantic import BaseModel, Field

class LlmProxy:
    def __init__(self, config_service: ConfigService):
        self.config_service = config_service

        self.embeddings = OllamaEmbeddings(
            base_url=config_service.ollama_base_url, 
            model=config_service.embeddings_model
        )

        self.competions_client = instructor.from_openai(
            OpenAI(
                base_url=self.config_service.ollama_base_url + "/v1",
                api_key="ollama",  # required, but unused
            ),
            mode=instructor.Mode.JSON,
        )

    def add_embeddings_to_posts(self, posts: List[Post], batch_size: int = 10) -> List[Post]:
        """Calculate embeddings for a list of posts in batches"""
        posts_with_embeddings = []
        batch_start = 0

        logging.info(f"Creating embeddings for {len(posts)} posts...")

        while batch_start < len(posts):
            batch_end = min(batch_start + batch_size, len(posts))
            
            documents = [
                f"Title: {post.title}\n\n{post.summary}" 
                for post in posts[batch_start:batch_end]
            ]

            post_embeddings = self.embeddings.embed_documents(documents)
            
            for index, post in enumerate(posts[batch_start:batch_end]):
                post.embeddings = post_embeddings[index]
                posts_with_embeddings.append(post)

            batch_start = batch_end

        return posts_with_embeddings
    
    def add_embeddings_to_topics(self, topics: List[Topic], batch_size: int = 10) -> List[Topic]:
        """Calculate embeddings for a list of topics in batches"""
        topics_with_embeddings = []
        batch_start = 0

        logging.info(f"Creating embeddings for {len(topics)} topics...")

        while batch_start < len(topics):
            batch_end = min(batch_start + batch_size, len(topics))
            
            documents = [
                f"Title: {topic.title}\n\n{topic.summary}"
                for topic in topics[batch_start:batch_end]
            ]

            topic_embeddings = self.embeddings.embed_documents(documents)
            
            for index, topic in enumerate(topics[batch_start:batch_end]):
                topic.embeddings = topic_embeddings[index]
                topics_with_embeddings.append(topic)

            batch_start = batch_end

        return topics_with_embeddings

    def get_topic_title_and_summary(self, posts: list[Post]) -> tuple[str, str]:
        summaries = ""
        for post in posts:
            summaries += f"{post.title}\n{post.summary}\n\n"
            if len(summaries) > (self.config_service.keywords_context_size * 0.75):
                break

        content = f"""
Input: 
-------------------------------------------------------------------------------
Summaries: 
{summaries}
-------------------------------------------------------------------------------
Task:
1. Generate a short title for the topic, ideally 3–5 words long.
2. Create an overall summary from the "Summaries". Keep it concise (maximum five sentences).

Guidelines:
- Focus on facts, avoiding opinions or sentiment.
- Ensure summaries and titles are clear, precise, and to the point.
"""

        logging.info(f"Getting title and summary ({len(summaries)} bytes)")

        try:
            response = self.competions_client.chat.completions.create(
                model=self.config_service.keywords_model,
                temperature=self.config_service.keywords_temperature,
                max_tokens=self.config_service.keywords_context_size,
                messages=[
                    {
                        "role": "user",
                        "content": content,
                    }
                ],
                response_model=TopicSummary,
            )

            return response.title, response.overall_summary
        
        except Exception as e:
            logging.error(f"Error getting topic title and summary: {str(e)}")
            return None, None

    def get_topic_title_and_summaries(self, new_posts: list[Post], previous_posts: list[Post]) -> tuple[str, str, str]:
        previous_summaries = ""
        for post in previous_posts:
            previous_summaries += f"{post.title} - {post.summary}\n"
            if len(previous_summaries) > (self.config_service.keywords_context_size * 0.4):
                break

        new_summaries = ""
        for post in new_posts:
            new_summaries += f"{post.title} - {post.summary}\n"
            if (len(previous_summaries) + len(new_summaries)) > (self.config_service.keywords_context_size * 0.75):
                break

        content = f"""
Input: 
-------------------------------------------------------------------------------
Previous Summaries: 
{previous_summaries}
-------------------------------------------------------------------------------
New Summaries: 
{new_summaries}
-------------------------------------------------------------------------------
Task:
1. Generate a short title for the topic, ideally 3–5 words long.
2. Create an overall summary combining the "Previous Summaries" and "New Summaries". Keep it concise (maximum five sentences).
3. Identify and summarise the key updates from "New Summaries" compared to "Previous Summaries". Keep this summary concise (maximum five sentences).

Guidelines:
- Focus on facts, avoiding opinions or sentiment.
- Ensure summaries and titles are clear, precise, and to the point.
"""

        logging.info(f"Getting title and summaries ({len(new_summaries) + len(previous_summaries)} bytes)")

        try:
            response = self.competions_client.chat.completions.create(
                model=self.config_service.keywords_model,
            temperature=self.config_service.keywords_temperature,
            max_tokens=self.config_service.keywords_context_size,
            messages=[
                {
                    "role": "user",
                    "content": content,
                }
            ],
                response_model=TopicSummaries,
            )

            return response.title, response.overall_summary, response.updates_summary
        
        except Exception as e:
            logging.error(f"Error getting topic title and summaries: {str(e)}")
            return None, None, None


class TopicSummary(BaseModel):
    title: str = Field(description="Title of the topic")
    overall_summary: str = Field(description="Overall summary of the topic")


class TopicSummaries(BaseModel):
    title: str = Field(description="Title of the topic")
    overall_summary: str = Field(description="Overall summary of the topic")
    updates_summary: str = Field(description="Summary of the key updates in new summaries")

