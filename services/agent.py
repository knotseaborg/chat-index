import os
from typing import Annotated, TypedDict

from dotenv import load_dotenv
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from langgraph.checkpoint.memory import MemorySaver
from langchain_openai import ChatOpenAI
from langchain_core.messages import AIMessage

# Configurations
load_dotenv()


class Agent:
    """Components of a Chat Agent"""
    class State(TypedDict):
        messages: Annotated[list, add_messages]

    def __init__(self, llm: ChatOpenAI):
        self._llm = llm
        self._graph_builder = StateGraph(Agent.State)
        self._graph = None
        self._memory = MemorySaver()


    @property
    def graph(self):
        """Graphical connections within the chat. Can be extended with tools in the future"""
        if self._graph is None:

            def chatbot(state: Agent.State):
                return {"messages": [self._llm.invoke(state["messages"])]}

            self._graph_builder.add_node("chatbot", chatbot)

            self._graph_builder.add_edge(START, "chatbot")
            self._graph_builder.add_edge("chatbot", END)

            self._graph = self._graph_builder.compile(checkpointer=self._memory)
        return self._graph

    def generate_response(self, user_content: str, thread_id: str) -> str:
        """Generates the final response from the LLM"""
        for event in self.graph.stream(
            {"messages": [{"role": "user", "content": user_content}]},
            config = {"configurable": {"thread_id": thread_id}}
        ):
            for value in event.values():
                #print("Assistant: ", value["messages"][-1])
                if isinstance(value["messages"][-1], AIMessage):
                    return value["messages"][-1]



if __name__ == "__main__":
    llm = ChatOpenAI(model=os.getenv("OPENAI_MODEL"))
    chat = Agent(llm)
    x = chat.generate_response("Hello! My name is Reuben", "1")
    y = chat.generate_response("What is my name?", "1")

    print(x.content,y.content)