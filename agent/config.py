"""
agent/config.py
================

Centralizes everything TripMate's agent pipeline needs to read from the
environment: API keys, the database connection string, and the LLM client.

Why put this in its own file?
------------------------------
Before this refactor, ``os.getenv(...)`` calls, the ``.env`` loading, and the
LLM client construction were all scattered inside ``backend.py`` next to the
agent logic. That made it hard to answer a simple question like "what
environment variables does this app actually need?" without reading the
whole file. Now there is exactly one place to look.

Nothing here is agent-specific logic — it is pure setup/configuration, which
is why it is imported by both ``agent/graph.py`` (for the database URL) and
``agent/nodes.py`` (for the ``llm`` client).
"""

import os

import certifi
from dotenv import load_dotenv
from langchain_groq import ChatGroq

# Load variables from a local .env file (if one exists) into the process
# environment. This has to run before we call os.getenv() below, otherwise
# the variables from .env would not be visible yet.
load_dotenv()

# Some corporate networks / older Python installs ship an outdated list of
# trusted certificate authorities, which makes HTTPS calls to the Groq,
# Tavily, and AviationStack APIs fail with SSL errors. Pointing both OpenSSL
# and the `requests` library at certifi's up-to-date CA bundle avoids that.
os.environ["SSL_CERT_FILE"] = certifi.where()
os.environ["REQUESTS_CA_BUNDLE"] = certifi.where()


def get_database_url() -> str:
    """
    Read and validate the PostgreSQL connection string used for LangGraph's
    checkpointer (this is what lets the agent "remember" a conversation
    across multiple requests when the frontend sends the same thread_id).

    Returns:
        str: A PostgreSQL connection URL with ``sslmode=require`` appended
        if it was not already present. Render's managed Postgres instances
        (and most cloud Postgres providers) expect SSL connections, so we
        add this automatically instead of making every developer remember
        to type it themselves.

    Raises:
        ValueError: If the ``DATABASE_URL`` environment variable is missing,
        since the app cannot start without somewhere to store conversation
        state.
    """
    database_url = os.getenv("DATABASE_URL")

    if not database_url:
        raise ValueError(
            "DATABASE_URL is missing. Please add your Render PostgreSQL "
            "External Database URL to .env"
        )

    if "sslmode=" not in database_url:
        # If the URL already has a "?something=..." query string, append
        # with "&"; otherwise start a new query string with "?".
        separator = "&" if "?" in database_url else "?"
        database_url = f"{database_url}{separator}sslmode=require"

    return database_url


# The Groq API key that authenticates every LLM call this app makes.
# We fail fast (at import time) instead of later inside a request, so a
# missing key shows up immediately when the server starts rather than as a
# confusing 500 error on the first user request.
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
if not GROQ_API_KEY:
    raise ValueError("GROQ_API_KEY is missing. Please add it to your .env file.")


# The single LLM client shared by every agent node that needs to call an
# LLM (itinerary_agent and final_agent). Reusing one client instance avoids
# recreating the HTTP session on every request.
#
# openai/gpt-oss-20b is a good general-purpose model for this project:
# fast (important since Groq is used specifically for low-latency inference)
# and capable enough to follow the multi-section formatting instructions in
# agent/prompts.py.
llm = ChatGroq(model="openai/gpt-oss-20b", api_key=GROQ_API_KEY)
