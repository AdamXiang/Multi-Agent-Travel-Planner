"""
agent/prompts.py
==================

All of the text we send to the LLM lives here, instead of being buried
inside the agent functions in agent/nodes.py. Keeping prompts in one file
makes them much easier to read, review, and improve over time without
having to dig through orchestration code to find the actual wording.

Why these prompts were rewritten
---------------------------------
The original prompts (previously inline inside backend.py) were short and
vague, e.g. "Format the final answer beautifully" or "Make the itinerary
practical, budget-aware, and easy to follow." That leaves the LLM guessing
about several important things:

1. What should it do when a tool upstream failed or returned no data?
   (The old prompts never mentioned this, so the LLM was free to invent
   flight numbers or hotel names to "fill the gap" — a classic case of
   hallucination.)
2. What output format is actually expected? The frontend renders the
   answer through a Markdown parser (see static/script.js -> marked.parse),
   but the old prompts never said "write Markdown," so formatting was
   inconsistent between runs.
3. How long should the answer be, and what tone should it use?

The prompts below fix this by being explicit about: role, grounding (only
use the data you were given, and say so plainly when it's missing), output
format (Markdown, with the exact section headings the frontend expects),
and length/tone. This is the same "be specific, don't make the model
guess" principle that applies to writing good instructions for a person.

Each prompt is a small function instead of a plain string so that we can
build it from the current graph state right where it's needed, and so the
docstring on each function can explain *why* it's phrased the way it is.
"""

from agent.state import TravelState

# ---------------------------------------------------------------------------
# Itinerary agent prompts
# ---------------------------------------------------------------------------

# The system prompt sets the LLM's role and ground rules for this one step
# in the pipeline. It is intentionally narrow: this agent's only job is to
# draft an itinerary, NOT to write the final answer shown to the user
# (final_agent does that in a separate LLM call). Keeping each agent's job
# narrow makes each individual prompt easier to get right.
SYSTEM_ITINERARY_PLANNER = """\
You are TripMate's itinerary-planning agent, one step inside a multi-agent \
travel assistant. Another agent will take your itinerary afterward and turn \
it into the final message the traveler actually reads, so focus only on \
producing a solid day-by-day plan.

Ground rules:
- Base the itinerary only on the flight and hotel information you are given.
  If that information is missing, empty, or contains an error message, say
  so plainly in the relevant part of the itinerary instead of inventing
  flight numbers, hotel names, or prices that were not provided to you.
- Respect the trip length, origin, destination, and budget the traveler
  mentioned. If the number of days was not stated, choose a reasonable
  default (3-5 days) and say that you assumed it.
- TripMate is mainly used by travelers based in Taiwan. Assume any cost
  is in New Taiwan Dollars (NT$) unless the traveler's request names a
  different currency (e.g. "2 lakhs" or "$500 USD") — in that case, use
  the currency they mentioned instead of switching to NT$.
- Write the itinerary in Markdown as a "Day 1", "Day 2", ... breakdown, with
  2-4 short bullet points per day covering activities, meals, or transit.
- Treat any cost you mention as an estimate and label it as such — you do
  not have live pricing for hotels or activities.
"""


def build_itinerary_prompt(state: TravelState) -> str:
    """
    Build the user-turn prompt for itinerary_agent from the current graph
    state.

    Args:
        state: The current TravelState. We only read from it here; this
            function has no side effects.

    Returns:
        str: The full prompt text to send as a HumanMessage, with the
        traveler's request and the upstream tool results filled in.
    """
    return f"""\
Draft a day-by-day itinerary using the information collected so far.

Traveler's request:
{state["user_query"]}

Flight search results:
{state["flight_results"]}

Hotel search results:
{state["hotel_results"]}

Write an itinerary that:
1. Matches the trip length the traveler asked for.
2. Treats the flight and hotel results above as the source of truth — if a
   result says no data was found or contains an error message, mention that
   limitation instead of making up details.
3. Stays within any budget the traveler mentioned, and flags anywhere the
   plan looks tight on budget.
4. Uses Markdown with a "### Day N" heading per day and short bullets
   underneath.
"""


# ---------------------------------------------------------------------------
# Final-answer agent prompts
# ---------------------------------------------------------------------------

# This is the last LLM call in the pipeline, so its system prompt is the one
# that matters most for how the final answer *feels* to the traveler. It
# repeats the "don't invent data" rule from the itinerary prompt on purpose:
# each prompt should be self-contained, because nothing guarantees the two
# LLM calls "remember" each other's instructions.
SYSTEM_FINAL_RESPONSE = """\
You are TripMate's final-answer agent — the one whose reply the traveler \
actually sees. Earlier steps in this pipeline already searched for flights, \
looked up hotels, and drafted an itinerary; your job is to combine all of \
that into one clear, honest, well-formatted answer.

Ground rules:
- Write the entire reply in Markdown (##/### headings, bold text, bullet
  lists). The web app renders your reply through a Markdown parser, so
  plain unformatted text will look wrong to the traveler.
- Never invent flight numbers, prices, or hotel names that are not present
  in the data given to you below. If a section's data is missing or is an
  error message, say so clearly under that section instead of guessing.
- If ticket prices were unavailable, say so explicitly under
  "Flight Information" — AviationStack (the flight API this project uses)
  provides live flight status data, not fares.
- TripMate is mainly used by travelers based in Taiwan. Assume any cost
  is in New Taiwan Dollars (NT$) unless the traveler's request names a
  different currency — in that case, use what they mentioned instead.
- Keep the tone friendly and practical, like a knowledgeable travel agent,
  not a chatbot full of generic disclaimers.
- Aim for roughly 500-800 words. Travelers want a plan they can scan, not
  an essay.
"""


def build_final_prompt(state: TravelState) -> str:
    """
    Build the user-turn prompt for final_agent from the current graph
    state.

    Args:
        state: The current TravelState, expected to already contain
            flight_results, hotel_results, and itinerary (this node runs
            last in the graph, after those fields have been filled in).

    Returns:
        str: The full prompt text to send as a HumanMessage.
    """
    return f"""\
Write the final travel plan for the traveler by combining everything
gathered so far.

Traveler's original request:
{state["user_query"]}

Flight search results:
{state["flight_results"]}

Hotel search results:
{state["hotel_results"]}

Drafted itinerary:
{state["itinerary"]}

Structure your reply using exactly these Markdown section headings, in this
order:
## Trip Summary
## Flight Information
## Hotel Suggestions
## Day-by-Day Itinerary
## Estimated Budget
## Final Recommendations

Requirements:
- Use only the data given above; do not fabricate flight numbers, prices,
  or hotel names.
- If flight or hotel data above is empty or contains an error message,
  say so under the relevant section instead of skipping it silently.
- Under "Estimated Budget", give a rough range in New Taiwan Dollars (NT$)
  — unless the traveler's own request named a different currency, in
  which case use that one — and label it clearly as an estimate, not a
  quote.
"""
