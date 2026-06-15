"""
Tests for the agent.py planning loop (Step H).

The loop drives deterministic tools (search_listings, outfit_preference_tool)
against the real dataset and two LLM tools (suggest_outfit, create_fit_card)
through the tools._chat seam. We monkeypatch _chat so the loop is exercised
end-to-end without burning Groq API calls (BUILD_LOG N3), and we cover the
parsing, the happy path (tools fire in order, state carries through), and the
two early-stop branches (empty query, no results).
"""

import tools
from agent import _parse_query, run_agent
from utils.data_loader import get_empty_wardrobe, get_example_wardrobe

WALKTHROUGH = (
    "I'm looking for a vintage graphic tee under $30. "
    "I mostly wear baggy jeans and chunky sneakers. "
    "What's out there and how would I style it?"
)


def _capture_chat(monkeypatch):
    """Patch tools._chat to record every prompt and return canned replies."""
    calls = []

    def fake_chat(messages, **kwargs):
        calls.append(messages[-1]["content"])
        return "Outfit: the tee with your baggy jeans and chunky sneakers."

    monkeypatch.setattr(tools, "_chat", fake_chat)
    return calls


# ── parsing ─────────────────────────────────────────────────────────────────

def test_parse_walkthrough_query():
    """The canonical query yields price + preference, and the preference clause
    is kept OUT of the search description so it can't skew the listing search."""
    parsed = _parse_query(WALKTHROUGH)
    assert parsed["max_price"] == 30.0
    assert parsed["preference_indicator"] is True
    assert "baggy" in parsed["clothing_preference"].lower()
    desc = parsed["description"].lower()
    assert "tee" in desc
    assert "jeans" not in desc and "sneakers" not in desc
    assert "$30" not in desc and "30" not in desc


def test_parse_extracts_size_after_size_keyword():
    """'size M' is recognized; a bare price still parses alongside it."""
    parsed = _parse_query("graphic tee size M under $25")
    assert parsed["size"].lower() == "m"
    assert parsed["max_price"] == 25.0
    assert parsed["preference_indicator"] is False
    assert parsed["clothing_preference"] is None


def test_parse_query_with_no_filters():
    """A plain query has no size/price and records no preference."""
    parsed = _parse_query("denim jacket")
    assert parsed["size"] is None
    assert parsed["max_price"] is None
    assert parsed["preference_indicator"] is False
    assert "jacket" in parsed["description"].lower()


# ── happy path ────────────────────────────────────────────────────────────────

def test_happy_path_fires_tools_and_threads_state(monkeypatch):
    """Full walkthrough: search hits, outfit + fit card produced, no error, and
    state flows through — preference into suggest_outfit, outfit into fit card."""
    calls = _capture_chat(monkeypatch)
    session = run_agent(WALKTHROUGH, get_example_wardrobe())

    assert session["error"] is None
    assert session["selected_item"] is not None
    blob = (
        session["selected_item"]["title"]
        + " "
        + " ".join(session["selected_item"]["style_tags"])
    ).lower()
    assert "tee" in blob or "graphic" in blob
    assert session["outfit_suggestion"].strip()
    assert session["fit_card"].strip()

    # Exactly the two LLM tools ran (suggest_outfit, then create_fit_card).
    assert len(calls) == 2
    # Preference threaded into the styling prompt.
    assert "baggy" in calls[0].lower()
    # The outfit suggestion threaded into the fit-card prompt.
    assert "baggy jeans and chunky sneakers" in calls[1].lower()


def test_preference_recorded_in_session(monkeypatch):
    """The detected preference is stored in session state via Tool 4."""
    _capture_chat(monkeypatch)
    session = run_agent(WALKTHROUGH, get_example_wardrobe())
    assert session["preference_indicator"] is True
    assert "baggy" in session["clothing_preference"].lower()


def test_empty_wardrobe_continues_to_fit_card(monkeypatch):
    """An empty wardrobe is not an error: suggest_outfit gives general advice
    and the loop still produces a fit card."""
    calls = _capture_chat(monkeypatch)
    session = run_agent("vintage graphic tee under $30", get_empty_wardrobe())
    assert session["error"] is None
    assert session["outfit_suggestion"].strip()
    assert session["fit_card"].strip()
    assert "general" in calls[0].lower()  # empty-wardrobe styling branch


# ── early-stop branches ─────────────────────────────────────────────────────

def test_no_results_stops_before_llm_tools(monkeypatch):
    """No matching listing → error set, downstream None, and no LLM call."""

    def boom(*args, **kwargs):
        raise AssertionError("LLM tools must not run when search is empty")

    monkeypatch.setattr(tools, "_chat", boom)
    session = run_agent("designer ballgown size XXXL under $5", get_example_wardrobe())
    assert session["error"]
    assert session["search_results"] == []
    assert session["selected_item"] is None
    assert session["outfit_suggestion"] is None
    assert session["fit_card"] is None


def test_blank_query_returns_friendly_error(monkeypatch):
    """An empty/whitespace query stops immediately without touching the LLM."""

    def boom(*args, **kwargs):
        raise AssertionError("LLM tools must not run for a blank query")

    monkeypatch.setattr(tools, "_chat", boom)
    for blank in ("", "   ", None):
        session = run_agent(blank, get_example_wardrobe())
        assert session["error"]
        assert session["selected_item"] is None
