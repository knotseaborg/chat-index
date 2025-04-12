import pytest
from services.summary import Summarizer
from db.models import Message

# Replace this with an actual mocked ChatOpenAI or use langchain's FakeLLM
class FakeLLM:
    def invoke(self, messages):
        system = messages[0].content
        human = messages[1].content
        if "group" in system:
            return type("MockMsg", (), {"content": "[[0, 1], [2]]"})()
        if "summarize" in system:
            return type("MockMsg", (), {"content": "This is a summary."})()
        if "Determine if" in system:
            return type("MockMsg", (), {"content": "Yes"})()
        return type("MockMsg", (), {"content": "No"})()


@pytest.fixture
def summarizer():
    return Summarizer(llm=FakeLLM())


@pytest.fixture
def sample_messages():
    return [
        Message(id=1, content="Let's brainstorm UI ideas."),
        Message(id=2, content="What if we try semantic zoom?"),
        Message(id=3, content="Maybe we simplify the layout."),
    ]


def test_group_returns_groups(summarizer, sample_messages):
    result = summarizer.group(sample_messages)
    assert isinstance(result, list)
    assert len(result) == 2
    assert all(isinstance(group, list) for group in result)
    assert all(isinstance(msg, Message) for group in result for msg in group)


def test_generate_summary_returns_string(summarizer, sample_messages):
    summary = summarizer.generate_summary(sample_messages)
    assert isinstance(summary, str)
    assert len(summary) > 0


def test_detect_topic_shift_returns_boolean(summarizer):
    result = summarizer.detect_topic_shift("Let's talk about UI", "How about auth systems?")
    assert isinstance(result, bool)