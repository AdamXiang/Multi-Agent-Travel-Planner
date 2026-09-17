"""
scripts/manual_smoke_test.py
==============================

A quick, manual sanity check for the Tavily hotel-search tool
(tools/tavily_tool.py) — run it by hand after changing that file, or after
rotating your TAVILY_API_KEY, to confirm the API call still works.

This used to live at the project root as ``test.py``. It has been moved
here and renamed because it is NOT an automated test: it has no
assertions, isn't discovered by pytest, and just prints whatever the API
returns for you to eyeball. Calling it "test.py" was misleading — a real
test suite would live in a ``tests/`` folder and use ``assert`` statements
(or a framework like pytest) to pass/fail automatically. If this project
adds real automated tests later, that's the pattern to reach for; this
script is only meant for a quick manual check while developing.

Run it with (from the project root):
    uv run python scripts/manual_smoke_test.py
"""

import sys
from pathlib import Path

# Running a script that lives in a subfolder (scripts/) means Python's
# default import path only includes that subfolder, not the project root —
# so "from tools.tavily_tool import ..." below would fail with
# ModuleNotFoundError without this line. Inserting the project root
# (one directory up from this file) at the front of sys.path fixes that,
# regardless of which directory you happen to run this script from.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tools.tavily_tool import tavily_search  # noqa: E402 (must come after the sys.path fix above)

res = tavily_search("Best top 3 hotels in Taiwan Taipei")
print(res)
