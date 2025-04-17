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
        [---summary----]---[]--[]--[]--[prev_node_node]-[current_message]
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

    def delete_branch(self, thread_id: int, branch_start_message_id: int) -> None:
        """
        Nukes a branch. Use with care!
        
        Note: This is not thread-safe. Can lead to dirty reads
        """
        message_tree, summary_tree = self._tree_cache.get(thread_id)

        ## Delete Messages

        # Chain deletions, every message and summary in the branch is deleted
        branch_off_message_id = message_tree.index[branch_start_message_id]["parent"]
        
        # Detatch branch_start_message from branch_off_message.
        if branch_off_message_id is not None:            
            self._db.delete_link(branch_off_message_id, branch_start_message_id)

        # Delete remaining messages in branch
        message_ids: list[int] = [branch_start_message_id]
        while message_ids:
            message_id = message_ids.pop()
            child_ids = message_tree.index[message_id]["child_ids"]
            # Add children for future exploration
            message_ids.extend(child_ids)
            # Detach current node from children
            for child_id in child_ids:
                self._db.delete_link(message_id, child_id)
            # Delete the current node
            self._db.delete_message(message_id)

        ## Delete Summaries

        branch_start_summary_id = summary_tree.index.start_message_lookup.get(
            branch_start_message_id, None
        )
        # If no summary exists at the start point, this cannot proceed
        if branch_start_summary_id is None:
            return

        # Since summary tree is derived from the message tree, no deletion of links necessary
        # Delete summaries from db
        summary_ids: list[int] = [branch_start_summary_id]
        while summary_ids:
            summary_id = summary_ids.pop()
            self._db.delete_summary(summary_id)
            summary = summary_tree.index.summary_id_lookup[summary_id]
            summary_ids.extend(summary["child_ids"])

        # Delete invalid trees.
        # This forces a re-construction from db during next call to the LRU cache.
        self._tree_cache.delete(thread_id)


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
