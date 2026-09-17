"""
tools package
=============

Plain Python wrappers around the external APIs TripMate's agents call.
Each function here returns a plain string (not a dict, not a custom class)
that is meant to be dropped straight into an LLM prompt — that's why they
format their results as readable text instead of returning raw JSON.

- ``flight_tool.py`` -> searches live flight data via the AviationStack API.
- ``tavily_tool.py`` -> general web search via the Tavily API, used here to
  look up hotel recommendations.

Neither module depends on LangGraph or the agent package — they could be
imported and used completely on their own, which is why they were pulled
out into their own package in the first place. agent/nodes.py is the only
place that calls into them.
"""
