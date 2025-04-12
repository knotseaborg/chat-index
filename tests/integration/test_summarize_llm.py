import pytest
import os
from dotenv import load_dotenv
from services.summary import Summarizer
from db.models import Message

from langchain_openai import ChatOpenAI

# Configurations
load_dotenv()

llm = ChatOpenAI(model=os.getenv("OPENAI_MODEL"))

@pytest.fixture
def summarizer():
    return Summarizer(llm)


@pytest.fixture
def messages():
    return [
        Message(id=1, content="Let's design a new UI system."),
        Message(id=2, content="How about semantic zooming?"),
        Message(id=3, content="Could also use TUI as a fallback."),
    ]


def test_grouping(summarizer, messages):
    result = summarizer.group(messages)
    assert isinstance(result, list)
    assert all(isinstance(g, list) for g in result)
    assert all(isinstance(m, Message) for g in result for m in g)


def test_summary_generation(summarizer, messages):
    summary = summarizer.generate_summary(messages)
    assert isinstance(summary, str)


def test_topic_shift_detection(summarizer):
    result = summarizer.detect_topic_shift("We should refactor the database.", "Let's switch to real-time analytics.")
    assert isinstance(result, bool)
    assert result is True
