"""
agent/nodes.py
================

The four "agents" (LangGraph nodes) that make up TripMate's pipeline.

What is a "node" in LangGraph?
--------------------------------
A node is just a plain Python function that takes the current TravelState
(see agent/state.py) and returns a dict with the fields it wants to update.
LangGraph calls each node in the order defined by the edges in
agent/graph.py, and merges every returned dict back into the shared state
before passing it to the next node. None of these functions call each
other directly — the graph in agent/graph.py is what decides the order.

The four nodes here run in this order (see agent/graph.py for the edges):

    flight_agent -> hotel_agent -> itinerary_agent -> final_agent

- flight_agent and hotel_agent are "tool-calling" nodes: they don't use the
  LLM at all, they just call a plain Python function (in tools/) that hits
  an external API and returns text.
- itinerary_agent and final_agent are "LLM" nodes: they build a prompt (see
  agent/prompts.py) from the state collected so far and ask the LLM to
  write something.
"""

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from agent.config import llm
from agent.prompts import (
    SYSTEM_FINAL_RESPONSE,
    SYSTEM_ITINERARY_PLANNER,
    build_final_prompt,
    build_itinerary_prompt,
)
from agent.state import TravelState
from tools.flight_tool import search_flights
from tools.tavily_tool import tavily_search


def flight_agent(state: TravelState) -> dict:
    """
    First node in the graph. Calls the AviationStack-backed flight search
    tool (tools/flight_tool.py) with the traveler's raw query and stores the
    result on the state as ``flight_results``.

    This node does not call the LLM at all — ``search_flights`` does its own
    parsing of the query (e.g. figuring out departure/arrival airports), so
    there's nothing for an LLM to add here.

    Args:
        state: Current TravelState. Only ``user_query`` is read.

    Returns:
        dict: Partial state update with the flight results, a short status
        message appended to ``messages``, and the incremented LLM-call
        counter (kept even though this node makes zero LLM calls, so the
        counter's meaning stays "how many pipeline steps have run so far").
    """
    query = state["user_query"]
    flight_data = search_flights(query)

    return {
        "flight_results": flight_data,
        "messages": [AIMessage(content="Flight results fetched.")],
        "llm_calls": state.get("llm_calls", 0) + 1,
    }


def hotel_agent(state: TravelState) -> dict:
    """
    Second node in the graph. Calls the Tavily web-search tool
    (tools/tavily_tool.py) to look up hotel recommendations for the
    traveler's destination and stores the result as ``hotel_results``.

    Like flight_agent, this node does not call the LLM — it just wraps a
    plain search call and hands the raw text downstream for
    itinerary_agent and final_agent to summarize.

    Args:
        state: Current TravelState. Only ``user_query`` is read.

    Returns:
        dict: Partial state update with the hotel results.
    """
    query = f"Best hotels for {state['user_query']}"
    hotel_results = tavily_search(query)

    return {
        "hotel_results": hotel_results,
        "messages": [AIMessage(content="Hotel information fetched.")],
        "llm_calls": state.get("llm_calls", 0) + 1,
    }


def itinerary_agent(state: TravelState) -> dict:
    """
    Third node in the graph. This is the first node that actually calls the
    LLM: it builds a prompt from everything collected so far (the traveler's
    request plus the flight/hotel results) and asks the model to draft a
    day-by-day itinerary.

    Args:
        state: Current TravelState. Reads ``user_query``, ``flight_results``,
            and ``hotel_results``.

    Returns:
        dict: Partial state update with the drafted ``itinerary`` text and
        the LLM's raw response appended to ``messages`` (so the final
        answer, further down the graph, has the full conversation history
        available if needed).
    """
    prompt = build_itinerary_prompt(state)

    response = llm.invoke(
        [
            SystemMessage(content=SYSTEM_ITINERARY_PLANNER),
            HumanMessage(content=prompt),
        ]
    )

    return {
        "itinerary": response.content,
        "messages": [response],
        "llm_calls": state.get("llm_calls", 0) + 1,
    }


def final_agent(state: TravelState) -> dict:
    """
    Last node in the graph. Combines the traveler's request, the flight and
    hotel results, and the drafted itinerary into the single Markdown
    answer that the FastAPI endpoint returns to the frontend.

    Args:
        state: Current TravelState. Reads ``user_query``, ``flight_results``,
            ``hotel_results``, and ``itinerary``.

    Returns:
        dict: Partial state update with the LLM's final response appended
        to ``messages``. app.py reads ``result["messages"][-1].content`` as
        the answer shown to the user (see agent/graph.py's
        ``run_travel_agent``).
    """
    final_prompt = build_final_prompt(state)

    response = llm.invoke(
        [
            SystemMessage(content=SYSTEM_FINAL_RESPONSE),
            HumanMessage(content=final_prompt),
        ]
    )

    return {"messages": [response], "llm_calls": state.get("llm_calls", 0) + 1}
