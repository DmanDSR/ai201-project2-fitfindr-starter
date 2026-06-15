# FitFindr — planning.md

> Complete this document before writing any implementation code.
> Your spec and agent diagram are what you'll use to direct AI tools (Claude, Copilot, etc.) to generate your implementation — the more specific they are, the more useful the generated code will be.
> Your planning.md will be reviewed as part of your submission.
> Update it before starting any stretch features.

---

## Tools

List every tool your agent will use. For each tool, fill in all four fields.
You must have at least 3 tools. The three required tools are listed — add any additional tools below them.

### Tool 1: search_listings

**What it does:**
<!-- Describe what this tool does in 1–2 sentences -->
 this tool will intake information from the user, clothing type, size, and price, and search the clothing database to find an item that matches the description.

**Input parameters:**
<!-- List each parameter, its type, and what it represents -->
- `description` (str): with clothing type shirt, pants, jacket, etc
- `size` (str): small, small/medium, medium, medium/large, large, x-large, xx-large
- `max_price` (float): anywhere from 0.00 to (should cap at the highest price clothing item)

**What it returns:**
<!-- Describe the return value — what fields does a result contain? -->

this function will return a list of clothing items that fit the users description, stating the details relevant, size, description, price

**What happens if it fails or returns nothing:**
<!-- What should the agent do if no listings match? -->

if the function finds nothing it will return, no clothing items that fit this description and would let the user trying another item

---

### Tool 2: suggest_outfit

**What it does:**
<!-- Describe what this tool does in 1–2 sentences -->
this function will use the information gather from the function above to suggest an outfit, if there was no look up it will ask the user to specify an item, and give one suggest of what they could use. The function would then search the wardrobe to see if there are any items that go with the clothing item. to see if there is a clothing preference the function will ask the clothing_preference to ask and record the preference other wise if none that section is blank. it will use this info to help pick an outfit

**Input parameters:**
<!-- List each parameter, its type, and what it represents -->
- `new_item` string: the new clothing type that is available
- `wardrobe` (dict): the wardrobe of the user to look for outfits 
- `preferenceIndicator` (bool): lets the system know if a clothing preference was indicated 
- `clothingPreference`  (String): this is the preference for what the user likes to wear, so like baggy cloths, ot jeans , or shorts things of that nature.

**What it returns:**
<!-- Describe the return value -->

this tool will return a clothing recommendation using the information the user provides, so it will give a top, a bottom, (if there are any shoes in the wardrobe) shoes, (other garments if available). the tool gives  back a stylish outfit using the information available in the wardrobe about the different clothing items 

**What happens if it fails or returns nothing:**
<!-- What should the agent do if the wardrobe is empty or no outfit can be suggested? -->

If there are no clothes in the wardrobe the system will stat that the wardrobe is empty please add clothes to the wardrobe to use this function. if there are clothing not in the wardrobe for the outfit suggesting the system will suggest what is available and state that there are no item for example (blue shirt, there are no pants available in wardrobe, black shoes, etc), but if there is only oce type of clothing that will be stated. 
---

### Tool 3: create_fit_card

**What it does:**
<!-- Describe what this tool does in 1–2 sentences -->
THis tool is to help create a social media tag/caption for the suggested outfit. the tool will return the fit suggestion and the cool witty caption that matches the outfit.
**Input parameters:**
<!-- List each parameter, its type, and what it represents -->
- `outfit` (String?): this is the outfit from the outfit suggestion tool

**What it returns:**
<!-- Describe the return value -->
this tool will return a the outfit description then underneath it will be the witty caption that goes with the suggestion

if the user does not ask for a outfit suggestion the user can still just generate random captions for there clothing choices anyways.
**What happens if it fails or returns nothing:**
<!-- What should the agent do if the outfit data is incomplete? -->

if there is no outfit provided the system will say outfit not provided please use the suggestion tool first.
if there is an issue with the information being passed the system will indicate that the outfit format is wrong please report.

---

### Additional Tools (if any)

<!-- Copy the block above for any tools beyond the required three -->

#tool 4: outfit_preference_tool

**what it does**

this tool will ask and record any out preferences the user has. the user will be asked if they have an outfit preference if yes it will then record the preference to be used for the outfit_suggestion tool.

**Input parameters**
- `preferenceIndicator` (bool): will record yes or no
- `clothing_preference` (String): this is the preference for what the user likes to wear, so like baggy cloths, ot jeans , or shorts things of that nature.

**what it returns**

it will let the user know its response was received, the contents of the tool will be used for the other tool after if needed.

**What happens if it fails or returns nothing:**
 this this fails the system will say that no preference was recorded. the system will check to see if a preference was written when the user says yes, if the user doesn't put anything in the tool will ask them to input a preference or type no if they changed there mind

---

## Planning Loop

**How does your agent decide which tool to call next?**
<!-- Describe the logic your planning loop uses. What does it look at? What conditions change its behavior? How does it know when it's done? -->
 The agent greets the user and explains what it can do, then waits for a request. On each turn it looks at two things: the user's latest message and the current session state (whether a search has run, whether a clothing preference is recorded, whether the wardrobe has been checked, and whether an outfit exists yet).

It decides the next tool by intent + what data is already available:

If the user is describing an item they want → call search_listings (needs description / size / max_price pulled from the message).
If the user mentions how they like to dress, or no preference is recorded yet → call outfit_preference_tool to capture it (this is optional and feeds the next step).
If the user wants styling → before suggest_outfit, check the wardrobe. If it's empty, the agent stops and asks the user to add clothes instead of calling the tool.
If an outfit has been produced and the user wants to share it → call create_fit_card (it requires an existing outfit; if none exists, the agent routes back to suggest_outfit first).
Conditions that change behavior: no matching listings → tell the user and offer to adjust the search; empty wardrobe → block suggest_outfit and prompt to add items; no preference given → proceed without one rather than forcing it; no outfit yet → can't make a fit card.

How it knows it's done: the loop ends when the user's request has been fully answered (they received listings, an outfit, and/or a fit card) and there's no tool whose inputs are now ready but uncalled. The agent then returns to waiting for the next request.
---

## State Management

**How does information from one tool get passed to the next?**
<!-- Describe how your agent stores and accesses state within a session. What data is tracked? How is it passed between tool calls? -->
The agent keeps a session state object (a dictionary) that persists for the whole conversation, and each tool reads from it and writes back to it. The fields tracked are:

wardrobe (dict) — the user's items, loaded once and reused
preference_indicator (bool) and clothing_preference (str) — written by outfit_preference_tool, read by suggest_outfit
search_results (list) — the listings returned by search_listings
current_outfit (str/dict) — the outfit produced by suggest_outfit, read by create_fit_card
Information passes between tools through this shared state rather than the tools calling each other directly. For example: outfit_preference_tool writes clothing_preference = "baggy jeans" into state → later, suggest_outfit reads that field and uses it to filter the wardrobe → its result is stored as current_outfit → create_fit_card reads current_outfit to write the caption.

The planning loop also reads this state to decide what to do next (e.g. if current_outfit is empty, it knows it can't call create_fit_card yet). When a tool can't run because its required state is missing, the agent uses that gap to route to the tool that fills it first.
---

## Error Handling

For each tool, describe the specific failure mode you're handling and what the agent does in response.

| Tool | Failure mode | Agent response |
|------|-------------|----------------|
| search_listings | No results match the query | lets the user know that there were no cloths that match the criteria |
| suggest_outfit | Wardrobe is empty | notifies the user that the wardrobe need clothes in it|
| create_fit_card | Outfit input is missing or incomplete | notifies the user they need to use the suggest_outfit tool first |
| clothing_preference | no preference saved | notifies the user they didnt add anything and asks if that is okay|


---

## Architecture

<!-- Draw a diagram of your agent showing how the components connect:
     User input → Planning Loop → Tools (search_listings, suggest_outfit, create_fit_card)
                                                                          ↕
                                                                   State / Session
     Show what triggers each tool, how state flows between them, and where error paths branch off.
     ASCII art, a Mermaid diagram (https://mermaid.js.org/syntax/flowchart.html), or an embedded
     sketch are all fine. You'll share this diagram with an AI tool when asking it to implement
     the planning loop and each individual tool. -->


![alt text](<Project Diagram.png>)
---

## AI Tool Plan

<!-- For each part of the implementation below, describe:
     - Which AI tool you plan to use (Claude, Copilot, ChatGPT, etc.)
     - What you'll give it as input (which sections of this planning.md, your agent diagram)
     - What you expect it to produce
     - How you'll verify the output matches your spec before moving on

     "I'll use AI to help me code" is not a plan.
     "I'll give Claude my Tool 1 spec (inputs, return value, failure mode) and ask it to implement
     search_listings() using load_listings() from the data loader — then test it against 3 queries
     before trusting it" is a plan. -->

**Milestone 3 — Individual tool implementations:**

I'll use Claude and build one tool at a time, never moving on until the current one passes its tests.

search_listings — I'll give Claude my Tool 1 spec (the description / size / max_price inputs, the "return a list of matching items" return value, and the "no match → tell user, offer to retry" failure mode) plus the load_listings() signature and the listing fields from the README (category, style_tags, size, price, etc.). I expect a function that loads the 40 listings and filters them by type, size, and max price. Verify: run 3 queries — one that should hit (e.g. "tee under $30"), one over-budget that should return nothing, and one with a size that doesn't exist — and confirm the right items / empty result come back.

outfit_preference_tool — I'll give Claude the Tool 4 spec (preference_indicator bool, clothing_preference str, and the "if yes but blank, re-ask" failure mode). I expect a function that records the preference into session state. Verify: test "yes + baggy jeans" (stored), "no" (left blank), and "yes + empty" (re-prompts).

suggest_outfit — I'll give Claude the Tool 2 spec plus get_example_wardrobe() and the wardrobe schema. I expect it to read the wardrobe + optional preference and return a top/bottom/shoes outfit, naming any missing slots. Verify: test against the 10-item example wardrobe (full outfit), the empty_wardrobe template (returns the "add clothes" message), and a wardrobe missing a category (states "no pants available").

create_fit_card — I'll give Claude the Tool 3 spec (outfit input, caption output, "no outfit → ask to use suggestion tool first" failure mode). I expect it to return the outfit description + a witty caption. Verify: pass a real outfit (caption generated) and pass nothing (returns the "outfit not provided" message).

**Milestone 4 — Planning loop and state management:**

I'll use Claude, giving it my Planning Loop answer, my State Management answer (the session-state dict with wardrobe / preference / search_results / current_outfit), and my Architecture Mermaid diagram so it can see the routing and error branches.

I expect it to produce (1) a session-state object the tools read from and write to, and (2) the loop that parses the user's request, reads state to pick the next tool, and stops when the request is satisfied. Verify: I'll run the full walkthrough query from the doc ("vintage graphic tee under $30, I wear baggy jeans and chunky sneakers, how would I style it?") and confirm the tools fire in order — search → preference → wardrobe check → suggest_outfit → create_fit_card — and that state carries the preference into suggest_outfit and the outfit into create_fit_card. I'll also test the empty-wardrobe path to confirm the loop blocks suggest_outfit correctly.

---

## A Complete Interaction (Step by Step)

Write out what a full user interaction looks like from start to finish — tool call by tool call. Use a specific example query.

**Example user query:** "I'm looking for a vintage graphic tee under $30. I mostly wear baggy jeans and chunky sneakers. What's out there and how would I style it?"

**Step 1:**
<!-- What does the agent do first? Which tool is called? With what input? -->

the system first looks through the query and picks out key terms/sections it can use. Paying attention aspects like price, cloths 
type, size, price, what the user is asking for, what there style normally is.

1. looking for - what the user is asking for
2. vintage graphic tee - cloths type
3. under 30$ - price
4. I mostly wear baggy jeans and chunky sneakers - what there style normally is
5. What's out there and how would I style it? - what the user is asking for


the system will use the size, price and cloths type variables to find items that fit what the user is asking


**Step 2:**
<!-- What happens next? What was returned from step 1? What tool is called now? -->

search_listing()

once the item has been searched the system would go on to the next part of the sentence which is the "I mostly wear baggy jeans and chunky sneakers" there is no too for this but I would like to add a clothing preference aspect to this system.

clothing _reference() 

I think a function to get preference should be available to get the users preference on what they like to wear. then that function should have a variable that can be used with the suggest outfit function as an optional variable to include.


**Step 3:**
<!-- Continue until the full interaction is complete -->

get_empty_wardrobe()
now for this stage the system will check the wardrobe and see if there are any clothes in it,

if nothing the function will return no clothes in wardrobe, please add clothes to use the function to use suggest_outfit.

suggest_outfit()
if there are clothes in the wardrobe the next step is to see if the user has added anything to the clothing preference variable, depending on if there is any preference depends on the search for clothes.

once the preference is figured out (empty or the preference) the system will look to find clothes that fit the preference or find clothes in general if no preference 

**Final output to user:**
<!-- What does the user actually see at the end? -->

create_fit_card()
the final output will be the clothing suggestion for the user
