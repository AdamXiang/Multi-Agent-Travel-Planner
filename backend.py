"""
backend.py
============

Historical entry point for TripMate's agent logic.

This file used to contain the *entire* LangGraph pipeline — state
definition, prompts, all four agent functions, the graph wiring, and the
PostgreSQL checkpointer — in one long file. As the project grew that became
hard to navigate, so the logic has been split into the ``agent/`` package:

    agent/config.py   - environment variables, the Groq LLM client, the
                         database URL helper
    agent/state.py    - the TravelState TypedDict (what data flows between
                         agents)
    agent/prompts.py  - the LLM prompt templates used by the itinerary and
                         final-answer agents
    agent/nodes.py    - the four agent functions: flight_agent, hotel_agent,
                         itinerary_agent, final_agent
    agent/graph.py    - builds the LangGraph StateGraph, sets up the
                         PostgreSQL checkpointer, and exposes
                         run_travel_agent() for app.py to call

This file is kept only so that ``from backend import run_travel_agent``
keeps working if anything (or anyone) still imports it that way. New code
should import directly from ``agent.graph`` instead — that's what app.py
does now.

Note: a natural next step (not done here, to keep this refactor small)
would be moving the whole app under the existing src/tripmate_multi_agent/
package so the project has a single, proper package layout instead of a mix
of root-level scripts and an unused src/ package. See
src/tripmate_multi_agent/__init__.py for more on that.
"""

from agent.graph import run_travel_agent

__all__ = ["run_travel_agent"]
