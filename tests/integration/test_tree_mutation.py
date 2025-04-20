"""
Integration tests for TreeCache, which maintains an in-memory tree structure of messages and summaries
linked to a given chat thread. These tests validate the structural correctness of both message trees
and summary trees.

Components under test:
- message_tree: maintains parent-child relationships between messages
- summary_tree: maintains hierarchical summaries over the message tree

Test coverage:
1. Message insertion into message_tree
2. Summary insertion into summary_tree
3. Counting unsummarized messages
4. Splitting an existing summary
"""

import pytest

from db.db import DB
from services.chat_trees import TreeCache


@pytest.fixture
def db():
    """
    Returns a DB instance connected to an in-memory SQLite database.
    Used for isolating tests without persistence.
    """
    return DB("sqlite:///:memory:")


class DummyLLMOps:
    """Dummy class for mocking LLM operations."""

    def generate_summary(self, contents):
        return f"Summary({len(contents)} messages)"

    def detect_topic_shift(self, prev, curr):
        return "new" in curr.lower()


def test_tree_add_message(db):
    """
    Test whether message_tree correctly maintains parent-child relationships
    when inserting messages in a branching structure.
    """
    tree_cache = TreeCache(db, 2)
    thread_id = db.insert_thread()
    message_tree, _ = tree_cache.get(thread_id)

    # Build message tree
    message_tree.add_message(0, "Message A", None)  # Root
    message_tree.add_message(1, "Message B", 0)
    message_tree.add_message(2, "Message C", 1)
    message_tree.add_message(3, "Message D", 0)  # Sibling branch

    index = message_tree.index
    assert index[0]["child_ids"] == [1, 3]
    assert index[1]["parent_id"] == 0
    assert index[1]["child_ids"] == [2]
    assert index[2]["parent_id"] == 1
    assert index[2]["child_ids"] == []
    assert index[3]["parent_id"] == 0
    assert index[3]["child_ids"] == []


def test_tree_add_summary(db):
    """
    Test whether summary_tree correctly builds a hierarchical summary tree
    over a branching message tree.
    """
    tree_cache = TreeCache(db, 2)
    thread_id = db.insert_thread()
    message_tree, summary_tree = tree_cache.get(thread_id)

    # Create a tree structure of messages
    message_tree.add_message(0, "Message A", None)
    message_tree.add_message(1, "Message B", 0)
    message_tree.add_message(2, "Message C", 1)
    message_tree.add_message(3, "Message D", 2)
    message_tree.add_message(4, "Message E", 1)
    message_tree.add_message(5, "Message F", 4)

    # Add summaries covering distinct branches
    summary_tree.add_summary(0, "Summary A", 0, 1)
    summary_tree.add_summary(1, "Summary B", 2, 3)
    summary_tree.add_summary(2, "Summary C", 4, 5)

    sml = summary_tree.index.start_message_lookup
    eml = summary_tree.index.end_message_lookup
    sil = summary_tree.index.summary_id_lookup

    # Check summary ID mapping by start and end messages
    assert sml[0] == 0
    assert sml[2] == 1
    assert sml[4] == 2
    assert eml[1] == 0
    assert eml[3] == 1
    assert eml[5] == 2

    # Check summary tree structure
    assert sil[0]["parent_id"] is None
    assert sil[0]["child_ids"] == [1, 2]
    assert sil[1]["parent_id"] == 0
    assert sil[1]["child_ids"] == []
    assert sil[2]["parent_id"] == 0
    assert sil[2]["child_ids"] == []


def test_tree_count_unsummarized_messages(db):
    """
    Test that the count_unsummarized_messages function correctly calculates
    the number of unsummarized messages along a given path in the message tree.
    """
    tree_cache = TreeCache(db, 2)
    thread_id = db.insert_thread()
    message_tree, summary_tree = tree_cache.get(thread_id)

    # Build a linear message chain
    message_tree.add_message(0, "Message A", None)
    message_tree.add_message(1, "Message B", 0)
    message_tree.add_message(2, "Message C", 1)
    message_tree.add_message(3, "Message D", 2)

    # No summaries yet, expect 4 messages in chain
    assert summary_tree.count_unsummarized_messages(3) == 4

    # Add a branched chain
    message_tree.add_message(4, "Message E", 1)
    message_tree.add_message(5, "Message F", 4)
    message_tree.add_message(6, "Message G", 5)
    message_tree.add_message(7, "Message H", 6)

    # Add summary to part of the tree
    summary_tree.add_summary(0, "Summary A", 0, 1)

    # Now the new branch should have 4 unsummarized messages
    assert summary_tree.count_unsummarized_messages(7) == 4


def test_tree_split_summary(db):
    """
    Test the behavior of splitting an existing summary in the summary tree.
    Ensures proper replacement and structural updates to summary tree.
    """
    tree_cache = TreeCache(db, 2)
    thread_id = db.insert_thread()
    message_tree, summary_tree = tree_cache.get(thread_id)

    # Create a two-message summary
    message_tree.add_message(0, "Message A", None)
    message_tree.add_message(1, "Message B", 0)
    summary_tree.add_summary(0, "Summary A", 0, 1)

    # Add a branching message that splits the range
    message_tree.add_message(2, "Message C", 0)

    # Split the existing summary into two
    summary_tree.split_summary(0, 1, "Summary A-pre", 0, 2, "Summary A-post")

    sml = summary_tree.index.start_message_lookup
    eml = summary_tree.index.end_message_lookup
    sil = summary_tree.index.summary_id_lookup

    # Original summary removed
    assert 0 not in sil

    # New structure
    assert sil[1]["parent_id"] is None
    assert sil[1]["child_ids"] == [2]
    assert sil[2]["parent_id"] == 1
    assert sil[2]["child_ids"] == []

    assert sml[0] == 1
    assert eml[0] == 1
    assert sml[1] == 2
    assert eml[1] == 2
