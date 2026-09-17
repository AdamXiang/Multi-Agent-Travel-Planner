# syntax=docker/dockerfile:1
#
# Dockerfile
# ===========
# Multi-stage build for TripMate AI (FastAPI + LangGraph), using uv to
# install dependencies.
#
# Why two stages ("builder" and the final stage)?
# -------------------------------------------------
# The "builder" stage installs build tools (a C compiler, etc.) and uses uv
# to resolve and install every dependency into a virtual environment. Those
# build tools take up a lot of space and are only needed while installing
# packages — never once the packages are actually installed. The final
# stage starts fresh from a clean, small python:3.12-slim image and copies
# over ONLY the finished virtual environment and application code, so
# build tools never end up in the image you actually deploy. This keeps
# the final image smaller and reduces its attack surface (fewer tools
# available if the container is ever compromised).
#
# Build:  docker build -t tripmate-ai .
# Run:    docker run --rm -p 8000:8000 --env-file .env tripmate-ai
#         (--env-file injects your secrets at runtime; .env itself is
#         never copied into the image — see .dockerignore)


# ============================================================
# Stage 1: builder — installs dependencies with uv
# ============================================================
FROM python:3.12-slim AS builder

# Copy the uv/uvx binaries from Astral's own image instead of installing uv
# with pip. Pinned to an exact version (not ":latest") so the build is
# reproducible — an unpinned build tool could silently behave differently
# on a later build. 0.12.15 satisfies this project's
# `uv_build>=0.12.12,<0.13.0` constraint in pyproject.toml.
COPY --from=ghcr.io/astral-sh/uv:0.12.15 /uv /uvx /bin/

WORKDIR /app

# Environment variables for Python + uv:
# - PYTHONDONTWRITEBYTECODE: don't write .pyc files while the app itself
#   runs later — there's no benefit to caching bytecode in a container
#   that gets rebuilt from scratch on every deploy.
# - PYTHONUNBUFFERED: flush stdout/stderr immediately instead of
#   buffering, so `docker logs` shows output in real time.
# - UV_COMPILE_BYTECODE: the opposite of PYTHONDONTWRITEBYTECODE, but for
#   uv's OWN install step below — pre-compiling .pyc files once here, at
#   build time, makes the app's first startup slightly faster.
# - UV_LINK_MODE=copy: uv normally hard-links packages from its cache to
#   save disk space, but that only works within one filesystem. Docker
#   build layers are separate filesystems, so linking would just warn and
#   fall back anyway; copy mode does that up front, cleanly.
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy

# build-essential provides a C compiler, needed only if uv has to build a
# dependency from source instead of using a pre-built wheel. None of this
# project's current dependencies require it (psycopg is installed via its
# [binary] extra), but it's kept as a safety net for future dependencies —
# and since this is the "builder" stage, it never bloats the final image
# either way.
#
# Note: the original draft of this Dockerfile also installed `git` and
# `curl`. Neither is actually needed: nothing in pyproject.toml/uv.lock is
# fetched via git, and nothing at build time calls curl (the container
# HEALTHCHECK below uses Python instead, specifically to avoid needing
# curl in the final image). Dropping both keeps the image smaller.
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copy ONLY the dependency manifests first (not the rest of the source
# code yet). Docker caches each layer, so as long as pyproject.toml/
# uv.lock don't change, this (slow) dependency-install step is skipped on
# your next build even if you only edited app.py.
COPY pyproject.toml uv.lock ./

# Install dependencies only (--no-install-project skips installing this
# project itself, since the source code hasn't been copied in yet).
# --frozen refuses to update uv.lock even if pyproject.toml looks newer,
# guaranteeing the exact versions your lockfile pins are what gets built —
# not "whatever the resolver would pick today."
RUN uv sync --frozen --no-install-project --no-dev

# Now copy the actual source code.
COPY . .

# Install the project itself into the same virtual environment. This step
# is fast, since all the heavy dependencies were already installed above.
RUN uv sync --frozen --no-dev


# ============================================================
# Stage 2: final — a clean, small runtime image
# ============================================================
FROM python:3.12-slim

WORKDIR /app

# Copy only the finished virtual environment + application code from the
# builder stage — not apt packages, not uv itself, not any build cache.
# (This app also never needs a system CA bundle: tools/flight_tool.py and
# agent/config.py already point OpenSSL/requests at the certifi package's
# own bundled certificates, so we don't need to apt-get install
# ca-certificates here either.)
COPY --from=builder /app /app

# Put the virtual environment's bin/ directory first on PATH, so plain
# `uvicorn ...` (in CMD below) resolves to /app/.venv/bin/uvicorn instead
# of needing an activated venv.
ENV PATH="/app/.venv/bin:$PATH"

# Run as a non-root user. A container runs as root by default, which is
# more privilege than this app ever needs — if something inside the
# container were ever compromised, a non-root user limits what it could
# do to the rest of the container.
RUN useradd --create-home --uid 1000 appuser \
    && chown -R appuser:appuser /app
USER appuser

EXPOSE 8000

# Let Docker (and orchestrators like Kubernetes/ECS) know whether the app
# is actually healthy, using the /health route already defined in app.py.
# Uses Python instead of curl/wget specifically so the final image doesn't
# need either of those installed just for this check.
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=2)" || exit 1

CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]
