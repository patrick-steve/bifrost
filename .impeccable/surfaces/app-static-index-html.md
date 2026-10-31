---
version: 1
slug: "app-static-index-html"
primary_target: "app/static/index.html"
related_targets: []
---

# Surface brief: negotiation dashboard (app/static/index.html)

Scope: the single-page dashboard served by app/server.py. Visitor mode: Operate.
Audience: hackathon judges at a laptop during a 3-minute demo, then ops roles (controller, airline duty manager, ramp lead). Job: watch three agents negotiate one disrupted flight, see why each plan was ruled out, see the agreed plan or the fallback, approve it, then compare with 2015 and the evaluation.
Constraints: offline, plain HTML/CSS/JS, no em dashes, synthetic values labelled, scripted agents labelled no AI.
Memorable moment: the plan board filling with red mandatory marks turn by turn until one yellow direction sign points at the agreed plan.

## Direction contract
THESIS: Airfield signage as the grammar of a negotiation: where you are, what is mandatory, which way to go. Refuses the generic card dashboard where every box has equal weight.
OWN-WORLD: Light concrete ground. Black panels with yellow type and yellow keyline mark location (current step, IDs). Yellow panels with black type and arrows mark direction (recommended plan, next action). Red panels with white type mark mandatory limits and rejections. Condensed sign face for panels, plain sans body, tabular numerals, 1px rules, square corners.
STORY: Judge sees the flight and the uncertainty, presses Run, watches each party publish limits, rank and sign, sees what each limit ruled out on the plan board, reads the recommendation or the honest fallback, approves as a human, then reveals 2015.
FIRST VIEWPORT: Top bar (product name, scenario select, agent mode, pressure toggle, Run primary, Replay). Protocol strip of location signs: Setup, Turn 1, Turn 2, Turn 3, Decision, Approval. Left: disruption card with forecast histogram. Right: outcome sign (empty state tells you to press Run). Below: three agent columns plus coordinator lane, rows aligned by turn.
FORM: Airside signage, my pick (position 1 of my ordered list); seed:2f59a86fa1cf05d3. Signature move: plan board, every plan a cell, cells struck by the red mandatory mark of whoever ruled them out, the chosen one carries a yellow direction sign. Motion: turns reveal in sequence while the location sign advances.
FINISH: unreviewed and undocumented is unfinished; this build ends with the finish review, the verdict, DESIGN.md, and every shipping raster carrying its provenance
