"""
Integration tests for the LLMOps service, which encapsulates large language model (LLM)
interactions such as message grouping, summarization, and topic shift detection.

These tests verify that:
- Message grouping returns a list of message clusters.
- Summarization generates valid output from a list of messages.
- Topic shift detection identifies semantic boundaries between two messages.

NOTE: These tests use the actual OpenAI model via `langchain_openai.ChatOpenAI`.
Ensure API keys and models are correctly configured via .env.
"""

import pytest
import os
from dotenv import load_dotenv
from services.llm_ops import LLMOps
from db.models import Message
from langchain_openai import ChatOpenAI

# Load environment variables from .env
load_dotenv()

# Initialize the model (model name must be set in OPENAI_MODEL env var)
llm = ChatOpenAI(model=os.getenv("OPENAI_MODEL"))


@pytest.fixture
def llm_ops():
    """Provides an LLMOps instance configured with the OpenAI model."""
    return LLMOps(llm)


@pytest.fixture
def messages():
    """
    Provides a set of sample Message objects for testing LLM operations.
    Represents a small conversation thread about UI design.
    """
    return [
        Message(id=1, content="Let's design a new UI system."),
        Message(id=2, content="How about semantic zooming?"),
        Message(id=3, content="Could also use TUI as a fallback."),
    ]


def test_grouping(llm_ops, messages):
    """
    Tests that the group function correctly clusters messages.
    Ensures:
    - Return type is a list of message groups (each group is a list)
    - All returned objects are instances of Message
    """
    result = llm_ops.group(messages)

    assert isinstance(result, list), "Expected list of groups"
    assert all(isinstance(g, list) for g in result), "Each group must be a list"
    assert all(
        isinstance(m, Message) for g in result for m in g
    ), "Each item must be a Message instance"


def test_summary_generation(llm_ops, messages):
    """
    Tests that a summary is generated from a list of messages.
    Ensures:
    - Return type is a non-empty string
    """
    summary = llm_ops.generate_summary(messages)

    assert isinstance(summary, str), "Summary must be a string"
    assert len(summary.strip()) > 0, "Summary must not be empty"


def test_topic_shift_detection(llm_ops):
    """
    Tests that the topic shift detection logic correctly identifies change in topic.
    Ensures:
    - Return type is a boolean
    - Logical shift between database discussion and analytics triggers detection
    """
    result = llm_ops.detect_topic_shift(
        "We should refactor the database.", "Let's switch to real-time analytics."
    )

    assert isinstance(result, bool), "Return value must be boolean"
    assert result is True, "Expected topic shift to be detected"
