"""
agent/state.py
===============

Defines the "state" that flows through TripMate's LangGraph pipeline.

What is "state" in LangGraph?
------------------------------
LangGraph runs your pipeline as a graph of nodes (plain Python functions,
see agent/nodes.py) connected by edges (see agent/graph.py). Every node
receives the *same* shared dictionary-like object — the state — reads
whatever fields it needs, and returns a partial update. LangGraph then
merges that update back into the state before handing it to the next node.

Think of it as a shared clipboard that gets passed from agent to agent:
flight_agent writes flight_results on it, hotel_agent writes hotel_results,
itinerary_agent reads both of those and writes itinerary, and so on.

TravelState is a ``TypedDict`` (not a real class with methods) purely so
that type checkers and editors can tell us "hey, state['user_query'] is a
str" instead of state being an untyped dict. It has no behavior of its own.
"""

import operator
from typing import Annotated, TypedDict

from langchain_core.messages import AnyMessage


class TravelState(TypedDict):
    """
    Shared state object passed between every node in the travel-planning
    graph.

    Fields:
        messages: The running conversation history as LangChain message
            objects (HumanMessage, AIMessage, SystemMessage, ...).
            ``Annotated[list[AnyMessage], operator.add]`` tells LangGraph to
            *append* new messages to this list instead of overwriting it
            whenever a node returns a "messages" key — this is what
            LangGraph calls a "reducer". Without it, each node would erase
            the previous node's messages.
        user_query: The raw text the traveler typed in the UI, e.g.
            "Plan a complete 7 days Japan trip from Taiwan under NT$60,000."
        flight_results: Plain-text summary of flights found by flight_agent
            (tools/flight_tool.py). Empty string until that node runs.
        hotel_results: Plain-text summary of hotels found by hotel_agent
            (tools/tavily_tool.py). Empty string until that node runs.
        itinerary: The day-by-day plan written by itinerary_agent. Empty
            string until that node runs.
        llm_calls: A simple running counter of how many times we called the
            LLM during this request. Useful for debugging/cost tracking;
            it is not used for any control-flow decisions.
    """

    messages: Annotated[list[AnyMessage], operator.add]
    user_query: str
    flight_results: str
    hotel_results: str
    itinerary: str
    llm_calls: int
