from typing import Optional, TypedDict
from dataclasses import dataclass, field
from collections import OrderedDict
from db.db import DB


class MessageNode(TypedDict):
    id: int
    content: str
    parent_id: Optional[int]
    child_ids: list[int]


class SummaryNode(TypedDict):
    id: int
    content: str
    start_message_id: int
    end_message_id: int
    parent_id: Optional[int]
    child_ids: list[int]


@dataclass
class SummaryIndex:
    start_message_lookup: dict[int, int] = field(
        default_factory=dict
    )  # message_id --> summary_id
    end_message_lookup: dict[int, int] = field(
        default_factory=dict
    )  # message_id --> summary_id
    summary_id_lookup: dict[int, SummaryNode] = field(
        default_factory=dict
    )  # summary_id --> SummaryNode


class MessageTree:
    def __init__(self, thread_id: int, db: DB):
        self._db = db
        self.thread_id = thread_id
        self.root_message_id, self.index = self._load_message_tree(thread_id)

    def _load_message_tree(self, thread_id: int) -> tuple[int, dict[int, MessageNode]]:
        """
        Builds an in-memory tree of messages from the thread's links.
        Returns a dict of message_id → MessageNode
        """

        messages = self._db.fetch_messages(thread_id)
        links = self._db.fetch_links(thread_id)

        nodes: dict[int, MessageNode] = {
            msg["id"]: {
                "id": msg["id"],
                "content": msg["content"],
                "parent_id": None,
                "child_ids": [],
            }
            for msg in messages
        }

        for link in links:
            parent = nodes.get(link["previous_message_id"])
            child = nodes.get(link["next_message_id"])

            child["parent_id"] = parent["id"]
            parent["child_ids"].append(child["id"])

        for node in nodes.values():
            if node["parent_id"] is None:  # Only root node will not have parent_id
                return node["id"], nodes

        raise AssertionError("root_message_id must exist for the message tree")

    def add_message(
        self, message_id: int, message_content: str, prev_message_id: Optional[int]
    ):
        """Adds message to the tree"""
        self.index[message_id] = {
            "id": message_id,
            "content": message_content,
            "parent_id": prev_message_id,
            "child_ids": [],
        }
        if prev_message_id is None:
            print("A new root node has been created")
            return
        print(
            f"A new message: {message_id} has been attached to message: {prev_message_id}"
        )
        self.index[prev_message_id]["child_ids"].append(message_id)


class SummaryTree:
    # WIP: Requires mechanism to track root and branch selections
    def __init__(self, message_tree: MessageTree, db: DB):

        self._db = db  # Used to fetch summaries from db
        self.message_tree = message_tree  # Used to walk the tree
        self.root_summary_id, self.index = self._load_index(self.message_tree.thread_id)

    def _load_index(self, thread_id: int):
        """Loads the index for quick sunmmary traceability"""

        # Index components
        id_lookup: dict[int, SummaryNode] = {}
        start_message_lookup: dict[int, int] = {}
        end_message_lookup: dict[int, int] = {}

        # Load compnents
        summaries = self._db.fetch_summaries(thread_id)
        for summary in summaries:
            node: SummaryNode = {
                "id": summary["id"],
                "content": summary["content"],
                "start_message_id": summary["start_message_id"],
                "end_message_id": summary["end_message_id"],
                "parent_id": None,
                "child_ids": [],
            }
            id_lookup[summary["id"]] = node
            start_message_lookup[summary["start_message_id"]] = summary["id"]
            end_message_lookup[summary["end_message_id"]] = summary["id"]

        # Map summaries
        for summary in summaries:
            # Find parent
            parent_end_message_id = self.message_tree.index[
                summary["start_message_id"]
            ]["parent_id"]
            if parent_end_message_id:
                parent_id = end_message_lookup[parent_end_message_id]
                id_lookup[summary["id"]]["parent_id"] = parent_id

            # Find children
            for child_start_message_id in self.message_tree.index[
                summary["end_message_id"]
            ]["child_ids"]:
                if child_start_message_id not in start_message_lookup:
                    continue
                child_id = start_message_lookup[child_start_message_id]
                id_lookup[summary["id"]]["child_ids"].append(child_id)

        # Intended: Will default to None, if the summary does not exist!
        root_summary_id = start_message_lookup.get(self.message_tree.root_message_id)
        return root_summary_id, SummaryIndex(
            start_message_lookup, end_message_lookup, id_lookup
        )

    def add_summary(
        self, summary_id: int, content: str, start_message_id: int, end_message_id: int
    ):
        """Adds summary to the summary tree, and the associated lookups"""
        prev_summary_end_message_id = self.message_tree.index[start_message_id][
            "parent_id"
        ]
        if prev_summary_end_message_id:
            summary_parent = self.index.end_message_lookup[
                self.message_tree.index[start_message_id]["parent_id"]
            ]
        else:
            summary_parent = None

        summary: SummaryNode = {
            "id": summary_id,
            "content": content,
            "start_message_id": start_message_id,
            "end_message_id": end_message_id,
            "parent_id": summary_parent,
            "child_ids": [],
        }
        if prev_summary_end_message_id is not None:
            prev_summary_id = self.index.end_message_lookup[prev_summary_end_message_id]
            self.index.summary_id_lookup[prev_summary_id]["child_ids"].append(
                summary_id
            )
        self.index.summary_id_lookup[summary_id] = summary
        self.index.start_message_lookup[start_message_id] = summary_id
        self.index.end_message_lookup[end_message_id] = summary_id

    def count_unsummarized_messages(self, message_id: int):
        """
        Strictly assumes that message_id is either the end node of a summary,
        or message_id is yet to be summarized.
        """
        count = 0
        while (message_id is not None) and (
            message_id not in self.index.end_message_lookup
        ):
            count += 1
            message_id = self.message_tree.index[message_id]["parent_id"]
        return count

    def is_summarized(self, message_id: int) -> bool:
        """
        Determines if the message is already a part of a summary.
        For this, if iterated forward, an end_message_id for a summary must be detected.
        """
        while True:
            # Summary exists
            if message_id in self.index.end_message_lookup:
                return True
            child_ids = self.message_tree.index[message_id]["child_ids"]
            # After having run through the messages
            if child_ids == []:
                return False
            # Within a summary, there can only be linear chain of messages.
            # Even for non-summarized messages, a branch-off forces summary generation.
            assert len(child_ids) == 1
            message_id = child_ids[0]

        # No returns. This must fail loudly

    def split_summary(
        self,
        summary_id: int,
        pre_summary_id: int,  # pre summary details
        pre_summary_content: str,
        branch_off_message_id: int,
        post_summary_id: int,  # post summary details
        post_summary_content: str,
    ):
        """
        Replaces the summary identfied by _id, with two summaries
        consisting of pre-and post of splitting at the branch_odd_message_id
        """
        summary = self.index.summary_id_lookup[summary_id]
        # Delete summary from indices!
        del self.index.summary_id_lookup[summary_id]
        del self.index.start_message_lookup[summary["start_message_id"]]
        del self.index.end_message_lookup[summary["end_message_id"]]
        # create new summaries with old summary
        pre_summary: SummaryNode = {
            "id": pre_summary_id,
            "content": pre_summary_content,
            "parent_id": summary["parent_id"],
            "start_message_id": summary["start_message_id"],
            "end_message_id": branch_off_message_id,
            "child_ids": [post_summary_id],
        }
        post_summary: SummaryNode = {
            "id": post_summary_id,
            "content": post_summary_content,
            "parent_id": pre_summary_id,
            # A summary consists of linear chain only, so the below statement is valid
            "start_message_id": self.message_tree.index[branch_off_message_id][
                "child_ids"
            ][0],
            "end_message_id": summary["end_message_id"],
            "child_ids": summary["child_ids"],
        }
        # Add summary nodes to lookup indices
        self.index.summary_id_lookup[pre_summary_id] = pre_summary
        self.index.summary_id_lookup[post_summary_id] = post_summary
        self.index.start_message_lookup[pre_summary["start_message_id"]] = (
            pre_summary_id
        )
        self.index.end_message_lookup[pre_summary["end_message_id"]] = pre_summary_id
        self.index.start_message_lookup[post_summary["start_message_id"]] = (
            post_summary_id
        )
        self.index.end_message_lookup[post_summary["end_message_id"]] = post_summary_id


class TreeCache:
    """LRU is a good policy to optimize long chat access"""

    def __init__(self, db: DB, max_capacity: int):
        self.cache: OrderedDict[int, tuple[MessageTree, SummaryTree]] = OrderedDict()
        self.db = db
        self.max_capacity = max_capacity
        self.curr_capacity = 0

    def get(self, thread_id: int) -> tuple[MessageTree, SummaryTree]:
        """Implements LRU elimination"""
        if self.cache.get(thread_id) is None:
            if self.max_capacity == self.curr_capacity:
                self.cache.popitem(last=True)  # Pop the last item in dict
                self.curr_capacity -= 1

            message_tree = MessageTree(thread_id, self.db)
            summary_tree = SummaryTree(message_tree, self.db)

            self.cache[thread_id] = (message_tree, summary_tree)
            self.curr_capacity += 1
            self.cache.move_to_end(thread_id, last=False)  # Move to front of dict

        return self.cache[thread_id]

    def delete(self, thread_id: int) -> None:
        """
        Deletes tree data from cache. Meant to trash invalid trees!
        Invalid trees are those, which are not in sync with the database
        """
        if self.cache.get(thread_id) is not None:
            del self.cache[thread_id]
