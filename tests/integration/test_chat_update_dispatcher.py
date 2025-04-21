"""
Integration tests for TreeCache, which maintains an in-memory tree structure of messages and summaries
linked to a given chat thread. These tests validate the structural correctness of both message trees
and summary trees.

Components under test:
- message_tree: maintains parent-child relationships between messages
- summary_tree: maintains hierarchical summaries over the message tree

Test coverage:
1. Message insertion into message_tree
    1. With summary check triggered
    2. Without summary check
3. Does summary generation respect the min-count?
4. Splitting an existing summary5
"""

import pytest

from db.db import DB
from services.dispatcher import Handler, ChatUpdateDispatcher
from services.chat_trees import TreeCache


@pytest.fixture
def db():
    """
    Returns a DB instance connected to an in-memory SQLite database.
    Used for isolating tests without persistence.
    """
    return DB("sqlite:///:memory:")


@pytest.fixture
def tree_cache():
    return TreeCache(db, 2)


class DummyLLMOps:
    """Dummy class for mocking LLM operations."""

    def generate_summary(self, contents):
        return f"Summary({len(contents)} messages)"

    def detect_topic_shift(self, prev, curr):
        return "new" in curr.lower()


def test_dispatcher_add_message(db, tree_cache):
    """
    Test whether message_tree correctly maintains parent-child relationships
    when inserting messages in a branching structure.
    """
    thread_id = db.insert_thread()
    tree_cache = TreeCache(db, 2)
    handler = Handler(db, tree_cache, DummyLLMOps())
    chat_dispatcher = ChatUpdateDispatcher(handler)

    # Build message tree
    chat_dispatcher.dispatch(
        "add_message",
        {
            "content": "Message A",
            "thread_id": thread_id,
            "prev_message_id": None,
            "trigger_summarization": True,
            "summary_batch_size": 1,
        },
    )
    chat_dispatcher.dispatch(
        "add_message",
        {
            "content": "Message B",
            "thread_id": thread_id,
            "prev_message_id": 1,
            "trigger_summarization": True,
            "summary_batch_size": 1,
        },
    )
    chat_dispatcher.dispatch(
        "add_message",
        {
            "content": "new Message C",
            "thread_id": thread_id,
            "prev_message_id": 2,
            "trigger_summarization": True,
            "summary_batch_size": 1,
        },
    )

    message_tree, summary_tree = tree_cache.get(thread_id)
    print(message_tree.index)
    assert message_tree.index[1]["child_ids"] == [2]
    assert message_tree.index[2]["child_ids"] == [3]
    assert message_tree.index[2]["parent_id"] == 1
    assert message_tree.index[3]["parent_id"] == 2
    assert summary_tree.index.summary_id_lookup[1]["start_message_id"] == 1
    assert summary_tree.index.summary_id_lookup[1]["end_message_id"] == 2


def test_dispatcher_add_summary(db, tree_cache):
    """
    Test whether message_tree correctly maintains parent-child relationships
    when inserting messages in a branching structure.
    """
    thread_id = db.insert_thread()
    tree_cache = TreeCache(db, 2)
    handler = Handler(db, tree_cache, DummyLLMOps())
    chat_dispatcher = ChatUpdateDispatcher(handler)

    # Build message tree
    chat_dispatcher.dispatch(
        "add_message",
        {
            "content": "new Message A",
            "thread_id": thread_id,
            "prev_message_id": None,
            "trigger_summarization": True,
            "summary_batch_size": 2,
        },
    )
    chat_dispatcher.dispatch(
        "add_message",
        {
            "content": "new Message B",
            "thread_id": thread_id,
            "prev_message_id": 1,
            "trigger_summarization": True,
            "summary_batch_size": 2,
        },
    )
    chat_dispatcher.dispatch(
        "add_message",
        {
            "content": "new Message C",
            "thread_id": thread_id,
            "prev_message_id": 2,
            "trigger_summarization": True,
            "summary_batch_size": 2,
        },
    )
    chat_dispatcher.dispatch(
        "add_message",
        {
            "content": "new Message D",
            "thread_id": thread_id,
            "prev_message_id": 2,
            "trigger_summarization": True,
            "summary_batch_size": 2,
        },
    )

    message_tree, summary_tree = tree_cache.get(thread_id)
    print(summary_tree.index.summary_id_lookup)
    assert message_tree.index[1]["child_ids"] == [2]
    assert message_tree.index[2]["child_ids"] == [3, 4]
    assert message_tree.index[2]["parent_id"] == 1
    assert message_tree.index[3]["parent_id"] == 2
    assert message_tree.index[4]["parent_id"] == 2
    assert summary_tree.index.summary_id_lookup[1]["start_message_id"] == 1
    assert summary_tree.index.summary_id_lookup[1]["end_message_id"] == 2


def test_dispatcher_split_summary(db, tree_cache):
    """
    Test whether message_tree correctly maintains parent-child relationships
    when inserting messages in a branching structure.
    """
    thread_id = db.insert_thread()
    tree_cache = TreeCache(db, 2)
    handler = Handler(db, tree_cache, DummyLLMOps())
    chat_dispatcher = ChatUpdateDispatcher(handler)

    # Build message tree
    chat_dispatcher.dispatch(
        "add_message",
        {
            "content": "new Message A",
            "thread_id": thread_id,
            "prev_message_id": None,
            "trigger_summarization": True,
            "summary_batch_size": 2,
        },
    )
    chat_dispatcher.dispatch(
        "add_message",
        {
            "content": "new Message B",
            "thread_id": thread_id,
            "prev_message_id": 1,
            "trigger_summarization": True,
            "summary_batch_size": 2,
        },
    )
    chat_dispatcher.dispatch(
        "add_message",
        {
            "content": "new Message C",
            "thread_id": thread_id,
            "prev_message_id": 2,
            "trigger_summarization": True,
            "summary_batch_size": 2,
        },
    )
    chat_dispatcher.dispatch(
        "add_message",
        {
            "content": "new Message D",
            "thread_id": thread_id,
            "prev_message_id": 2,
            "trigger_summarization": True,
            "summary_batch_size": 2,
        },
    )

    message_tree, summary_tree = tree_cache.get(thread_id)
    print(summary_tree.index.summary_id_lookup)
    assert message_tree.index[1]["child_ids"] == [2]
    assert message_tree.index[2]["child_ids"] == [3, 4]
    assert message_tree.index[2]["parent_id"] == 1
    assert message_tree.index[3]["parent_id"] == 2
    assert message_tree.index[4]["parent_id"] == 2
    assert summary_tree.index.summary_id_lookup[1]["start_message_id"] == 1
    assert summary_tree.index.summary_id_lookup[1]["end_message_id"] == 2

    chat_dispatcher.dispatch(
        "branch_off", {"thread_id": thread_id, "branch_off_message_id": 1}
    )

    message_tree, summary_tree = tree_cache.get(thread_id)

    # sqlite reuses auto-inc ids, so totally there must not be 3 summarys (old summary shouldn't exist)
    assert 3 not in summary_tree.index.summary_id_lookup
    assert summary_tree.index.summary_id_lookup[1]["start_message_id"] == 1
    assert summary_tree.index.summary_id_lookup[1]["end_message_id"] == 1
    assert summary_tree.index.summary_id_lookup[2]["start_message_id"] == 2
    assert summary_tree.index.summary_id_lookup[2]["end_message_id"] == 2
