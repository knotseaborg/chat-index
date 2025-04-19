import json
from typing import Optional

from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage

from db.models import Message


class LLMOps:
    def __init__(self, llm: ChatOpenAI):
        self._llm = llm

    def group(self, messages: list[Message]) -> list[list[Message]]:
        """Groups Messages such that they each group can form coherent summaries"""
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
        except json.JSONDecodeError as exc:
            raise ValueError(
                f"Failed to parse reponse into JSON formation: Raw output: {raw_response}"
            ) from exc

        return result

    def detect_topic_shift(self, prev_msg: Optional[str], new_msg: str) -> bool:
        """Detectss topic shift between messages"""

        if prev_msg is None:
            print(
                "This message does not have a previous message, thus summary cannot be generated"
            )
            return False

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
        """A simple prompt to generate summaries for a given list of strings"""
        with open("prompts/summary_generation.txt", "r") as f:
            system_prompt = f.read()
        # Refer system prompt
        human_prompt = "\n".join(
            ["Messages:", *[f"{i+1}. {content}" for i, content in enumerate(contents)]]
        )

        return self._llm.invoke(
            [SystemMessage(content=system_prompt), HumanMessage(content=human_prompt)]
        ).content.strip()
