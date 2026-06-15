# FitFindr 🛍️

FitFindr finds secondhand fashion listings from a natural-language request and
styles them into outfits using your wardrobe. Describe what you're after — e.g.
*"vintage graphic tee under $30, size M, I mostly wear baggy jeans"* — and it
returns the best-matching listing, a styling suggestion, and a shareable "fit
card" caption.

It's built as a small, deterministic agent: the query is parsed with plain
string rules (no network), listings are searched locally, and only the two
styling steps call an LLM (via [Groq](https://console.groq.com)). The whole flow
is exposed through a [Gradio](https://www.gradio.app/) web UI.

## How It Works

```
user query ──▶ parse (regex, no network)
                 │
                 ├──▶ outfit_preference_tool   record optional style preference
                 ├──▶ search_listings          local keyword + size + price search
                 │        └─ no matches ──▶ friendly "loosen your filters" message, stop
                 ├──▶ suggest_outfit   (LLM)    pair the top listing with wardrobe pieces
                 └──▶ create_fit_card  (LLM)    write a short OOTD caption
```

The loop lives in [agent.py](agent.py) (`run_agent`), the four tools in
[tools.py](tools.py), and the UI wiring in [app.py](app.py). State for one
interaction is passed between steps in a single session dict; `session["error"]`
is set (and the loop stops early) for an empty query or no matching listings.

## Project Layout

```
ai201-project2-fitfindr-starter/
├── app.py                     # Gradio web interface (entry point)
├── agent.py                   # run_agent() — the planning loop
├── tools.py                   # the four tools (search + 2 LLM tools + preference)
├── data/
│   ├── listings.json          # 40 mock secondhand listings
│   └── wardrobe_schema.json   # wardrobe format + example & empty wardrobes
├── utils/
│   └── data_loader.py         # helpers to load listings / wardrobes
├── scripts/
│   └── check.py               # syntax + ruff + bandit gate for a single file
├── tests/                     # pytest suite (one file per tool + agent + app)
├── planning.md                # design notes
├── BUILD_LOG.md               # build journal
├── requirements.txt           # Python dependencies
└── pyproject.toml             # ruff + pytest config
```

## Setup

Requires **Python 3.12+**.

1. (Recommended) create and activate a virtual environment:

   ```bash
   python -m venv .venv
   # Windows (PowerShell)
   .venv\Scripts\Activate.ps1
   # macOS / Linux
   source .venv/bin/activate
   ```

2. Install dependencies:

   ```bash
   pip install -r requirements.txt
   ```

3. Add your Groq API key to a `.env` file in the project root (get a free key at
   [console.groq.com](https://console.groq.com)):

   ```
   GROQ_API_KEY=your_key_here
   ```

   The `.env` file is git-ignored — never commit your key. Without it, search
   still works but the two styling tools will return an error message.

## Running the App

**Start** the web UI:

```bash
python app.py
```

Then open the URL shown in your terminal — usually
[http://localhost:7860](http://localhost:7860), but check the terminal in case
the port differs. Type a request (or click one of the example queries), pick a
wardrobe, and hit **Find it**.

**Stop** the app: press `Ctrl+C` in the terminal where it's running. (If you
started a virtual environment, run `deactivate` when you're done.)

### Try the loop without the UI

`agent.py` has a small CLI demo (a happy-path query and a no-results query):

```bash
python agent.py
```

### Check the data loads

```bash
python utils/data_loader.py
```

## Tools

| Tool | Signature | What it does |
| --- | --- | --- |
| `search_listings` | `(description, size=None, max_price=None) → list[dict]` | Local keyword/size/price search over the 40 mock listings, ranked by relevance. No network. |
| `outfit_preference_tool` | `(preference_indicator, preference=None) → dict` | Records an optional style preference (e.g. "baggy", "earth tones") to bias styling. |
| `suggest_outfit` | `(new_item, wardrobe, clothing_preference=None) → str` | **LLM.** Pairs the listing with named wardrobe pieces; gives general advice if the wardrobe is empty. |
| `create_fit_card` | `(outfit, new_item) → str` | **LLM.** Writes a short, shareable OOTD-style caption for the find. |

The LLM tools use Groq's `llama-3.3-70b-versatile` model and are written to never
raise — on bad input or an API failure they return a descriptive message string.

## Data

- **`data/listings.json`** — 40 mock secondhand listings across categories (tops,
  bottoms, outerwear, shoes, accessories) and styles (vintage, y2k, grunge,
  cottagecore, streetwear, and more). Each has: `id`, `title`, `description`,
  `category`, `style_tags`, `size`, `condition`, `price`, `colors`, `brand`,
  `platform`.
- **`data/wardrobe_schema.json`** — the wardrobe format, plus an
  `example_wardrobe` (10 items) and an `empty_wardrobe` template. Load with
  `get_example_wardrobe()` / `get_empty_wardrobe()` from
  [utils/data_loader.py](utils/data_loader.py).

## Development

Run the test suite:

```bash
pytest
```

The LLM tools are tested without burning API calls — tests monkeypatch the single
`_chat` network seam in [tools.py](tools.py).

Lint and security-check a file (used as an editor gate):

```bash
python scripts/check.py path/to/file.py   # py_compile + ruff + bandit
ruff check .                              # lint the whole project
```
