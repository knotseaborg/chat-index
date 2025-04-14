from typing import Callable, Optional
from services.chat_tree import ChatTree, MessageNode
from db.db import DB
from db.models import Message, Link, Summary
from services.agent import Agent
from services.summary import Summarizer


class MemoryTreeHandler:
    """Note: Deletion triggers rebuilding. So it is not handled here"""
    """Memory tree modifications only"""

    def __init__(self, tree: ChatTree):
        self.tree = tree

    # Wrong # Wrng, must add dict, not db
    def add_message(self, message: Message, prev_message_id: int):
        self.tree.message_index[message.id] = {"id": message.id, "content": message.content, "parent_id": message}
        self.tree.message_index[prev_message_id]["child_ids"].append(message.id)

    # Wrng, must add dict, not db
    def add_summary(self, summary: Summary):
        self.tree.summary_index.summary_id_lookup[summary.id] = summary
        self.tree.summary_index.start_message_lookup[summary.start_message_id] = (
            summary.id
        )
        self.tree.summary_index.end_message_lookup[summary.end_message_id] = summary.id

    def collapse_summary(self, collapsed_summary_ids: list[int], summary: Summary):
        # Future work. Would be neat!
        pass


class DBTreeHandler:
    """Database Tree Modifications only"""
    def __init__(self, db: DB):
        self._db = db

    def add_message(
        self, content: str, thread_id: int, prev_message_id: int
    ) -> Message:
        message = self._db.insert_message(thread_id=thread_id, content=content)

        # Create a link to the previous message
        if prev_message_id is not None:
            self._db.insert_link(
                thread_id=thread_id,
                prev_message_id=prev_message_id,
                next_message_id=message.id,
            )

        return message

    def add_summary(
        self, content: str, start_message_id: int, end_message_id: int
    ) -> Summary:
        return self._db.insert_summary(content, start_message_id, end_message_id)


class Handler:
    def __init__(
        self,
        db: DB,
        summarizer: Summarizer,
    ):
        self._db_handler = DBTreeHandler(db)
        self._tree = ChatTree(thread_id=None, db=db)
        self._tree_handler = MemoryTreeHandler() # Keeps changing depending on thread_id, so management is internal
        self._summarizer = summarizer

    def add_message(self, content: str, thread_id: int, prev_message_id: int):
        self._tree_handler._sync_tree(thread_id)

        message = self._db_handler.add_message(content, thread_id, prev_message_id)
        self._tree_handler.add_message(message, prev_message_id)

    def _add_summary(
        self, prev_message_id: int, message_content: str
    ) -> Optional[Summary]:
        """
        0. Check if topic shift has been detected.
        1. Gathers the summarizable contents from tree.
        2. Generates summary
        3. Inserts summary into db
        4. Inserts sumamry to tree
        """
        prev_message = self.db
        if not self._summarizer.detect_topic_shift(
            prev_message.content, message_content
        ):
            return None

        contents, start_message_id, end_message_id = (
            self._tree_handler.get_summarizable_data(prev_message_id)
        )
        summary_content = self._summarizer.generate_summary(contents)
        summary = self._db_handler.add_summary(
            summary_content, start_message_id, end_message_id
        )
        self._tree_handler.add_summary(summary)

    def get_summarizable_data(self, prev_message_id: int) -> tuple[list[str], int, int]:
        """
        From the provided message, retrace the last occuring summary to find summarizable data

        Note: This excludes the message_id's message
        """
        # Accumilate unsummarized messages
        content: list[str] = []
        start_message_id = end_message_id = prev_message_id
        while prev_message_id not in self.tree.summary_index.end_message_lookup:
            start_message_id = prev_message_id
            prev_message_id = self.tree.message_index[prev_message_id]["parent_id"]
            content.append(self.tree.message_index[prev_message_id]["content"])

        return (content[::-1], start_message_id, end_message_id)

    def get_front_span_messages(self, message_id: int) -> list[MessageNode]: # Includes message_id
        messages : list[MessageNode] = [self.tree.message_index[message_id]]
        while message_id not in self.tree.summary_index.start_message_lookup:
            message_id = self.tree.message_index[message_id]["parent_id"]    
            messages.append(self.tree.message_index[message_id])
        return messages

    def get_after_span_messages(self, message_id: int) -> list[MessageNode]: # Excludes message_id
        messages : list[MessageNode] = []
        while message_id not in self.tree.summary_index.end_message_lookup:
            message_id = self.tree.message_index[message_id]["child_ids"][0] # No branches between summaries, so ok!!
            messages.append(self.tree.message_index[message_id])

    def split_summary(self, message_id: int): # New end of first span of split
        """
        Two cases are possible.
        1. [-----split-----] {split and resummarize}
        2. [-----------] split [---------] {do nothing}
        """
        
        if self._tree_handler.tree.summary_index.end_message_lookup[message_id]:
            return None
        self.

class ChatUpdateDispatcher:
    def __init__(self, thread_id: int, db: DB, summarizer: Summarizer):
        self.thread_id = thread_id
        self._db = db
        self._summarizer = summarizer
        self._tree = ChatTree(thread_id, db)

        self._memory_tree_handler = MemoryTreeHandler(self._tree)
        self._db_tree_handler = DBTreeHandler(self._db)
        self._handler = Handler(
            self._db_tree_handler, self._memory_tree_handler, self._summarizer
        )

        # Action registry
        self.handlers: dict[str, Callable[[dict], dict]] = {
            "add_message": self._handler.add_message,
            "add_summary": self._handler.add_summary,
            "branch_off": self.handle_branch_off,
            "delete_branch": self.handle_delete_branch,
        }

    def dispatch(self, action: str, payload: dict) -> dict:
        """
        payload always expects "thread_id"
        """
        if action not in self.handlers:
            raise ValueError(f"Unsupported update type: {action}")
        handler = self.handlers[action]
        return handler(**payload)

    def _load_correct_thread(self, thread_id: int):
        """
        Loads the correct thread.
        TBD: Caching loaded trees, depending on user behaviour.
        """
        if thread_id != self.thread_id:
            self.thread_id = thread_id
            self._tree = ChatTree(thread_id, self._db)

    def add_message(self, content: str, prev_message_id: int):
        self.tree.message_index[prev_message_id][""]


# class ChatManager:

#     def __init__(self, db: DB, summarizer: Summarizer, agent: Agent):
#         self._db = db
#         self._summarizer = summarizer
#         self._agent = agent

#         self.memory_tree: Optional[MessageNode] = None

#     def handle_user_message(
#         self, thread_id: int, content: str, previous_message_id: Optional[int]
#     ) -> dict:
#         # Insert user's message
#         user_message = self._db.insert_message(thread_id=thread_id, content=content)

#         # Create a link to the previous message
#         if previous_message_id is not None:
#             self._db.insert_link(
#                 thread_id=thread_id,
#                 prev_message_id=previous_message_id,
#                 next_message_id=user_message.id,
#             )

#         # 3. Generate AI response
#         ai_message = self._agent.generate_response(content, thread_id)
#         ai_message = self._db.insert_message(thread_id, content=ai_message)
#         self._db.insert_link(
#             thread_id=thread_id,
#             prev_message_id=user_message.id,
#             next_message_id=ai_message.id,
#         )

#         # 4. Fetch previous message and check for topic shift
#         summary_text = None
#         if previous_message_id is not None:
#             previous_message = self._db.fetch_message(previous_message_id)
#             if self._summarizer.detect_topic_shift(
#                 previous_message.content, user_message.content
#             ):
#                 # Get recent messages (user + bot message) and summarize
#                 recent_messages = [previous_message, user_message, ai_message]
#                 summary_text = self._summarizer.generate_summary(recent_messages)
#                 self._db.insert_summary(
#                     content=summary_text,
#                     start_message_id=recent_messages[0].id,
#                     end_message_id=recent_messages[-1].id,
#                     embedding_file=None,
#                 )

#         return {
#             "user_message": {"id": user_message.id, "content": user_message.content},
#             "ai_response": {"id": ai_message.id, "content": ai_message.content},
#             "linked_from": previous_message_id,
#             "summary_created": summary_text,
#         }
