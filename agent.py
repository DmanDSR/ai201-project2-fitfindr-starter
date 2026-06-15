"""
agent.py

The FitFindr planning loop. Orchestrates the four tools in response to a
natural language user query, passing state between them via a session dict.

The loop is deterministic: it parses the query with regex/string rules (no
network), records any style preference, searches the listings, and only then
calls the two LLM tools (suggest_outfit, create_fit_card). It stops early and
cleanly when a required input is missing (empty query, no matching listings).

Usage:
    from agent import run_agent
    from utils.data_loader import get_example_wardrobe

    result = run_agent(
        query="vintage graphic tee under $30, size M",
        wardrobe=get_example_wardrobe(),
    )
    print(result["fit_card"])
    print(result["error"])   # None on success
"""

import re

from tools import (
    create_fit_card,
    outfit_preference_tool,
    search_listings,
    suggest_outfit,
)

# ── query parsing (deterministic, no network) ──────────────────────────────────

# Recognized size tokens. Single letters (s/m/l) are only honored when they
# follow the word "size" (see _SIZE_RE), so plain prose doesn't trip them.
_SIZE_WORDS = {
    "xs", "s", "m", "l", "xl", "xxl", "xxxl",
    "small", "medium", "large",
    "x-large", "xx-large",
}

# "under $30", "below 25", "less than $40", "up to 50" → the numeric ceiling.
_PRICE_RE = re.compile(
    r"(?:under|below|less than|cheaper than|max|up to|at most|around|about|<=?)"
    r"\s*\$?\s*(\d+(?:\.\d{1,2})?)",
    re.I,
)
# Bare "$30" anywhere, as a fallback when no qualifier word is present.
_PRICE_DOLLAR_RE = re.compile(r"\$\s*(\d+(?:\.\d{1,2})?)")

# "size M", "size is M/L", "sized XL".
_SIZE_RE = re.compile(
    r"\bsize[ds]?\s+(?:is\s+)?([a-z0-9](?:[a-z0-9/\-]*[a-z0-9])?)",
    re.I,
)

# Style-preference cues. Each captures the text after the cue as the preference.
# The cues are deliberately about how the user *dresses* ("I wear", "my style
# is") so an item request ("I'm looking for a tee") is not misread as a
# preference. The capture runs to the end of its sentence (see _parse_query),
# so preference clauses are expected in their own sentence — that keeps the
# wardrobe/style words ("baggy jeans") out of the listing search.
_PREF_PATTERNS = [
    re.compile(
        r"\bi\s*(?:'?m)?\s+(?:mostly|usually|normally|typically|generally|often|"
        r"really)?\s*wear(?:ing)?\s+(.+)",
        re.I,
    ),
    re.compile(
        r"\bi\s+(?:like|love|prefer)\s+(?:to\s+)?(?:wear|dress|rock|style)\b\s*"
        r"(?:in\s+)?(.+)",
        re.I,
    ),
    re.compile(r"\bi'?m\s+into\s+(.+)", re.I),
    re.compile(r"\bmy\s+style\s+is\s+(.+)", re.I),
    re.compile(r"\bi\s+dress\s+(.+)", re.I),
]


def _parse_query(query: str) -> dict:
    """
    Extract structured search/preference parameters from a free-text query.

    Returns a dict with:
        description (str)            — keywords for search_listings (preference,
                                       price, and size phrases stripped out)
        size (str | None)           — recognized size token, or None
        max_price (float | None)    — price ceiling, or None
        preference_indicator (bool) — True if a style preference was detected
        clothing_preference (str|None) — the lifted preference text, or None

    This is pure string work (no network) so the loop stays cheap and unit
    testable, per the build plan's parsing choice.
    """
    text = query or ""
    description = text

    # --- preference: lift the text after the first style cue, drop that span
    #     from the search description so it can't pollute keyword matching. ---
    preference = None
    for sentence in re.split(r"(?<=[.!?])\s+", text):
        for pat in _PREF_PATTERNS:
            match = pat.search(sentence)
            if match:
                preference = match.group(1).strip(" .!?,")
                description = description.replace(match.group(0), " ")
                break
        if preference:
            break

    # --- price ceiling ---
    max_price = None
    price_match = _PRICE_RE.search(description) or _PRICE_DOLLAR_RE.search(description)
    if price_match:
        max_price = float(price_match.group(1))
        description = description.replace(price_match.group(0), " ")

    # --- size ---
    size = None
    size_match = _SIZE_RE.search(description)
    if size_match:
        candidate = size_match.group(1)
        if (
            candidate.lower() in _SIZE_WORDS
            or "/" in candidate
            or "-" in candidate
            or candidate.isupper()
        ):
            size = candidate
            description = description.replace(size_match.group(0), " ")

    description = " ".join(description.split())

    return {
        "description": description,
        "size": size,
        "max_price": max_price,
        "preference_indicator": preference is not None,
        "clothing_preference": preference,
    }


# ── session state ─────────────────────────────────────────────────────────────

def _new_session(query: str, wardrobe: dict) -> dict:
    """
    Initialize and return a fresh session dict for one user interaction.

    The session dict is the single source of truth for everything that happens
    during a run — it stores the original query, parsed parameters, recorded
    preference, tool results, and any error that caused early termination.
    """
    return {
        "query": query,                # original user query
        "parsed": {},                  # extracted description / size / max_price
        "preference_indicator": False, # did the user express a style preference?
        "clothing_preference": None,   # recorded preference text (or None)
        "preference_message": None,    # user-facing note from outfit_preference_tool
        "search_results": [],          # list of matching listing dicts
        "selected_item": None,         # top result, passed into suggest_outfit
        "wardrobe": wardrobe,          # user's wardrobe dict
        "outfit_suggestion": None,     # string returned by suggest_outfit
        "fit_card": None,              # string returned by create_fit_card
        "error": None,                 # set if the interaction ended early
    }


# ── planning loop ─────────────────────────────────────────────────────────────

def run_agent(query: str, wardrobe: dict) -> dict:
    """
    Main agent entry point. Runs the FitFindr planning loop for a single
    user interaction and returns the completed session dict.

    Args:
        query:    Natural language user request
                  (e.g., "vintage graphic tee under $30, size M").
        wardrobe: User's wardrobe dict — use get_example_wardrobe() or
                  get_empty_wardrobe() from utils/data_loader.py.

    Returns:
        The session dict after the interaction completes. Check session["error"]
        first — if it is not None, the interaction ended early and the other
        output fields (outfit_suggestion, fit_card) will be None.

    Routing (matches the planning.md loop and error table):
        parse → (preference) → search → select → suggest_outfit → create_fit_card
        - empty/blank query        → friendly error, stop.
        - no matching listings     → "adjust your search" error, stop early
                                     (never call suggest_outfit on empty input).
        - empty wardrobe           → suggest_outfit returns general advice; this
                                     is NOT an error, so the loop continues.
        - missing preference text  → proceed without one (tool re-prompt is
                                     surfaced as session["preference_message"]).
    """
    session = _new_session(query, wardrobe)

    # Guard: nothing to plan around without a request.
    if not isinstance(query, str) or not query.strip():
        session["error"] = (
            "Tell me what you're looking for — e.g. 'vintage graphic tee under "
            "$30, size M' — and I'll find listings and style them."
        )
        return session

    # Step 1: parse the query into search params + any style preference.
    parsed = _parse_query(query)
    session["parsed"] = {
        "description": parsed["description"],
        "size": parsed["size"],
        "max_price": parsed["max_price"],
    }

    # Step 2: record the preference (Tool 4). Records only when non-blank;
    # otherwise the loop simply proceeds without one.
    pref = outfit_preference_tool(
        parsed["preference_indicator"], parsed["clothing_preference"]
    )
    session["preference_indicator"] = parsed["preference_indicator"]
    session["clothing_preference"] = pref["preference"]
    session["preference_message"] = pref["message"]

    # Step 3: search the listings. No matches → stop early with guidance.
    results = search_listings(
        parsed["description"], parsed["size"], parsed["max_price"]
    )
    session["search_results"] = results
    if not results:
        session["error"] = (
            "I couldn't find any listings matching that. Try loosening the "
            "filters — a higher price, a different size, or simpler keywords."
        )
        return session

    # Step 4: select the top-ranked listing to style.
    session["selected_item"] = results[0]

    # Step 5: suggest outfits. An empty wardrobe yields general advice (handled
    # inside the tool) rather than an error, so the loop keeps going.
    session["outfit_suggestion"] = suggest_outfit(
        results[0], wardrobe, session["clothing_preference"]
    )

    # Step 6: caption the outfit as a shareable fit card.
    session["fit_card"] = create_fit_card(session["outfit_suggestion"], results[0])

    # Step 7: done — request fully satisfied.
    return session


# ── CLI test ──────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    from utils.data_loader import get_example_wardrobe

    print("=== Happy path: graphic tee ===\n")
    session = run_agent(
        query=(
            "I'm looking for a vintage graphic tee under $30. "
            "I mostly wear baggy jeans and chunky sneakers. "
            "What's out there and how would I style it?"
        ),
        wardrobe=get_example_wardrobe(),
    )
    if session["error"]:
        print(f"Error: {session['error']}")
    else:
        print(f"Parsed: {session['parsed']}")
        print(f"Preference: {session['clothing_preference']}")
        print(f"Found: {session['selected_item']['title']}")
        print(f"\nOutfit: {session['outfit_suggestion']}")
        print(f"\nFit card: {session['fit_card']}")

    print("\n\n=== No-results path ===\n")
    session2 = run_agent(
        query="designer ballgown size XXXL under $5",
        wardrobe=get_example_wardrobe(),
    )
    print(f"Error message: {session2['error']}")
