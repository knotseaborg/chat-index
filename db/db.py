from typing import Optional


from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import db.models as models


class DB:
    """Separated functionalities of a relational database."""

    def __init__(self, user: str, password: str, host: str, name: str):
        self.uri = f"postgresql+psycopg2://{user}:{password}@{host}/{name}"
        self.load()

    def load(self):
        """Loads enginer and session"""
        self.db_engine = create_engine(self.uri)
        self.db_session = sessionmaker(bind=self.db_engine)()
        self._setup()

    def _connection_check(self):
        """Raises exception"""
        if self.db_engine is None or self.db_session is None:
            raise AssertionError(
                "db_engine or db_session is unloaded. load_db() must be called first"
            )

    def _setup(self):
        models.Base.metadata.create_all(  # Create tables if they don't exist
            self.db_engine
        )

    def fetch_threads(self) -> list[models.Thread]:
        return self.db_session.query(models.Thread).all()

    def fetch_messages(self, thread_id: int) -> list[models.Message]:
        return (
            self.db_session.query(models.Message)
            .filter(models.Message.thread_id == thread_id)
            .all()
        )

    def fetch_message(self, message_id: int) -> models.Message:
        return self.db_session.query(models.Message).filter(models.Message.id == message_id).first()

    def fetch_links(self, thread_id: int) -> list[models.Link]:
        return (
            self.db_session.query(models.Link)
            .filter(models.Thread.id == thread_id)
            .all()
        )

    def fetch_summaries(self, thread_id: int) -> list[models.Summary]:
        return (
            self.db_session.query(models.Summary)
            .join(models.Message, models.Message.id == models.Summary.start_message_id)
            .filter(models.Message.thread_id == thread_id)
            .all()
        )

    def insert_message(self, thread_id: int, content: str) -> models.Message:
        with self.db_session.begin():
            message = models.Message(thread_id=thread_id, content=content)
            self.db_session.add(message)
        return message

    def insert_link(
        self, thread_id: int, prev_msg_id: int, next_msg_id: int
    ) -> models.Link:  # For every message, add the double ll links
        with self.db_session.begin():
            link = models.Link(
                thread_id=thread_id,
                previous_message_id=prev_msg_id,
                next_message_id=next_msg_id,
            )
            self.db_session.add(link)
        return link

    def insert_thread(
        self, prompt: Optional[str] = None, topic: Optional[str] = None
    ) -> models.Thread:
        if prompt is None:
            prompt = "You are a powerful brain storming partner"
        with self.db_session.begin():
            thread = models.Thread(prompt=prompt, topic=topic)
            self.db_session.add(thread)
        return thread

    def insert_summary(
        self,
        content: str,
        start_message_id: int,
        end_message_id: int,
        embedding_file: Optional[str],
    ) -> models.Summary:  # Add summary
        with self.db_session.begin():
            summary = models.Summary(
                content=content,
                embedding_file=embedding_file,
                start_message_id=start_message_id,
                end_message_id=end_message_id,
            )
            self.db_session.add(summary)
        return summary

    def delete_summary(
        self, summary_id: int
    ) -> models.Summary:  # A split node causes split in summary too!
        with self.db_session.begin():
            summary = (
                self.db_session.query(models.Summary)
                .filter(models.Summary.id == summary_id)
                .first()
            )
            self.db_session.delete(summary)
        return summary
