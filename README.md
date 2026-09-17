# TripMate Multi-Agent

TripMate AI is a small multi-agent travel planner. You type a request like
*"Plan a complete 7 day Japan trip from Taiwan under NT$60,000"*, and four
agents work through it in order — search flights, look up hotels, draft an
itinerary, then write the final answer — using [LangGraph](https://www.langchain.com/langgraph)
for orchestration and [FastAPI](https://fastapi.tiangolo.com/) for the web
server.

This README explains how the pieces fit together and how to run the
project locally. It's written at a "just started learning AI agents" level
on purpose — if a term below is unfamiliar, that's the point where it's
worth pausing and looking it up.

## How a request flows through the app

```
Browser (templates/index.html + static/)
        │  POST /api/travel { message, thread_id }
        ▼
app.py  (FastAPI route)
        │  calls run_travel_agent(...)
        ▼
agent/graph.py  (LangGraph pipeline, remembers past turns via Postgres)
        │
        ├─ flight_agent    → tools/flight_tool.py   (AviationStack API)
        ├─ hotel_agent     → tools/tavily_tool.py    (Tavily search API)
        ├─ itinerary_agent → agent/prompts.py + Groq LLM
        └─ final_agent     → agent/prompts.py + Groq LLM
        │
        ▼
JSON response { answer, flight_results, hotel_results, itinerary, ... }
```

Each agent is just a Python function that reads a shared `state` dict and
returns updates to it — see `agent/state.py` and `agent/nodes.py` for the
full explanation. This is the core idea behind LangGraph: it's a graph of
plain functions, not "AI agents" in some magical sense.

## Project layout

```
app.py                      FastAPI app: routes only, no agent logic
backend.py                  Backward-compatible shim -> agent/graph.py

agent/
  config.py                 Env vars, database URL, the Groq LLM client
  state.py                  TravelState: the shape of data passed between agents
  prompts.py                All LLM prompt text (system prompts + templates)
  nodes.py                  The 4 agent functions (flight/hotel/itinerary/final)
  graph.py                  Builds the LangGraph graph + Postgres checkpointer

tools/
  flight_tool.py            AviationStack wrapper (place name -> IATA -> live flights)
  tavily_tool.py            Tavily web-search wrapper, used for hotel lookups

templates/index.html        Single-page frontend
static/style.css            Styling, including the hero header + mega menu
static/script.js            Planner form, results rendering, PDF export
static/hero.js               Hero header animation + mega menu (see credit below)

scripts/manual_smoke_test.py  Manual script to sanity-check tools/tavily_tool.py
                               (not an automated test suite)

src/tripmate_multi_agent/   Unused scaffolding left over from `uv init` —
                             see the docstring in its __init__.py
```

This project intentionally keeps things as plain functions and files rather
than classes/frameworks-on-top-of-frameworks — that's a deliberate choice
while learning, not a limitation. As you get more comfortable, the docstring
in `src/tripmate_multi_agent/__init__.py` and the note in `backend.py`
point at one reasonable "next step" refactor (consolidating everything
under one installable package) that wasn't done here to keep this change
focused.

## Setup

1. Install [uv](https://docs.astral.sh/uv/) if you don't have it yet.

2. Install the project's dependencies (this reads `pyproject.toml` /
   `uv.lock` and creates a `.venv/` folder — you do **not** need to run
   `uv init`, since the project already exists):
   ```bash
   uv sync
   ```

3. Activate the virtual environment:
   - **Mac/Linux:**
     ```bash
     source .venv/bin/activate
     ```
   - **Windows:**
     ```bash
     .venv\Scripts\activate
     ```

4. Copy the environment template and fill in your own API keys:
   ```bash
   cp .env.template .env
   ```
   See `.env.template` for what each variable is for and where to get it
   (AviationStack, Groq, Tavily, and a PostgreSQL `DATABASE_URL`).

5. Run the app:
   ```bash
   uv run python app.py
   ```
   or, equivalently:
   ```bash
   uv run uvicorn app:app --reload
   ```
   Then open http://127.0.0.1:8000 in your browser.

## Frontend credit

The full-screen hero header and the overlay "mega menu" (opened by the
hamburger icon in the top-right) are adapted from the CodePen
**"Codepen Challenge: Huge Headers/Mega Menus"** by
[Sicontis](https://codepen.io/Sicontis/pen/OJzOWxq), licensed under the MIT
License (see the credit comment at the top of the relevant sections in
`static/style.css` and `static/hero.js`). The layout, copy, images, and menu
content were adapted to fit TripMate; the animation technique (GSAP
`clip-path` reveals) is the original author's. The workflow design comes from [Build TripMate AI End-to-End: Multi-Agent Travel Planner ](https://github.com/entbappy/TripMate-AI-A-Multi-Agent-Travel-Planner-with-LangGraph/tree/main). 
