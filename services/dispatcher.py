"""
This module handles requests and dispatched then for chat updates
"""

from typing import Callable, Optional

from services.chat_trees import TreeCache, SummaryTree, MessageTree
from services.llm_ops import LLMOps
from db.db import DB


class Handler:
    """All handlers neccessary for mutation of persistent chat, is provided here"""

    def __init__(
        self,
        db: DB,
        tree_cache: TreeCache,
        llm_ops: LLMOps,
    ):
        self._db = db
        self._tree_cache = tree_cache
        self._llm_ops = llm_ops

    def add_message(
        self,
        content: str,
        thread_id: int,
        prev_message_id: Optional[int],
        trigger_summarization: bool,
        summary_batch_size: int,
    ) -> int:
        """
        Inserts message and generate corresponding summary in memory tree and database
        """
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

        if trigger_summarization:  # Usually, the summary must be triggered
            self._add_summary(thread_id, prev_message_id, content, summary_batch_size)
        return message.id

    def _add_summary(
        self,
        thread_id: int,
        prev_message_id: Optional[int],
        message_content: str,
        batch_size: int,
    ):
        """
        Supports the add_message method; is optionally executable through trigger parameter.

        Assumption: prev_message_id is either an end_node of summary, or not summarized at all.
        Note:Care must be taken for this assumption to not be violated
        Note: Current message cannot be included in the summary
        """
        # WIP: Needs guard code to prevent summary generation from rogue nodes
        message_tree, summary_tree = self._tree_cache.get(thread_id)

        ## Check if summarization is required
        if (
            (prev_message_id is None)
            or (summary_tree.count_unsummarized_messages(prev_message_id) < batch_size)
            or (
                not self._llm_ops.detect_topic_shift(
                    message_tree.index[prev_message_id]["content"], message_content
                )
            )
        ):
            return None

        # Accumulate summarizable content, and map the spanning nodes
        summarizable_content: list[str] = []
        end_message_id = prev_message_id  # prev_message is a valid summarizable content

        # This will run atleast once! If not, something is wrong. Must fail loudly!
        while prev_message_id not in summary_tree.index.end_message_lookup:
            start_message_id = prev_message_id
            message = message_tree.index[prev_message_id]
            summarizable_content.append(message["content"])
            prev_message_id = message["parent_id"]  # Update iterable

        # Generate summary and add to memory and db
        summarized_content = self._llm_ops.generate_summary(summarizable_content)
        summary = self._db.insert_summary(  # Add summary to database
            summarized_content, start_message_id, end_message_id, embedding_file=None
        )
        summary_tree.add_summary(  # Add summary to tree
            summary.id, summarized_content, start_message_id, end_message_id
        )

    def split_summary(self, thread_id: int, branch_off_message_id: int) -> tuple[int, int]:
        """
        Splits a summary, from the branch_off_message_node and persists it in memory and db
        
        Returns split summary ids

        Note: If this function runs, it implies that the split is valid
            and an unsplit summary span is being split.
        """
        message_tree, summary_tree = self._tree_cache.get(thread_id)
        ## Compute pre-summary data
        pre_content, pre_start_message_id, pre_end_message_id = (
            self._generate_split_pre_summary_data(
                message_tree, summary_tree, branch_off_message_id
            )
        )
        ## Compute post-summary data
        post_content, post_start_message_id, post_end_message_id = (
            self._generate_split_post_summary_data(
                message_tree, summary_tree, branch_off_message_id
            )
        )
        ## Persist Split in Database
        summary_id = summary_tree.index.start_message_lookup[pre_start_message_id]
        self._db.delete_summary(summary_id)
        pre_summary = self._db.insert_summary(
            pre_content, pre_start_message_id, pre_end_message_id
        )
        post_summary = self._db.insert_summary(
            post_content, post_start_message_id, post_end_message_id
        )
        # Invalidate cache, force rebuild tree.
        del self._tree_cache[thread_id]
        return pre_summary.id, post_summary.id

    def _generate_split_pre_summary_data(
        self,
        message_tree: MessageTree,
        summary_tree: SummaryTree,
        branch_off_message_id: int,
    ) -> tuple[str, int, int]:
        """
        Supporting method which generates pre-split point summary data.
        """
        contents = []
        pre_start_message_id = pre_end_message_id = message_id = branch_off_message_id

        # Iterate in reverse tracking parent id, until the previous summary is reached.
        # Note: A start message will always exist for a summary. Checking not required
        while message_id not in summary_tree.index.end_message_lookup:
            contents.append(message_tree.index[message_id]["content"])
            pre_start_message_id = message_id
            message_id = message_tree.index[message_id]["parent_id"]

        # Generate pre-summary content
        contents.reverse()  # Note: because of reverse traversal
        pre_content = self._llm_ops.generate_summary(contents)
        return pre_content, pre_start_message_id, pre_end_message_id

    def _generate_split_post_summary_data(
        self,
        message_tree: MessageTree,
        summary_tree: SummaryTree,
        branch_off_message_id: int,
    ) -> tuple[str, int, int]:
        """
        Supporting method which generates post-split point summary data.
        """
        contents = []
        post_start_message_id = post_end_message_id = message_id = message_tree.index[
            branch_off_message_id
        ]["child_ids"][0]
        while message_id not in summary_tree.index.start_message_lookup:
            contents.append(message_tree.index[message_id]["content"])
            post_end_message_id = message_id
            # Note: A summary always contains a linear chain of messages
            message_id = message_tree.index[message_id]["child_ids"][0]

        # generate post-summary
        post_content = self._llm_ops.generate_summary(contents)
        return post_content, post_start_message_id, post_end_message_id

    def delete_branch(self, thread_id: int, branch_start_message_id: int) -> None:
        """
        Nukes a branch. Use with care!
        Chain deletions, every message and summary in the branch is deleted

        Note: This is not thread-safe. Can lead to dirty reads
        """
        message_tree, summary_tree = self._tree_cache.get(thread_id)

        self._delete_branch_messages(message_tree, branch_start_message_id)
        self._delete_branch_summaries(summary_tree, branch_start_message_id)

        # The deletions invalidate trees, so force reconstruction from db
        self._tree_cache.delete(thread_id)

    def _delete_branch_messages(
        self, message_tree: MessageTree, branch_start_message_id: int
    ):
        """
        Chain deletes messages of a branch from database
        """
        branch_off_message_id = message_tree.index[branch_start_message_id]["parent"]

        # Detach branch_start_message from branch_off_message.
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

    def _delete_branch_summaries(
        self, summary_tree: SummaryTree, branch_start_message_id: int
    ):
        """
        Chain deletes summaries of a branch from database
        """
        branch_start_summary_id = summary_tree.index.start_message_lookup.get(
            branch_start_message_id, None
        )
        if branch_start_summary_id is None:  # delete only if branch exists
            return
        # Note: Summary tree is derived from message tree, no deletion of links necessary

        # Delete summaries from db
        summary_ids: list[int] = [branch_start_summary_id]
        while summary_ids:
            summary_id = summary_ids.pop()
            self._db.delete_summary(summary_id)
            summary = summary_tree.index.summary_id_lookup[summary_id]
            summary_ids.extend(summary["child_ids"])


class ChatUpdateDispatcher:
    """
    Dispatcher pattern for updating peristed chats
    """

    def __init__(self, handler: Handler):
        self._handler = handler
        # Action registry
        self.handlers: dict[str, Callable[[dict], dict]] = {
            "add_message": self._handler.add_message,
            "branch_off": self._handler.split_summary,
            "delete_branch": self._handler.delete_branch,
        }

    def dispatch(self, action: str, payload: dict) -> dict:
        """
        Routes chat update actions to the correct handler.
        Payload must match the expected kwargs for the selected handler.
        """
        if action not in self.handlers:
            raise ValueError(f"Unsupported update type: {action}")
        handler = self.handlers[action]
        return handler(**payload)
