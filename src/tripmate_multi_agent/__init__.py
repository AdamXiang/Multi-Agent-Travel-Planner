"""
src/tripmate_multi_agent/__init__.py
======================================

Status: currently unused by the running app.

This package was auto-generated when the project was first scaffolded with
``uv init``. The ``main()`` function below is what the
``tripmate-multi-agent`` console script (declared under
``[project.scripts]`` in pyproject.toml) points to.

However, the actual TripMate app does NOT start here — it runs via
``app.py`` (FastAPI + uvicorn) at the project root, which imports the agent
pipeline from the top-level ``agent/`` package, not from this ``src/``
package. In other words, this file and the ``agent/`` package are two
separate, unconnected pieces of code that both happen to live in this repo.

This is left as-is (rather than deleted or wired up) to keep this refactor
focused. A natural future improvement — once you're comfortable with
Python packaging — would be to move ``app.py``, ``agent/``, and ``tools/``
into this ``src/tripmate_multi_agent/`` package so the whole project has one
consistent, installable package layout instead of a mix of root-level
scripts and this mostly-empty stub.
"""


def main() -> None:
    print("Hello from tripmate-multi-agent!")
