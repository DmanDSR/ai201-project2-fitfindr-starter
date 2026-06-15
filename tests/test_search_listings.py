"""Tests for Tool 1: search_listings (deterministic — no network)."""

from tools import search_listings


def test_hit_returns_relevant_within_budget():
    """'graphic tee under $30' should return tops, all <= $30, tee on top."""
    results = search_listings("graphic tee", max_price=30.0)
    assert results, "expected at least one match"
    assert all(r["price"] <= 30.0 for r in results), "budget filter leaked"
    top = results[0]
    blob = (top["title"] + " " + " ".join(top["style_tags"])).lower()
    assert "tee" in blob or "graphic" in blob, "top result not tee-like"


def test_over_budget_returns_empty():
    """Cheapest graphic tee is $18, so a $5 ceiling yields nothing."""
    assert search_listings("graphic tee", max_price=5.0) == []


def test_nonexistent_size_returns_empty():
    """No listing is size XXXL, so a tee search at that size is empty."""
    assert search_listings("tee", size="XXXL") == []


def test_no_exception_on_empty_description():
    """A blank description must not raise; size/price-only search is valid."""
    results = search_listings("", max_price=20.0)
    assert isinstance(results, list)
    assert all(r["price"] <= 20.0 for r in results)


def test_size_token_match_is_flexible():
    """A size 'M' query should match combined sizes like 'S/M'."""
    results = search_listings("", size="M")
    assert results, "expected items in size M / S/M / M/L"
    assert all("m" in {t for t in r["size"].lower().replace("/", " ").split()}
               or "one" in r["size"].lower()
               for r in results)
