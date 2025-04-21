"""
Integration tests for tree construction and mutation via the ChatUpdateDispatcher.

Test Coverage:
1. Message insertion into message_tree
    a. With summary generation triggered
    b. Without summary generation
2. Summary generation behavior:
    a. Ensures minimum message count is respected
    b. Triggered only upon topic shift
3. Summary integrity:
    a. Summaries span correct message IDs
    b. Summary tree accurately reflects message tree state
4. Summary splitting:
    a. Old summary is replaced by two new ones
    b. Summary span is correctly split across message IDs
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


class DummyLLMOps:
    """
    Dummy class for mocking LLM operations during testing.
    - `generate_summary`: returns dummy text based on number of messages.
    - `detect_topic_shift`: returns True if the current message contains "new".
    """

    def generate_summary(self, contents):
        return f"Summary({len(contents)} messages)"

    def detect_topic_shift(self, prev, curr):
        return "new" in curr.lower()


@pytest.fixture
def tree_cache(db):
    """
    TreeCache instance for testing, with summary window size of 2.
    """
    return TreeCache(db, 2)


def test_dispatcher_add_message(db, tree_cache):
    """
    Validates message insertion and tree reconstruction.
    - Ensures parent-child links are correctly created in the message tree.
    - Confirms that summary is generated and reflects correct span.
    """

    thread_id = db.insert_thread()
    handler = Handler(db, tree_cache, DummyLLMOps())
    chat_dispatcher = ChatUpdateDispatcher(handler)

    # Insert 3 messages; summary should trigger after 2nd message due to batch size.
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
            "content": "new Message C",  # triggers topic shift
            "thread_id": thread_id,
            "prev_message_id": 2,
            "trigger_summarization": True,
            "summary_batch_size": 1,
        },
    )

    message_tree, summary_tree = tree_cache.get(thread_id)

    # Message tree structure
    assert message_tree.index[1]["child_ids"] == [2]
    assert message_tree.index[2]["child_ids"] == [3]
    assert message_tree.index[2]["parent_id"] == 1
    assert message_tree.index[3]["parent_id"] == 2

    # Summary spans messages 1-2
    assert summary_tree.index.summary_id_lookup[1]["start_message_id"] == 1
    assert summary_tree.index.summary_id_lookup[1]["end_message_id"] == 2


def test_dispatcher_add_summary(db, tree_cache):
    """
    Tests summary generation based on batch size and topic shift.
    - Ensures summary is only generated when enough messages have accumulated.
    - Verifies tree structure integrity when branching occurs.
    """

    thread_id = db.insert_thread()
    handler = Handler(db, tree_cache, DummyLLMOps())
    chat_dispatcher = ChatUpdateDispatcher(handler)

    # Insert 4 messages: 3 in a chain, 1 as branch off the 2nd
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
            "prev_message_id": 2,  # Fork from message 2
            "trigger_summarization": True,
            "summary_batch_size": 2,
        },
    )

    message_tree, summary_tree = tree_cache.get(thread_id)

    # Message tree integrity
    assert message_tree.index[1]["child_ids"] == [2]
    assert message_tree.index[2]["child_ids"] == [3, 4]
    assert message_tree.index[2]["parent_id"] == 1
    assert message_tree.index[3]["parent_id"] == 2
    assert message_tree.index[4]["parent_id"] == 2

    # Summary spans messages 1–2
    assert summary_tree.index.summary_id_lookup[1]["start_message_id"] == 1
    assert summary_tree.index.summary_id_lookup[1]["end_message_id"] == 2


def test_dispatcher_split_summary(db, tree_cache):
    """
    Validates the behavior of `split_summary`.
    - Confirms that an existing summary is split correctly into two summaries.
    - Ensures the old summary is deleted and IDs are reused (SQLite auto-inc behavior).
    """

    thread_id = db.insert_thread()
    handler = Handler(db, tree_cache, DummyLLMOps())
    chat_dispatcher = ChatUpdateDispatcher(handler)

    # Build initial summary
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

    # Pre-split assertions
    message_tree, summary_tree = tree_cache.get(thread_id)
    assert summary_tree.index.summary_id_lookup[1]["start_message_id"] == 1
    assert summary_tree.index.summary_id_lookup[1]["end_message_id"] == 2

    # Perform the split
    chat_dispatcher.dispatch(
        "branch_off", {"thread_id": thread_id, "branch_off_message_id": 1}
    )

    # Post-split validation
    message_tree, summary_tree = tree_cache.get(thread_id)
    assert (
        3 not in summary_tree.index.summary_id_lookup
    )  # old summary should not be reused
    assert summary_tree.index.summary_id_lookup[1]["start_message_id"] == 1
    assert summary_tree.index.summary_id_lookup[1]["end_message_id"] == 1
    assert summary_tree.index.summary_id_lookup[2]["start_message_id"] == 2
    assert summary_tree.index.summary_id_lookup[2]["end_message_id"] == 2
