"""
app.py
========

The FastAPI web server for TripMate AI.

This file is intentionally "thin": it only knows about HTTP concerns
(routes, request/response shapes, status codes). All of the actual
travel-planning logic lives in the ``agent`` package — see
``agent/graph.py`` for the LangGraph pipeline this calls into.

Routes:
    GET  /              -> serves the single-page frontend (templates/index.html)
    POST /api/travel     -> runs the multi-agent pipeline for one user message
    GET  /health         -> simple uptime check
    GET  /favicon.ico     -> avoids noisy 404s in the server logs from browsers
                             auto-requesting a favicon we don't have
"""

import traceback
from pathlib import Path

import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

from agent.graph import run_travel_agent

# Resolve paths relative to this file's location (not the current working
# directory), so the app still finds static/ and templates/ correctly no
# matter where `uvicorn` is launched from.
BASE_DIR = Path(__file__).resolve().parent

app = FastAPI(
    title="TripMate AI",
    description="LangGraph Multi-Agent Travel Planner with FastAPI Frontend",
    version="1.0.0",
)

# Serve everything in static/ (CSS, JS) under the /static/ URL prefix.
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")

# Jinja2Templates lets us render templates/index.html as an HTML response
# (even though this project only has one template right now).
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))


class TravelRequest(BaseModel):
    """
    Expected JSON body for POST /api/travel.

    Pydantic validates incoming requests against this shape automatically —
    if the frontend sent a request without a "message" field, FastAPI would
    reject it with a 422 error before our code even runs.

    Attributes:
        message: The traveler's free-text request, e.g.
            "Plan a 7 day Japan trip from Taiwan under NT$60,000."
        thread_id: Optional conversation id returned by a previous call.
            Sending it back lets the agent pipeline resume the same
            conversation instead of starting fresh (see
            agent/graph.py::run_travel_agent).
    """

    message: str
    thread_id: str | None = None


@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    """Render the single-page frontend."""
    return templates.TemplateResponse(request=request, name="index.html", context={})


@app.post("/api/travel")
async def travel_planner(request_data: TravelRequest):
    """
    Run the full multi-agent travel-planning pipeline for one message.

    This is the only endpoint that does real work: it hands the traveler's
    message to ``run_travel_agent`` (agent/graph.py) and returns the final
    answer plus the intermediate results from each step.

    Returns:
        200 with the plan on success.
        400 if the message was empty (nothing for the agents to work with).
        500 if the pipeline raised one of the expected error types (a
        missing API key, bad input, etc.) — we return the error message so
        the frontend can show it, and we also log the full traceback on the
        server side for debugging.
    """
    try:
        user_message = request_data.message.strip()

        if not user_message:
            return JSONResponse(
                status_code=400,
                content={"success": False, "error": "Message cannot be empty."},
            )

        result = run_travel_agent(
            user_input=user_message, thread_id=request_data.thread_id
        )

        return JSONResponse(
            content={
                "success": True,
                "thread_id": result["thread_id"],
                "answer": result["answer"],
                "flight_results": result["flight_results"],
                "hotel_results": result["hotel_results"],
                "itinerary": result["itinerary"],
                "llm_calls": result["llm_calls"],
            }
        )

    except (KeyError, RuntimeError, TypeError, ValueError) as e:
        # Only catching these specific exception types (rather than a bare
        # `except Exception`) is a deliberate choice: it lets truly
        # unexpected errors (e.g. a bug that raises something else) still
        # crash loudly during development instead of being silently
        # swallowed into a generic 500. If this endpoint ever raises an
        # exception type not listed here, that is worth investigating
        # rather than just adding it to the list.
        print("ERROR:", e)
        traceback.print_exc()

        return JSONResponse(
            status_code=500, content={"success": False, "error": str(e)}
        )


@app.get("/health")
async def health_check():
    """Basic liveness check for uptime monitoring / load balancers."""
    return {"status": "ok", "message": "AI Travel Planner API is running"}


@app.get("/favicon.ico")
async def favicon():
    """
    Return an empty response for favicon requests.

    Browsers automatically request /favicon.ico on every page load. Without
    this route, that request would 404 and clutter the server logs; we
    don't have a real favicon yet, so we just acknowledge the request.
    """
    return JSONResponse(content={})


if __name__ == "__main__":
    # Lets the app be started directly with `python app.py` in addition to
    # `uvicorn app:app`. reload=True auto-restarts the server on code
    # changes, which is convenient in development but should be turned off
    # (or run behind a production ASGI setup) before deploying.
    uvicorn.run("app:app", host="127.0.0.1", port=8000, reload=True)
