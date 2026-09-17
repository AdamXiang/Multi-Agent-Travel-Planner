"""
agent package
=============

This package holds the "brain" of TripMate: the LangGraph multi-agent
pipeline that turns one user message (e.g. "Plan a 7 day Japan trip from
Taiwan under NT$60,000") into a full travel plan.

Why this package exists
------------------------
Everything used to live in a single ``backend.py`` file at the project root.
That worked, but as the project grew it became hard to find things (state?
prompts? the graph wiring? all mixed together). Splitting it into small,
single-purpose modules makes it much easier to learn and to change one part
without accidentally breaking another:

- ``agent/config.py``  -> environment variables, the Groq LLM client, and the
  PostgreSQL connection string.
- ``agent/state.py``   -> the shape of the data ("state") that flows between
  agents while the graph runs.
- ``agent/prompts.py`` -> the actual text we send to the LLM (system prompts
  + prompt templates). Kept separate so prompts can be tweaked without
  touching any orchestration logic.
- ``agent/nodes.py``   -> the four agent functions themselves
  (flight_agent, hotel_agent, itinerary_agent, final_agent).
- ``agent/graph.py``   -> wires the nodes together into a LangGraph
  ``StateGraph``, attaches the PostgreSQL checkpointer (conversation
  memory), and exposes ``run_travel_agent()`` for the FastAPI app to call.

This file is intentionally left almost empty. We deliberately do NOT
re-export things here (e.g. no ``from .graph import run_travel_agent``)
because that would make Python import the whole graph (and open a database
connection!) the moment *anything* from this package is imported, which is
surprising behavior for a beginner codebase. Instead, import directly from
the module you need, e.g.:

    from agent.graph import run_travel_agent
    from agent.state import TravelState
"""
