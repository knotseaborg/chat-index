from typing import TypedDict, Optional
from datetime import datetime


class ThreadDTO(TypedDict):
    id: int
    topic: str
    prompt: str
    created_at: datetime


class MessageDTO(TypedDict):
    id: int
    thread_id: int
    content: str
    embedding_file: Optional[str]
    created_at: datetime


class SummaryDTO(TypedDict):
    id: int
    content: str
    embedding_file: Optional[str]
    start_message_id: int
    end_message_id: int
    created_at: datetime


class LinkDTO(TypedDict):
    id: int
    thread_id: int
    previous_message_id: int
    next_message_id: int
    created_at: datetime
