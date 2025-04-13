import json
from langchain_openai import ChatOpenAI
from db.models import Message
from langchain_core.messages import HumanMessage, SystemMessage


class Summarizer:
    def __init__(self, llm: ChatOpenAI):
        self._llm = llm

    def group(self, messages: list[Message]) -> list[list[Message]]:
        with open("prompts/group_policy.txt", "r") as f:
            system_prompt = f.read()
        # Refer system prompt
        human_prompt = "\n".join(
            [f"{i}. {message.content}" for i, message in enumerate(messages)]
        )
        raw_response = self._llm.invoke(
            [SystemMessage(content=system_prompt), HumanMessage(content=human_prompt)]
        ).content
        try:
            groups = json.loads(raw_response)
            result = []
            for group in groups:
                result.append([messages[i] for i in group])
        except json.JSONDecodeError:
            raise ValueError(
                f"Failed to parse reponse into JSON formation: Raw output: {raw_response}"
            )

        return result

    def detect_topic_shift(self, prev_msg: str, new_msg: str) -> bool:
        with open("prompts/topic_shift_detection.txt", "r") as f:
            system_prompt = f.read()
        # Refer system prompt
        human_prompt = "\n".join(
            ["Previous Message:", prev_msg, "Current Message:", new_msg]
        )

        result = (
            self._llm.invoke(
                [
                    SystemMessage(content=system_prompt),
                    HumanMessage(content=human_prompt),
                ]
            )
            .content.strip()
            .lower()
        )
        return result.startswith("y")

    def generate_summary(self, contents: list[str]) -> str:
        with open("prompts/summary_generation.txt", "r") as f:
            system_prompt = f.read()
        # Refer system prompt
        human_prompt = "\n".join(
            ["Messages:", *[f"{i+1}. {content}" for i, content in enumerate(contents)]]
        )

        return self._llm.invoke(
            [SystemMessage(content=system_prompt), HumanMessage(content=human_prompt)]
        ).content.strip()
