"""
Tests for Tool 3: create_fit_card (LLM tool — contract-tested, no network).

Like suggest_outfit, the only network seam is tools._chat. We monkeypatch it
to capture the prompt and return a canned caption, so we verify the contract
(item name/price/platform reach the prompt, higher temperature, guard + N4
failure behavior) without burning Groq API calls (BUILD_LOG N3).
"""

import tools
from tools import create_fit_card

TEE = {
    "id": "L_001",
    "title": "Vintage graphic tee",
    "price": 24.0,
    "platform": "depop",
}

OUTFIT = "The vintage tee with baggy jeans and chunky white sneakers."


def _capture(monkeypatch):
    captured = {}

    def fake_chat(messages, **kwargs):
        captured["messages"] = messages
        captured["kwargs"] = kwargs
        return "Thrifted heaven. This tee was begging to come home with me."

    monkeypatch.setattr(tools, "_chat", fake_chat)
    return captured


def _user_text(captured) -> str:
    return captured["messages"][-1]["content"]


def test_real_outfit_returns_caption(monkeypatch):
    """A real outfit produces a non-empty caption string."""
    _capture(monkeypatch)
    out = create_fit_card(OUTFIT, TEE)
    assert isinstance(out, str) and out.strip()


def test_prompt_includes_item_name_price_platform(monkeypatch):
    """Item name, formatted price, and platform must reach the prompt."""
    captured = _capture(monkeypatch)
    create_fit_card(OUTFIT, TEE)
    user = _user_text(captured)
    assert "Vintage graphic tee" in user
    assert "$24.00" in user
    assert "depop" in user


def test_outfit_text_reaches_prompt(monkeypatch):
    """The styled outfit itself is passed through to the caption prompt."""
    captured = _capture(monkeypatch)
    create_fit_card(OUTFIT, TEE)
    assert "chunky white sneakers" in _user_text(captured)


def test_higher_temperature_for_variety(monkeypatch):
    """Captions should run hotter than the styling tool for variety."""
    captured = _capture(monkeypatch)
    create_fit_card(OUTFIT, TEE)
    assert captured["kwargs"].get("temperature", 0) >= 0.8


def test_empty_outfit_is_guarded_without_network(monkeypatch):
    """Empty/whitespace outfit returns a guard message and never calls the LLM."""

    def boom(*args, **kwargs):
        raise AssertionError("_chat must not be called for an empty outfit")

    monkeypatch.setattr(tools, "_chat", boom)
    for bad in ("", "   ", None):
        out = create_fit_card(bad, TEE)
        assert isinstance(out, str)
        assert "outfit suggestion" in out.lower()


def test_llm_failure_returns_message_not_exception(monkeypatch):
    """If the LLM call raises, the tool returns a friendly string (N4)."""

    def boom(*args, **kwargs):
        raise RuntimeError("network down")

    monkeypatch.setattr(tools, "_chat", boom)
    out = create_fit_card(OUTFIT, TEE)
    assert isinstance(out, str)
    assert "couldn't" in out.lower()


def test_missing_price_falls_back_gracefully(monkeypatch):
    """A listing with no/garbage price must not break the prompt."""
    captured = _capture(monkeypatch)
    item = {"title": "Mystery jacket", "platform": "thredUp"}
    out = create_fit_card(OUTFIT, item)
    assert isinstance(out, str) and out.strip()
    assert "unlisted price" in _user_text(captured)
