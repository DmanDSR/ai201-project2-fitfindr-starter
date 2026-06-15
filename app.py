"""
app.py

Gradio interface for FitFindr. The layout and wiring are already set up —
your job is to fill in handle_query() so it calls run_agent() and maps
the session results to the three output panels.

Run with:
    python app.py

Then open the localhost URL shown in your terminal (usually http://localhost:7860,
but check your terminal — the port may differ).
"""

import gradio as gr

from agent import run_agent
from utils.data_loader import get_empty_wardrobe, get_example_wardrobe

EMPTY_WARDROBE_LABEL = "Empty wardrobe (new user)"


# ── formatting ────────────────────────────────────────────────────────────────

def _format_listing(item: dict) -> str:
    """Render a selected listing dict as readable text for the listing panel."""
    if not isinstance(item, dict) or not item:
        return "No listing details available."

    title = item.get("title", "Untitled listing")
    price = item.get("price")
    price_str = f"${float(price):.2f}" if isinstance(price, (int, float)) else "price n/a"

    facts = [price_str]
    if item.get("size"):
        facts.append(f"size {item['size']}")
    if item.get("condition"):
        facts.append(f"{item['condition']} condition")

    lines = [title, " · ".join(facts)]

    source = " · ".join(
        part for part in (item.get("brand"), item.get("platform")) if part
    )
    if source:
        lines.append(source)
    if item.get("style_tags"):
        lines.append("Tags: " + ", ".join(item["style_tags"]))
    if item.get("colors"):
        lines.append("Colors: " + ", ".join(item["colors"]))
    if item.get("description"):
        lines.append("")
        lines.append(item["description"])

    return "\n".join(lines)


# ── query handler ─────────────────────────────────────────────────────────────

def handle_query(user_query: str, wardrobe_choice: str) -> tuple[str, str, str]:
    """
    Called by Gradio when the user submits a query.

    Args:
        user_query:     The text the user typed into the search box.
        wardrobe_choice: Either "Example wardrobe" or "Empty wardrobe (new user)".

    Returns:
        A tuple of three strings (listing_text, outfit_suggestion, fit_card),
        one per output panel. On an empty query or an early agent stop (e.g. no
        matching listings), the message goes in the first panel and the other
        two are blank.
    """
    # 1. Guard against an empty query before doing any work.
    if not isinstance(user_query, str) or not user_query.strip():
        return (
            "Type what you're after first — e.g. 'vintage graphic tee under "
            "$30, size M'.",
            "",
            "",
        )

    # 2. Pick the wardrobe the user selected (default to the example).
    wardrobe = (
        get_empty_wardrobe()
        if wardrobe_choice == EMPTY_WARDROBE_LABEL
        else get_example_wardrobe()
    )

    # 3. Run the planning loop.
    session = run_agent(user_query, wardrobe)

    # 4. Early stop (no results, etc.) → message in the listing panel only.
    if session.get("error"):
        return session["error"], "", ""

    # 5. Success → format the three panels.
    return (
        _format_listing(session.get("selected_item")),
        session.get("outfit_suggestion") or "",
        session.get("fit_card") or "",
    )


# ── interface ─────────────────────────────────────────────────────────────────

EXAMPLE_QUERIES = [
    "vintage graphic tee under $30",
    "90s track jacket in size M",
    "flowy midi skirt under $40",
    "black combat boots size 8",
    "designer ballgown size XXS under $5",   # deliberate no-results test
]

def build_interface():
    with gr.Blocks(title="FitFindr") as demo:
        gr.Markdown("""
# FitFindr 🛍️
Find secondhand pieces and get outfit ideas based on your wardrobe.
Describe what you're looking for — include size and price if you want to filter.
        """)

        with gr.Row():
            query_input = gr.Textbox(
                label="What are you looking for?",
                placeholder="e.g. vintage graphic tee under $30, size M",
                lines=2,
                scale=3,
            )
            wardrobe_choice = gr.Radio(
                choices=["Example wardrobe", "Empty wardrobe (new user)"],
                value="Example wardrobe",
                label="Wardrobe",
                scale=1,
            )

        submit_btn = gr.Button("Find it", variant="primary")

        with gr.Row():
            listing_output = gr.Textbox(
                label="🛍️ Top listing found",
                lines=8,
                interactive=False,
            )
            outfit_output = gr.Textbox(
                label="👗 Outfit idea",
                lines=8,
                interactive=False,
            )
            fitcard_output = gr.Textbox(
                label="✨ Your fit card",
                lines=8,
                interactive=False,
            )

        gr.Examples(
            examples=[[q, "Example wardrobe"] for q in EXAMPLE_QUERIES],
            inputs=[query_input, wardrobe_choice],
            label="Try these queries",
        )

        submit_btn.click(
            fn=handle_query,
            inputs=[query_input, wardrobe_choice],
            outputs=[listing_output, outfit_output, fitcard_output],
        )
        query_input.submit(
            fn=handle_query,
            inputs=[query_input, wardrobe_choice],
            outputs=[listing_output, outfit_output, fitcard_output],
        )

    return demo


if __name__ == "__main__":
    demo = build_interface()
    demo.launch()
