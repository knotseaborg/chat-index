"""
TODO: Refactor to proper session-injected services.
Currently using isolated sessions for demo velocity.

Risk: Logic interleaven rollbacks are impossible
"""

from typing import Optional

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import db.models as models
from dto import ThreadDTO, SummaryDTO, LinkDTO, MessageDTO


class DB:
    """Separated functionalities of a relational database."""

    def __init__(self, uri: str):
        # "postgresql+psycopg2://{user}:{password}@{host}/{name}"
        self.db_engine = create_engine(uri)
        self.Session = sessionmaker(bind=self.db_engine)
        # Create tables if they don't exist
        models.Base.metadata.create_all(self.db_engine)

    def fetch_threads(self) -> list[ThreadDTO]:
        with self.Session() as session:
            threads: list[ThreadDTO] = []
            with session.begin():
                for thread in session.query(models.Thread).all():
                    threads.append(
                        {
                            "id": thread.id,
                            "topic": thread.topic,
                            "prompt": thread.prompt,
                            "created_at": thread.created_at,
                        }
                    )
            return threads

    def fetch_messages(self, thread_id: int) -> list[MessageDTO]:
        with self.Session() as session:
            messages: list[MessageDTO] = []
            with session.begin():
                for message in (
                    session.query(models.Message)
                    .filter(models.Message.thread_id == thread_id)
                    .all()
                ):
                    messages.append(
                        {
                            "id": message.id,
                            "content": message.content,
                            "thread_id": message.thread,
                            "created_at": message.created_at,
                            "embedding_file": None,
                        }
                    )
            return messages

    def fetch_message(self, message_id: int) -> MessageDTO:
        with self.Session() as session:
            with session.begin():
                message = (
                    session.query(models.Message)
                    .filter(models.Message.id == message_id)
                    .first()
                )
                return {
                    "id": message.id,
                    "content": message.content,
                    "thread_id": message.thread_id,
                    "created_at": message.created_at,
                    "embedding_file": None,
                }

    def fetch_links(self, thread_id: int) -> list[LinkDTO]:
        with self.Session() as session:
            links: list[LinkDTO] = []
            with session.begin():
                for link in (
                    session.query(models.Link)
                    .filter(models.Thread.id == thread_id)
                    .all()
                ):
                    links.append(
                        {
                            "id": link.id,
                            "thread_id": link.thread_id,
                            "next_message_id": link.next_message_id,
                            "previous_message_id": link.previous_message_id,
                            "created_at": link.created_at,
                        }
                    )
            return links

    def fetch_summaries(self, thread_id: int) -> list[SummaryDTO]:
        with self.Session() as session:
            summaries: list[SummaryDTO] = []
            with session.begin():
                for summary in (
                    session.query(models.Summary)
                    .join(
                        models.Message,
                        models.Message.id == models.Summary.start_message_id,
                    )
                    .filter(models.Message.thread_id == thread_id)
                    .all()
                ):
                    summaries.append(
                        {
                            "id": summary.id,
                            "content": summary.content,
                            "start_message_id": summary.start_message_id,
                            "end_message_id": summary.end_message_id,
                            "created_at": summary.created_at,
                            "embedding_file": None,
                        }
                    )
            return summaries

    def insert_message(self, thread_id: int, content: str) -> int:
        with self.Session() as session:
            with session.begin():
                message = models.Message(thread_id=thread_id, content=content)
                session.add(message)
                session.flush()
                return message.id

    def insert_link(
        self, thread_id: int, prev_message_id: int, next_message_id: int
    ) -> int:  # For every message, add the double ll links
        with self.Session() as session:
            with session.begin():
                link = models.Link(
                    thread_id=thread_id,
                    previous_message_id=prev_message_id,
                    next_message_id=next_message_id,
                )
                session.add(link)
                session.flush()
                return link.id

    def insert_thread(
        self, prompt: Optional[str] = None, topic: Optional[str] = None
    ) -> int:
        if prompt is None:
            prompt = "You are a powerful brain storming partner"
        with self.Session() as session:
            with session.begin():
                thread = models.Thread(prompt=prompt, topic=topic)
                session.add(thread)
                session.flush()
                return thread.id

    def insert_summary(
        self,
        content: str,
        start_message_id: int,
        end_message_id: int,
        embedding_file: Optional[str],
    ) -> int:
        with self.Session() as session:
            with session.begin():
                summary = models.Summary(
                    content=content,
                    embedding_file=embedding_file,
                    start_message_id=start_message_id,
                    end_message_id=end_message_id,
                )
                session.add(summary)
                session.flush()
                return summary.id

    def delete_summary(
        self, summary_id: int
    ):  # A split node causes split in summary too!
        with self.Session() as session:
            with session.begin():
                summary = (
                    session.query(models.Summary)
                    .filter(models.Summary.id == summary_id)
                    .first()
                )
                session.delete(summary)

    def delete_link(self, previous_message_id: int, next_message_id: int):
        """Deletes one link. Used to detatch branch"""
        with self.Session() as session:
            with session.begin():
                link = (
                    session.query(models.Link)
                    .filter(
                        models.Link.previous_message_id == previous_message_id
                        and models.Link.next_message_id == next_message_id
                    )
                    .first()
                )
                session.delete(link)

    def delete_message(self, _id: int):
        """
        Deletes a single messasge.
        """
        with self.Session() as session:
            with session.begin():
                message = (
                    session.query(models.Message)
                    .filter(models.Message.id == _id)
                    .first()
                )
                session.delete(message)
