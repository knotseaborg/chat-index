import os
from typing import Callable, Optional
from services.chat_trees import TreeCache
from db.db import DB
from db.models import Message, Link, Summary
from services.agent import Agent
from services.llm_ops import LLMOps


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
        tree_cache: TreeCache,
        llm_ops: LLMOps,
    ):
        self._db = db
        self._tree_cache = tree_cache
        self._llm_ops = llm_ops

    def add_message(self, content: str, thread_id: int, prev_message_id: Optional[int]):
        """Inserts message into both in-memory tree and database"""
        # Database insertion
        message = self._db.insert_message(thread_id, content)
        # Insert the link to previous message
        if prev_message_id is not None:
            self._db.insert_link(
                thread_id=thread_id,
                prev_message_id=prev_message_id,
                next_message_id=message.id,
            )

        # Load tree
        message_tree, _ = self._tree_cache.get(thread_id)
        # Add message
        message_tree.add_message(message.id, content, prev_message_id)

    def _add_summary(
        self, thread_id: int, prev_message_id: int, message_content: str
    ) -> Optional[Summary]:
        """
        Assumption: prev_message_id is either an end_node of summary, or not summarized at all.
        Essentially:
        [---summary----]---------prev_node_node-current_message
        [---summary----prev_node]-current_message

        Care must be taken for this assumption to not be violated

        Note; Current message cannot be included in the summary
        """
        # WIP: Needs guard code to prevent summary generation from rogue nodes
        message_tree, summary_tree = self._tree_cache.get(thread_id)
        prev_message_node = message_tree.index[prev_message_id]
        # No summary if there is no topic shift between messages
        # because summaries need to be semantically coherent
        if not self._llm_ops.detect_topic_shift(
            prev_message_node["content"], message_content
        ):
            return None

        # Cannot create summary if previous message was the end_point of the previous summary
        if prev_message_id in summary_tree.index.end_message_lookup:
            return None

        # Accumulate summarizable content, and map the spanning nodes
        summarizable_content: list[str] = []
        end_message_id = prev_message_id  # prev_message is a valid summarizable content

        # This will run atleast once! If not, something is wrong. Must fail loudly!
        while (prev_message_id is None) or (
            prev_message_id not in summary_tree.index.end_message_lookup
        ):
            start_message_id = prev_message_id

            message = message_tree.index[prev_message_id]
            summarizable_content.append(message["content"])

            # Update iterable
            prev_message_id = message["parent_id"]

        # Generate summary and add to memory and db
        summarized_content = self._llm_ops.generate_summary(summarizable_content)
        # Add summary to database
        summary = self._db.insert_summary(
            summarized_content, start_message_id, end_message_id, embedding_file=None
        )
        # Add summary to tree
        summary_tree.add_summary(
            summary.id, summarized_content, start_message_id, end_message_id
        )

    def _detect_summary_split(self, thread_id: int, message_id: int) -> bool:
        """
        Determines if a split takes place in a single summary, given the messaged_id from where the branch-off takes place.
        """
        _, summary_tree = self._tree_cache.get(thread_id)
        return message_id in summary_tree.index.end_message_lookup

    def split_summary(
        self, thread_id: int, branch_off_message_id: int
    ) -> tuple[str, int, int]:
        """
        Splits a summary, from the branch_off_message_node and persists it in memory and db

        Note: If this function runs, it implies that the split is valid 
            and an unsplit summary span is being split.
        """

        message_tree, summary_tree = self._tree_cache.get(thread_id)

        ## Compute pre-summary data
        contents = []
        pre_start_message_id = pre_end_message_id = message_id = branch_off_message_id

        # Iterate in reverse tracking parent id, until the previous summary is reached.
        # Note: A start message will always exist for a summary. None checking not required
        while message_id not in summary_tree.index.end_message_lookup:
            contents.append(message_tree.index[message_id]["content"])
            pre_start_message_id = message_id
            message_id = message_tree.index[message_id]["parent_id"]

        summary_id = summary_tree.index.start_message_lookup[
            pre_start_message_id
        ]  # Split summary's reference
        # Generate pre-summary content
        pre_content = self._llm_ops.generate_summary(contents)

        ## Compute post-summary data
        contents = []
        post_start_message_id = post_end_message_id = message_id = message_tree.index[
            branch_off_message_id
        ]["child_ids"][0]
        while message_id not in summary_tree.index.start_message_lookup:
            contents.append(message_tree.index[message_id]["content"])
            post_end_message_id = message_id
            # Note: A summary contains a linear chain of messages; this is valid
            message_id = message_tree.index[message_id]["child_ids"][0]
        # generate post-summary
        post_content = self._llm_ops.generate_summary(contents)

        ## Persist Split in Memory and Database
        self._db.delete_summary(summary_id)
        pre_summary = self._db.insert_summary(
            pre_content, pre_start_message_id, pre_end_message_id
        )
        post_summary = self._db.insert_summary(
            post_content, post_start_message_id, post_end_message_id
        )
        summary_tree.split_summary(
            summary_id,
            pre_summary.id,
            pre_summary.content,
            branch_off_message_id,
            post_summary.id,
            post_summary.content,
        )


class ChatUpdateDispatcher:
    def __init__(self, thread_id: int, db: DB, llm_ops: llm_ops):
        self.thread_id = thread_id
        self._db = db
        self._llm_ops = llm_ops
        self._tree = ChatTree(thread_id, db)

        self._memory_tree_handler = MemoryTreeHandler(self._tree)
        self._db_tree_handler = DBTreeHandler(self._db)
        self._handler = Handler(
            self._db_tree_handler, self._memory_tree_handler, self._llm_ops
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

#     def __init__(self, db: DB, llm_ops: LLMOps, agent: Agent):
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
