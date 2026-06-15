"""
tools.py

The three required FitFindr tools. Each tool is a standalone function that
can be called and tested independently before being wired into the agent loop.

Complete and test each tool before moving to agent.py.

Tools:
    search_listings(description, size, max_price)            → list[dict]
    outfit_preference_tool(preference_indicator, preference) → dict
    suggest_outfit(new_item, wardrobe, clothing_preference)  → str
    create_fit_card(outfit, new_item)                        → str
"""

import os
import re

from dotenv import load_dotenv
from groq import Groq

from utils.data_loader import load_listings

load_dotenv()

# Filler words stripped from a search description so they don't dilute scoring.
# Size/price phrasing ("size", "under", "$30") is also dropped here in case the
# caller passes a raw phrase instead of clean keywords.
_STOPWORDS = {
    "a", "an", "the", "and", "or", "for", "with", "in", "of", "to", "me",
    "i", "im", "looking", "want", "need", "find", "show", "some", "any",
    "size", "sized", "under", "below", "less", "than", "max", "around",
    "about", "something", "that", "is", "fits", "fit", "wear", "style",
}


def _tokenize(text: str) -> list[str]:
    """Lowercase a string and split it into alphanumeric word tokens."""
    return re.findall(r"[a-z0-9]+", text.lower())


def _size_matches(query_size: str, listing_size: str) -> bool:
    """Case-insensitive size match. A query token matches if it appears as a
    whole token in the listing size, so 'M' matches 'S/M' and 'M/L' but a
    listing like 'XL' does not. 'One Size' items always match."""
    listing_tokens = set(_tokenize(listing_size))
    if "one" in listing_tokens and "size" in listing_tokens:
        return True
    query_tokens = set(_tokenize(query_size))
    return bool(query_tokens & listing_tokens)


# ── Groq client ───────────────────────────────────────────────────────────────

# Model used for the LLM tools (styling suggestions, captions).
_STYLING_MODEL = "llama-3.3-70b-versatile"


def _get_groq_client():
    """Initialize and return a Groq client using GROQ_API_KEY from .env."""
    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        raise ValueError(
            "GROQ_API_KEY not set. Add it to a .env file in the project root."
        )
    return Groq(api_key=api_key)


def _chat(
    messages: list[dict],
    model: str = _STYLING_MODEL,
    temperature: float = 0.7,
    max_tokens: int = 600,
) -> str:
    """
    Send a chat completion to Groq and return the response text.

    This is the single network seam for the LLM tools — tests monkeypatch it
    so the contract (prompt shape, guard behavior) can be checked without
    burning API calls (see BUILD_LOG N3).
    """
    client = _get_groq_client()
    response = client.chat.completions.create(
        model=model,
        messages=messages,
        temperature=temperature,
        max_tokens=max_tokens,
    )
    return (response.choices[0].message.content or "").strip()


# ── Tool 1: search_listings ───────────────────────────────────────────────────

def search_listings(
    description: str,
    size: str | None = None,
    max_price: float | None = None,
) -> list[dict]:
    """
    Search the mock listings dataset for items matching the description,
    optional size, and optional price ceiling.

    Args:
        description: Keywords describing what the user is looking for
                     (e.g., "vintage graphic tee").
        size:        Size string to filter by, or None to skip size filtering.
                     Matching is case-insensitive (e.g., "M" matches "S/M").
        max_price:   Maximum price (inclusive), or None to skip price filtering.

    Returns:
        A list of matching listing dicts, sorted by relevance (best match first).
        Returns an empty list if nothing matches — does NOT raise an exception.

    Each listing dict has the following fields:
        id, title, description, category, style_tags (list), size,
        condition, price (float), colors (list), brand, platform

    TODO:
        1. Load all listings with load_listings().
        2. Filter by max_price and size (if provided).
        3. Score each remaining listing by keyword overlap with `description`.
        4. Drop any listings with a score of 0 (no relevant matches).
        5. Sort by score, highest first, and return the listing dicts.

    Before writing code, fill in the Tool 1 section of planning.md.
    """
    listings = load_listings()

    # Keywords the user actually cares about (filler/size/price words removed).
    keywords = [t for t in _tokenize(description) if t not in _STOPWORDS]

    scored: list[tuple[int, float, dict]] = []
    for item in listings:
        # Hard filters first — price ceiling and size.
        if max_price is not None and item["price"] > max_price:
            continue
        if size and not _size_matches(size, item["size"]):
            continue

        # Build one searchable blob from the fields a shopper would describe.
        haystack = " ".join(
            [
                item["title"],
                item["description"],
                item["category"],
                " ".join(item["style_tags"]),
                " ".join(item["colors"]),
                item.get("brand") or "",
            ]
        )
        haystack_tokens = set(_tokenize(haystack))

        # Score = how many distinct query keywords appear in the listing.
        # Title/style-tag hits are weighted slightly higher (better signal).
        strong_tokens = set(_tokenize(item["title"] + " " + " ".join(item["style_tags"])))
        score = 0
        for kw in set(keywords):
            if kw in haystack_tokens:
                score += 2 if kw in strong_tokens else 1

        # With no keywords (size/price-only search), every surviving item counts.
        if not keywords:
            score = 1

        if score > 0:
            scored.append((score, item["price"], item))

    # Best match first; cheaper item wins ties.
    scored.sort(key=lambda t: (-t[0], t[1]))
    return [item for _, _, item in scored]


# ── Tool 4: outfit_preference_tool ─────────────────────────────────────────────

def outfit_preference_tool(
    preference_indicator: bool,
    clothing_preference: str | None = None,
) -> dict:
    """
    Record an optional clothing preference to bias later outfit styling.

    The user is asked whether they have a style preference. If they say yes,
    the text they provide (e.g. "baggy", "earth tones") is recorded so
    suggest_outfit() can honor it. This tool never raises — every input maps
    to a documented result dict.

    Args:
        preference_indicator: True if the user says they have a preference,
                              False if they don't.
        clothing_preference:  The preference text. Only meaningful when
                              preference_indicator is True.

    Returns:
        A dict with:
        - recorded (bool):   True only when a non-empty preference was stored.
        - preference (str|None): the cleaned preference text, or None.
        - message (str):     a user-facing confirmation or re-prompt.

    Behavior:
        - said yes + non-blank text → recorded, preference stored.
        - said yes + blank/whitespace → not recorded, re-prompt to add one
          or say no instead.
        - said no → not recorded, acknowledge and confirm that's okay.
    """
    cleaned = (clothing_preference or "").strip()

    if not preference_indicator:
        return {
            "recorded": False,
            "preference": None,
            "message": (
                "No problem — I won't apply a style preference. "
                "You can tell me how you like to dress anytime."
            ),
        }

    if not cleaned:
        return {
            "recorded": False,
            "preference": None,
            "message": (
                "You said you have a style preference but didn't describe it. "
                "Tell me how you like to dress (e.g. 'baggy', 'earth tones'), "
                "or say no if you changed your mind."
            ),
        }

    return {
        "recorded": True,
        "preference": cleaned,
        "message": f"Got it — I'll style outfits around your preference: {cleaned}.",
    }


# ── Tool 2: suggest_outfit ────────────────────────────────────────────────────

def _format_item(item: dict) -> str:
    """Render a listing dict as a compact, readable block for the LLM prompt."""
    parts = [f"- Name: {item.get('title', 'Unknown item')}"]
    if item.get("category"):
        parts.append(f"- Category: {item['category']}")
    if item.get("colors"):
        parts.append(f"- Colors: {', '.join(item['colors'])}")
    if item.get("style_tags"):
        parts.append(f"- Style: {', '.join(item['style_tags'])}")
    if item.get("description"):
        parts.append(f"- Description: {item['description']}")
    return "\n".join(parts)


def _format_wardrobe(items: list[dict]) -> str:
    """Render wardrobe items grouped by category so the LLM sees what's
    available per slot (and, by omission, which slots are empty)."""
    by_category: dict[str, list[str]] = {}
    for entry in items:
        category = entry.get("category", "other")
        label = entry.get("name", "unnamed item")
        colors = ", ".join(entry.get("colors", []))
        label = f"{label} ({colors})" if colors else label
        by_category.setdefault(category, []).append(label)

    lines = []
    for category in ("tops", "bottoms", "outerwear", "shoes", "accessories"):
        if category in by_category:
            lines.append(f"{category}: " + "; ".join(by_category[category]))
    # Any unexpected categories still get listed.
    for category, labels in by_category.items():
        if category not in {"tops", "bottoms", "outerwear", "shoes", "accessories"}:
            lines.append(f"{category}: " + "; ".join(labels))
    return "\n".join(lines)


def _build_outfit_messages(
    new_item: dict,
    wardrobe: dict,
    clothing_preference: str | None,
) -> list[dict]:
    """Build the chat messages for suggest_outfit. Pure (no network) so it can
    be unit-tested for prompt contract and the empty-wardrobe branch."""
    items = (wardrobe or {}).get("items") or []
    pref = (clothing_preference or "").strip()
    pref_line = (
        f"The user likes to dress like this: {pref}. Work that into the styling."
        if pref
        else "The user has no specific style preference on record."
    )
    item_block = _format_item(new_item)

    system = (
        "You are FitFindr, a warm, practical personal stylist for secondhand "
        "fashion. Give concrete, wearable advice and keep it concise and skimmable."
    )

    if not items:
        user = (
            f"A shopper is considering this secondhand item:\n{item_block}\n\n"
            f"{pref_line}\n\n"
            "Their wardrobe is empty, so you can't pair it with pieces they "
            "already own. Give GENERAL styling advice for this item: what kinds "
            "of tops, bottoms, shoes, and outerwear pair well with it, the vibe "
            "it suits, and 1-2 example outfits they could build around it. Do "
            "not invent specific items they own."
        )
    else:
        wardrobe_block = _format_wardrobe(items)
        user = (
            f"A shopper is considering this secondhand item:\n{item_block}\n\n"
            f"Here is their current wardrobe, grouped by category:\n"
            f"{wardrobe_block}\n\n"
            f"{pref_line}\n\n"
            "Suggest 1-2 complete outfits that pair the new item with specific, "
            "named pieces from their wardrobe. For each outfit, cover top, "
            "bottom, and shoes, plus outerwear/accessories when they fit. "
            "Reference wardrobe pieces by name. If a slot has nothing suitable "
            "in their wardrobe, say so explicitly (e.g. 'no shoes in your "
            "wardrobe yet'). Keep it short and skimmable."
        )

    return [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]


def suggest_outfit(
    new_item: dict,
    wardrobe: dict,
    clothing_preference: str | None = None,
) -> str:
    """
    Given a thrifted item and the user's wardrobe, suggest 1–2 complete outfits.

    Args:
        new_item: A listing dict (the item the user is considering buying).
        wardrobe: A wardrobe dict with an 'items' key containing a list of
                  wardrobe item dicts. May be empty — handled gracefully with
                  general styling advice instead of an error.
        clothing_preference: Optional recorded preference (e.g. "baggy",
                  "earth tones") from outfit_preference_tool, used to bias the
                  styling. Backward-compatible default None.

    Returns:
        A non-empty string with outfit suggestions. Never raises — on bad input
        or an LLM failure it returns a descriptive message string instead.
    """
    if not isinstance(new_item, dict) or not new_item:
        return (
            "I need an item to style first — search for a listing, then I can "
            "build outfits around it."
        )

    messages = _build_outfit_messages(new_item, wardrobe, clothing_preference)
    try:
        suggestion = _chat(messages, temperature=0.7)
    except Exception as exc:  # noqa: BLE001 — N4: tool must never raise
        return (
            "Sorry, I couldn't put together an outfit just now "
            f"({type(exc).__name__}). Please try again in a moment."
        )

    return suggestion or (
        "I couldn't think of an outfit for this item — try a different piece "
        "or add more to your wardrobe."
    )


# ── Tool 3: create_fit_card ───────────────────────────────────────────────────

def _format_price(value) -> str:
    """Render a listing price as '$24.00', falling back gracefully on bad data."""
    try:
        return f"${float(value):.2f}"
    except (TypeError, ValueError):
        return "an unlisted price"


def _build_fit_card_messages(outfit: str, new_item: dict) -> list[dict]:
    """Build the chat messages for create_fit_card. Pure (no network) so the
    prompt contract can be unit-tested without burning API calls."""
    item = new_item or {}
    name = item.get("title", "this thrifted find")
    price = _format_price(item.get("price"))
    platform = item.get("platform") or "secondhand"

    system = (
        "You write short, authentic OOTD captions for secondhand fashion finds — "
        "the kind a real person posts on Instagram or TikTok, not a product "
        "description. Casual, specific, a little witty."
    )
    user = (
        f"Write a 2-4 sentence caption for this outfit.\n\n"
        f"The thrifted piece: {name}, {price}, found on {platform}.\n"
        f"The styled outfit:\n{outfit.strip()}\n\n"
        "Guidelines:\n"
        f"- Mention the item name, its price ({price}), and the platform "
        f"({platform}) naturally — each exactly once.\n"
        "- Capture the outfit's vibe in specific terms (not generic hype).\n"
        "- Sound like a real post: casual, authentic, no hashtag spam.\n"
        "- Return only the caption text."
    )
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]


def create_fit_card(outfit: str, new_item: dict) -> str:
    """
    Generate a short, shareable outfit caption for the thrifted find.

    Args:
        outfit:   The outfit suggestion string from suggest_outfit().
        new_item: The listing dict for the thrifted item.

    Returns:
        A 2–4 sentence caption usable as an Instagram/TikTok caption.
        If outfit is empty or missing, returns a descriptive guard message —
        never raises (N4). Caller is routed back to suggest_outfit first.

    The caption mentions the item name, price, and platform once each, captures
    the outfit vibe in specific terms, and uses a higher LLM temperature so it
    reads differently each time.
    """
    if not isinstance(outfit, str) or not outfit.strip():
        return (
            "I don't have an outfit to caption yet — use the outfit suggestion "
            "first, then I can write a fit card for it."
        )

    messages = _build_fit_card_messages(outfit, new_item)
    try:
        caption = _chat(messages, temperature=0.9)
    except Exception as exc:  # noqa: BLE001 — N4: tool must never raise
        return (
            "Sorry, I couldn't write a fit card just now "
            f"({type(exc).__name__}). Please try again in a moment."
        )

    return caption or (
        "I couldn't come up with a caption for this outfit — try regenerating it."
    )
