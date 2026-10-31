# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Stack
FastAPI (Python) serving one static page in plain HTML/CSS/JS, no build step. Reuses the `dn` engine directly. Must run offline on the demo laptop. Replaces the earlier Streamlit UI.

## Users
Primary: hackathon judges (Autonomous SG 2026, Airbus AI and Aerospace track) watching a 3-minute live demo on a laptop screen. They must understand every box, card and button at a glance, without narration.
Represented roles (the people the product is for in reality): the arrival air traffic controller, the airline duty manager / flight crew, and the ground ramp lead, each from a different organisation, coordinating a recovery plan for one disrupted flight during irregular operations. Today they coordinate by phone.

## Product Purpose
Three independent AI agents (ATC, Airline, Ground) negotiate a recovery plan (revised arrival time, gate, or ground delay / hold / divert) for one disrupted flight from the 2015 US DOT data, in at most 3 turns. A coordinator holding no private data checks every message against every published constraint and mandate. If there is no safe agreement, a deterministic non-AI rulebook decides and says why. Humans approve the final plan. Success: a safe answer, or an honest "no safe answer", within 3 turns, faster than phone coordination.

## Positioning
- Independent by design: each party shares only the rules it needs respected (constraint contracts), never its data, and no agent can commit beyond its signed mandate.
- No hindsight: agents decide like a controller at decision time, from a forecast built from other days' history; the real 2015 outcome is revealed only afterwards for scoring.
Closing line: "A safe answer, or an honest 'no safe answer', within 3 turns."

## Operating Context
Demo flow (3 minutes): problem (20 s), live negotiation on the showcase flight N767SK DAY to ORD 15 Jul 2015 (40 s, including a pressure test where the airline agent is pushed to accept a 25 min fuel reserve and the commitment is rejected), reveal of what actually happened in 2015 (30 s), evaluation table over 51 scenarios vs baselines (40 s), USPs (30 s), honest limits (20 s).
Turn structure: Turn 1 each agent publishes constraint contracts; Turn 2 each ranks up to 5 plans from the feasible overlap; Turn 3 each accepts or rejects the selected plan (signed). Coordinator selects by max-min Borda score. Every event goes to a hash-chained, HMAC-signed log that can be verified.

## Capabilities and Constraints
- API: run a scenario (scripted deterministic agents with no AI, or Claude agents when ANTHROPIC_API_KEY is set), with optional pressure test; replay a saved log; append human approvals; verify the log; evaluation summary; workbook rules and stated assumptions.
- Synthetic values (private operator states: booked arrivals, gate occupancy, crew duty, connections, shift ends, turbulence) must be visibly labelled synthetic.
- Scripted agents must be visibly labelled "no AI".
- No em dashes in UI copy.
- Terminology: contract, mandate, feasible set, Borda score, fallback rulebook, escalation, consensus log, decision time, forecast level.

## Evidence on Hand
- `runs/eval_summary.md` / `runs/eval_results.jsonl`: evaluation over 51 scenarios (scripted agents at time of writing; Claude-agent numbers pending the API key).
- Showcase: N767SK, OO6262 DAY to ORD, scheduled arrival 06:08, real weather delay 31 min, arrived 43 min late; next leg OO5164 ORD to CLE departed 34 min late.
- No customers, testimonials, or deployment claims exist. Do not invent any.

## Product Principles
1. Safety is enforced by code, not persuasion: show the checks, rejections and fallbacks as first-class content, not errors to hide.
2. Separate what each party knows: private state stays visually inside its own column; shared/public facts live in shared space.
3. Every number says where it came from: real 2015 data, forecast from history, model estimate, or synthetic.
4. Honest outcomes over flattering ones: failure cases and fallbacks are shown as clearly as successes.
5. Humans decide: the system recommends; approvals are explicit actions.

## Accessibility & Inclusion
Readable at laptop distance by judges; colour is never the only carrier of meaning (accept/reject/fallback states also use text and icons).
