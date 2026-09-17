"""
agent/graph.py
================

Wires the four agent nodes (agent/nodes.py) into an actual LangGraph
``StateGraph``, attaches PostgreSQL-backed memory ("checkpointing"), and
exposes ``run_travel_agent()`` — the one function app.py calls to go from a
user message to a finished travel plan.

What is a StateGraph / checkpointer, in plain terms?
-----------------------------------------------------
- ``StateGraph`` is LangGraph's way of describing "run these functions in
  this order, sharing this state object." ``START`` and ``END`` are special
  markers for "where the graph begins" and "where it stops."
- A "checkpointer" is what makes the graph remember previous turns. Every
  time the graph runs, LangGraph saves a snapshot of the state to Postgres,
  keyed by a ``thread_id``. If a later request reuses the same
  ``thread_id``, LangGraph loads that snapshot back before running again.
  Without a checkpointer, every request would be a completely blank slate.

This module intentionally keeps the *same* graph shape as the original
single-file version (flight -> hotel -> itinerary -> final, in a straight
line, no branching) — only the file layout changed, not the pipeline logic.
"""

import uuid

import psycopg
from langchain_core.messages import HumanMessage
from langgraph.checkpoint.postgres import PostgresSaver
from langgraph.graph import END, START, StateGraph
from psycopg.rows import dict_row

from agent.config import get_database_url
from agent.nodes import final_agent, flight_agent, hotel_agent, itinerary_agent
from agent.state import TravelState

# ---------------------------------------------------------------------------
# Build the graph
# ---------------------------------------------------------------------------

graph = StateGraph(TravelState)

# Register each function from agent/nodes.py as a named node.
graph.add_node("flight_agent", flight_agent)
graph.add_node("hotel_agent", hotel_agent)
graph.add_node("itinerary_agent", itinerary_agent)
graph.add_node("final_agent", final_agent)

# Connect the nodes into a single straight-line pipeline:
# START -> flight_agent -> hotel_agent -> itinerary_agent -> final_agent -> END
graph.add_edge(START, "flight_agent")
graph.add_edge("flight_agent", "hotel_agent")
graph.add_edge("hotel_agent", "itinerary_agent")
graph.add_edge("itinerary_agent", "final_agent")
graph.add_edge("final_agent", END)


# ---------------------------------------------------------------------------
# PostgreSQL checkpointer (conversation memory)
# ---------------------------------------------------------------------------

DATABASE_URL = get_database_url()

# autocommit=True: each checkpoint write commits immediately instead of
# waiting inside a longer transaction, which is what PostgresSaver expects.
# row_factory=dict_row: makes psycopg return query rows as dicts (e.g.
# {"thread_id": ..., "checkpoint": ...}) instead of plain tuples, which is
# easier to read while debugging.
_conn = psycopg.connect(DATABASE_URL, autocommit=True, row_factory=dict_row)

checkpointer = PostgresSaver(_conn)

# Creates the checkpoint tables in Postgres the first time this runs; it is
# a no-op (safe to call every startup) if the tables already exist.
checkpointer.setup()

# The compiled, runnable graph. Compiling with a checkpointer is what
# enables the "same thread_id -> remembers previous turns" behavior.
travel_graph = graph.compile(checkpointer=checkpointer)


# ---------------------------------------------------------------------------
# Public entry point used by app.py
# ---------------------------------------------------------------------------


def run_travel_agent(user_input: str, thread_id: str | None = None) -> dict:
    """
    Run the full flight -> hotel -> itinerary -> final-answer pipeline for
    one user message, and return everything the FastAPI endpoint needs to
    build its JSON response.

    Args:
        user_input: The traveler's message, exactly as typed in the UI.
        thread_id: An identifier for the conversation. Pass the same
            thread_id on a follow-up request to let the checkpointer
            resume from where this conversation left off. If omitted, a
            new random thread_id is generated (i.e. this is treated as a
            brand-new conversation).

    Returns:
        dict: Contains the thread_id (so the frontend can remember it for
        the next request), the final answer text, and the intermediate
        flight_results/hotel_results/itinerary/llm_calls values — handy for
        debugging or for a future UI that wants to show the individual
        agent steps, not just the final answer.
    """
    if not thread_id:
        # No thread_id was supplied, so this is a brand-new conversation.
        # Generate a fresh, unique id for the checkpointer to key off of.
        thread_id = f"user_{uuid.uuid4().hex}"

    # LangGraph reads the thread_id from this "configurable" dict to decide
    # which saved checkpoint (if any) to resume from.
    config = {"configurable": {"thread_id": thread_id}}

    result = travel_graph.invoke(
        {
            "messages": [HumanMessage(content=user_input)],
            "user_query": user_input,
            "flight_results": "",
            "hotel_results": "",
            "itinerary": "",
            "llm_calls": 0,
        },
        config=config,
    )

    # final_agent's LLM response is always the last message in the list,
    # since it's the last node the graph runs before END.
    final_answer = result["messages"][-1].content

    return {
        "thread_id": thread_id,
        "answer": final_answer,
        "flight_results": result.get("flight_results", ""),
        "hotel_results": result.get("hotel_results", ""),
        "itinerary": result.get("itinerary", ""),
        "llm_calls": result.get("llm_calls", 0),
    }
