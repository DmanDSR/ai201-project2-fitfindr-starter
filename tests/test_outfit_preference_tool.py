"""Tests for Tool 4: outfit_preference_tool (deterministic — no network)."""

from tools import outfit_preference_tool


def test_yes_with_text_is_recorded():
    """Saying yes with a real preference stores the cleaned text."""
    result = outfit_preference_tool(True, "baggy jeans")
    assert result["recorded"] is True
    assert result["preference"] == "baggy jeans"
    assert "baggy jeans" in result["message"]


def test_yes_strips_surrounding_whitespace():
    """A padded preference is trimmed before being stored."""
    result = outfit_preference_tool(True, "   earth tones  ")
    assert result["recorded"] is True
    assert result["preference"] == "earth tones"


def test_no_leaves_preference_blank():
    """Saying no records nothing and acknowledges the choice."""
    result = outfit_preference_tool(False)
    assert result["recorded"] is False
    assert result["preference"] is None
    assert result["message"]


def test_yes_but_blank_reprompts():
    """Yes with empty/whitespace text is not recorded and re-prompts."""
    result = outfit_preference_tool(True, "   ")
    assert result["recorded"] is False
    assert result["preference"] is None
    assert "no" in result["message"].lower()


def test_yes_but_none_reprompts():
    """Yes with a None preference must not raise and re-prompts."""
    result = outfit_preference_tool(True, None)
    assert result["recorded"] is False
    assert result["preference"] is None


def test_no_with_stray_text_still_not_recorded():
    """preference_indicator=False wins even if text was passed."""
    result = outfit_preference_tool(False, "baggy")
    assert result["recorded"] is False
    assert result["preference"] is None
