from typing import Optional

from db.db import DB
from services.agent import Agent
from services.summary import Summarizer

class ChatManager:

    def __init__(self, db: DB,summarizer: Summarizer, agent: Agent):
        self._db = db
        self._summarizer = summarizer
        self._agent = agent


    def handle_user_message(
        self,
        thread_id: int,
        content: str,
        previous_message_id: Optional[int]
    ) -> dict:
        # 1. Insert the user's message
        user_message = self._db.insert_message(thread_id=thread_id, content=content)

        # 2. Create a link to the previous message
        if previous_message_id is not None:
            self._db.insert_link(
                thread_id=thread_id,
                prev_message_id=previous_message_id,
                next_message_id=user_message.id,
            )

        # 3. Generate AI response
        ai_message = self._agent.generate_response(content, thread_id)
        ai_message = self._db.insert_message(thread_id, content=ai_message)
        self._db.insert_link(thread_id=thread_id, prev_message_id=user_message.id, next_message_id=ai_message.id)

        # 4. Fetch previous message and check for topic shift
        if previous_message_id is not None:
            previous_message = self._db.fetch_message(previous_message_id)
            if self._summarizer.detect_topic_shift(
                previous_message.content, user_message.content
            ):
                # Get recent messages (user + bot message) and summarize
                recent_messages = [previous_message, user_message, ai_message]
                summary_text = self._summarizer.generate_summary(recent_messages)
                self._db.insert_summary(
                    content=summary_text,
                    start_message_id=recent_messages[0].id,
                    end_message_id=recent_messages[-1].id,
                    embedding_file=None,
                )

        return {
            "user_message": {"id": user_message.id, "content": user_message.content},
            "ai_response": {"id": ai_message.id, "content": ai_message.content},
            "linked_from": previous_message_id,
            "summary_created": summary_text if previous_message_id and topic_shift else None
        }

