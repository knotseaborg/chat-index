from typing import Optional, TypedDict
from dataclasses import dataclass, field
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
    parent_id: int
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


class ChatTree:
    def __init__(self, thread_id: int, db: DB):
        self._db = db
        self.message_index = self._load_message_tree(thread_id)
        self.summary_index = self._load_summary_index(thread_id)

    def _load_message_tree(self, thread_id: int) -> dict[int, MessageNode]:
        """
        Builds an in-memory tree of messages from the thread's links.
        Returns a dict of message_id → MessageNode
        """

        messages = self._db.fetch_messages(thread_id)
        links = self._db.fetch_links(thread_id)

        nodes: dict[int, MessageNode] = {
            msg.id: {
                "id": msg.id,
                "content": msg.content,
                "parent_id": None,
                "child_ids": [],
            }
            for msg in messages
        }

        for link in links:
            parent = nodes.get(link.previous_message_id)
            child = nodes.get(link.next_message_id)

            child["parent_id"] = parent["id"]
            parent["child_ids"].append(child["id"])

        return nodes  # You can now traverse from any node

    def _load_summary_index(self, thread_id: int):
        """Loads the index for quick sunmmary traceability"""

        # Index components
        id_lookup: dict[int, SummaryNode] = {}
        start_message_lookup: dict[int, int] = {}
        end_message_lookup: dict[int, int] = {}
        
        # Load compnents
        summaries = self._db.fetch_summaries(thread_id)
        for summary in summaries:
            node: SummaryNode = {
                "id": summary.id,
                "content": summary.content,
                "start_message_id": summary.start_message_id,
                "end_message_id": summary.end_message_id,
                "parent_id": None,
                "child_ids": [],
            }
            id_lookup[summary.id] = node
            start_message_lookup[summary.start_message_id] = summary.id
            end_message_lookup[summary.end_message_id] = summary.id

        # Map summaries
        for summary in summaries:
            # Find parent
            parent_end_message_id = self.message_index[summary.start_message_id]["parent_id"]
            parent_id = end_message_lookup[parent_end_message_id]
            id_lookup[summary.id]["parent_id"] = parent_id

            # Find children
            for child_start_message_id in self.message_index[summary.end_message_id]["child_ids"]:
                child_id = start_message_lookup[child_start_message_id]
                id_lookup[summary.id]["child_ids"].append(child_id)

        return SummaryIndex(start_message_lookup, end_message_lookup, id_lookup)
