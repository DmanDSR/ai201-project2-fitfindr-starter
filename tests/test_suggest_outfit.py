"""
Tests for Tool 2: suggest_outfit (LLM tool — contract-tested, no network).

The single network seam is tools._chat. We monkeypatch it to capture the
messages the tool builds and to return a canned reply, so these tests verify
the prompt contract and branch behavior (full / empty / preference / guard)
without burning Groq API calls (BUILD_LOG N3).
"""

import tools
from tools import suggest_outfit
from utils.data_loader import get_empty_wardrobe, get_example_wardrobe

TEE = {
    "id": "L_001",
    "title": "Vintage graphic tee",
    "category": "tops",
    "style_tags": ["vintage", "graphic", "streetwear"],
    "colors": ["black", "white"],
    "description": "Faded band tee, soft cotton.",
    "price": 24.0,
}


def _capture(monkeypatch):
    """Patch tools._chat to record its messages and return a fixed reply."""
    captured = {}

    def fake_chat(messages, **kwargs):
        captured["messages"] = messages
        captured["kwargs"] = kwargs
        return "Outfit 1: the tee with your jeans."

    monkeypatch.setattr(tools, "_chat", fake_chat)
    return captured


def _user_text(captured) -> str:
    return captured["messages"][-1]["content"]


def test_full_wardrobe_returns_text_and_uses_wardrobe(monkeypatch):
    """A populated wardrobe yields a non-empty suggestion built from named pieces."""
    captured = _capture(monkeypatch)
    out = suggest_outfit(TEE, get_example_wardrobe())
    assert isinstance(out, str) and out.strip()
    user = _user_text(captured)
    # The new item and at least one real wardrobe piece reach the prompt.
    assert "Vintage graphic tee" in user
    assert "Baggy straight-leg jeans, dark wash" in user


def test_empty_wardrobe_gives_general_advice_not_error(monkeypatch):
    """Empty wardrobe → general styling advice branch, never an exception/blank."""
    captured = _capture(monkeypatch)
    out = suggest_outfit(TEE, get_empty_wardrobe())
    assert isinstance(out, str) and out.strip()
    user = _user_text(captured).lower()
    assert "general" in user
    assert "empty" in user


def test_preference_is_woven_into_prompt(monkeypatch):
    """A recorded clothing preference must appear in the styling prompt."""
    captured = _capture(monkeypatch)
    suggest_outfit(TEE, get_example_wardrobe(), clothing_preference="baggy, earth tones")
    assert "baggy, earth tones" in _user_text(captured)


def test_no_preference_is_stated_explicitly(monkeypatch):
    """Without a preference the prompt says so rather than inventing one."""
    captured = _capture(monkeypatch)
    suggest_outfit(TEE, get_example_wardrobe())
    assert "no specific style preference" in _user_text(captured).lower()


def test_bad_item_is_guarded_without_network(monkeypatch):
    """An empty/invalid item returns a guidance message and never calls the LLM."""

    def boom(*args, **kwargs):
        raise AssertionError("_chat must not be called for a bad item")

    monkeypatch.setattr(tools, "_chat", boom)
    assert "search for a listing" in suggest_outfit({}, get_example_wardrobe()).lower()


def test_llm_failure_returns_message_not_exception(monkeypatch):
    """If the LLM call raises, the tool returns a friendly string (N4)."""

    def boom(*args, **kwargs):
        raise RuntimeError("network down")

    monkeypatch.setattr(tools, "_chat", boom)
    out = suggest_outfit(TEE, get_example_wardrobe())
    assert isinstance(out, str)
    assert "couldn't" in out.lower()


def test_missing_slot_is_visible_in_wardrobe_block(monkeypatch):
    """A wardrobe with no shoes should not list a shoes line, so the LLM is
    told (by omission) the slot is empty; tops it does have is present."""
    captured = _capture(monkeypatch)
    no_shoes = {"items": [
        {"name": "White tee", "category": "tops", "colors": ["white"]},
        {"name": "Blue jeans", "category": "bottoms", "colors": ["blue"]},
    ]}
    suggest_outfit(TEE, no_shoes)
    user = _user_text(captured)
    assert "tops:" in user and "bottoms:" in user
    assert "shoes:" not in user
