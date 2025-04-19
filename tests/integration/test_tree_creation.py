import pytest

from db.db import DB
from services.chat_trees import TreeCache


# Setup test DB
@pytest.fixture
def db():
    return DB("sqlite:///:memory:")


# Dummy LLM Ops
class DummyLLMOps:
    def generate_summary(self, contents):
        return f"Summary({len(contents)} messages)"

    def detect_topic_shift(self, prev, curr):
        return "NEW_TOPIC" in curr


# 🌲 TEST 1.1: Linear message chain
def test_linear_chain_cache_builds_correctly(db):
    tree_cache = TreeCache(db, 2)
    thread_id = db.insert_thread()

    m1_id = db.insert_message(thread_id=thread_id, content="Message A")
    m2_id = db.insert_message(thread_id=thread_id, content="Message B")
    m3_id = db.insert_message(thread_id=thread_id, content="Message C")
    db.insert_link(thread_id, prev_msg_id=m1_id, next_msg_id=m2_id)
    db.insert_link(thread_id, prev_msg_id=m2_id, next_msg_id=m3_id)

    # Trigger cache load
    message_tree, _ = tree_cache.get(thread_id)

    # ASSERTIONS
    # assert len(message_tree.roots) == 1
    assert message_tree.index[m1_id]["child_ids"] == [m2_id]
    assert message_tree.index[m2_id]["child_ids"] == [m3_id]
    assert message_tree.index[m3_id]["child_ids"] == []
    assert message_tree.index[m2_id]["parent_id"] == m1_id
    assert message_tree.index[m3_id]["parent_id"] == m2_id
