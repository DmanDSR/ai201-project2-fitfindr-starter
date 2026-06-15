"""
Tests for the Gradio handler (Step I).

handle_query maps a run_agent() session onto the three UI panels. We stub
app.run_agent so these tests cover the handler's wiring (wardrobe choice,
empty-query guard, error routing, listing formatting) in isolation — the loop
itself is already covered by test_agent.py, and Gradio is never launched.
"""

import app
from app import _format_listing, handle_query

LISTING = {
    "title": "Y2K Baby Tee",
    "price": 18.0,
    "size": "S/M",
    "condition": "excellent",
    "brand": "Unbranded",
    "platform": "depop",
    "style_tags": ["y2k", "graphic"],
    "colors": ["white", "pink"],
    "description": "Soft cotton baby tee with a butterfly print.",
}


def _stub_agent(monkeypatch, session):
    """Patch app.run_agent to return a canned session and record its args."""
    seen = {}

    def fake_run_agent(query, wardrobe):
        seen["query"] = query
        seen["wardrobe"] = wardrobe
        return session

    monkeypatch.setattr(app, "run_agent", fake_run_agent)
    return seen


# ── happy path ────────────────────────────────────────────────────────────────

def test_success_fills_three_panels(monkeypatch):
    """A successful session populates all three panels with its fields."""
    _stub_agent(monkeypatch, {
        "error": None,
        "selected_item": LISTING,
        "outfit_suggestion": "Tee + baggy jeans + chunky sneakers.",
        "fit_card": "Thrifted heaven on depop.",
    })
    listing, outfit, fitcard = handle_query("graphic tee", "Example wardrobe")
    assert "Y2K Baby Tee" in listing and "$18.00" in listing
    assert outfit == "Tee + baggy jeans + chunky sneakers."
    assert fitcard == "Thrifted heaven on depop."


def test_empty_wardrobe_choice_selects_empty_wardrobe(monkeypatch):
    """The 'Empty wardrobe' radio routes get_empty_wardrobe() into the loop."""
    seen = _stub_agent(monkeypatch, {
        "error": None,
        "selected_item": LISTING,
        "outfit_suggestion": "General advice.",
        "fit_card": "Caption.",
    })
    handle_query("graphic tee", "Empty wardrobe (new user)")
    assert seen["wardrobe"]["items"] == []


def test_default_choice_selects_example_wardrobe(monkeypatch):
    """Any non-empty choice uses the populated example wardrobe."""
    seen = _stub_agent(monkeypatch, {
        "error": None, "selected_item": LISTING,
        "outfit_suggestion": "x", "fit_card": "y",
    })
    handle_query("graphic tee", "Example wardrobe")
    assert len(seen["wardrobe"]["items"]) > 0


# ── guards & error routing ──────────────────────────────────────────────────

def test_empty_query_short_circuits_without_calling_agent(monkeypatch):
    """A blank query returns guidance and never reaches run_agent."""

    def boom(*args, **kwargs):
        raise AssertionError("run_agent must not run for a blank query")

    monkeypatch.setattr(app, "run_agent", boom)
    for blank in ("", "   ", None):
        listing, outfit, fitcard = handle_query(blank, "Example wardrobe")
        assert listing and outfit == "" and fitcard == ""


def test_agent_error_routes_to_first_panel_only(monkeypatch):
    """A session error shows in the listing panel; the other two stay blank."""
    _stub_agent(monkeypatch, {
        "error": "I couldn't find any listings matching that.",
        "selected_item": None,
        "outfit_suggestion": None,
        "fit_card": None,
    })
    listing, outfit, fitcard = handle_query("ballgown size XXXL under $5", "Example wardrobe")
    assert listing == "I couldn't find any listings matching that."
    assert outfit == "" and fitcard == ""


# ── formatting ────────────────────────────────────────────────────────────────

def test_format_listing_includes_key_fields():
    """The listing formatter surfaces title, price, size, and platform."""
    text = _format_listing(LISTING)
    assert "Y2K Baby Tee" in text
    assert "$18.00" in text
    assert "size S/M" in text
    assert "depop" in text


def test_format_listing_handles_missing_price():
    """A listing with no price degrades gracefully instead of raising."""
    text = _format_listing({"title": "Mystery item"})
    assert "Mystery item" in text
    assert "price n/a" in text
