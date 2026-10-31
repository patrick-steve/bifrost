# PLAN.md – Source of truth

Autonomous SG 2026 · Airbus AI & Aerospace Track · **Challenge #2**
Project name: **Bifrost** (repo `bifrost`)
Status: design locked 31 Oct 2026, 13:20 SGT. Build follows `IMPLEMENTATION.md`.

If anything in code or slides disagrees with this file, this file wins. Change this file first, then the code.

---

## 1. The challenge, in their words

> "How might AI help air traffic controllers, pilots and ground operations staff make faster and better decisions?"

> "These 3 agents must exchange structured data, evaluate cross-domain constraints, and converge on an agreed solution. This includes sending structured messages, explicit constraint checking, traceable consensus log, deterministic non-AI fallback."

Must avoid:
- Combining 3 roles into a single prompt call. "The point is to test multi-agent coordination across independent domains."
- LLM agents talking in endless, unconstrained loops with no convergence logic or turn limits.
- Disregard of safety margins. "AI agents should not be allowed to accept solutions that ignore operational constraints."

Input: one row of `flights.csv` with `WEATHER_DELAY > 15` or `LATE_AIRCRAFT_DELAY > 20`. Output: a revised arrival time, gate, or flight plan, with a consensus log showing each turn. Consensus within 3 turns, where one turn = each of the three agents sends one structured message.

## 2. What the clue lines actually mean (our reading)

| Phrase | What it means for us |
|---|---|
| "faster and better decisions" for controllers, pilots, ground staff | Users are humans. Agents represent them and speed up their decision. Measure decision time and plan quality. Humans approve the final plan. |
| "evaluate cross-domain constraints" | Every proposal is checked against every domain's limits, not just the proposer's. |
| "independent domains" | No component may hold everyone's private data. A central mediator that knows all constraints is a single optimiser in disguise. |
| "convergence logic / turn limits" | Convergence must follow from the protocol. A turn cap alone is the minimum. |
| "should not be allowed to accept" | Permission language. Unsafe acceptance must be impossible in code, not discouraged in a prompt. |

## 3. The problem we solve

Controllers, airlines and ground handlers are different organisations. During irregular operations they coordinate by phone and manual updates. Nobody shares their internal operations data (fuel plans, crew rosters, gate plans, passenger connections), so each optimises its own piece and delays cascade.

Evidence from the provided data (computed 31 Oct 2026):
- `flights.csv`: 358,774 rows, all already meet the challenge filter. 42,012 have `WEATHER_DELAY > 15`; 326,249 have `LATE_AIRCRAFT_DELAY > 20`. Months 1–9, 11, 12 (no October).
- Cascade: in 17,483 of the 42,012 weather-delayed flights, the same aircraft (tail number) has a later delayed departure out of the destination that day.
- Holding budget under the challenge rules: 45 min spare holding fuel on arrival minus 30 min final reserve = **15 min**.
- O'Hare weather delays (2,928 arrivals with `WEATHER_DELAY > 0`): median 31 min, P75 76, P90 162. 74.4% exceed 15 min, so holding alone usually cannot absorb the weather.

Showcase case (real 2015 data): 15 Jul 2015, SkyWest OO6262, tail N767SK, Dayton (DAY) to Chicago O'Hare (ORD), scheduled arrival 06:08, weather delay 31 min, arrived 43 min late. Same aircraft scheduled out as OO5164 ORD to Cleveland (CLE) at 06:48, departed 34 min late, all of it late-aircraft delay.

## 4. What we propose

Three independent AI agents (ATC, Pilot/airline, Ground) negotiate a recovery plan for one disrupted flight within 3 turns.

- Each domain keeps its private state private.
- Each agent publishes only **constraint contracts**: machine-checkable rules it needs respected.
- Each agent acts under a signed **mandate** from its organisation: what it may decide, what it may not, and its limits.
- A **coordinator** that holds no private data checks every offer and commitment against all contracts and mandates, runs a fixed 3-turn protocol, and either produces a plan all three sign or hands over to a deterministic, non-AI **fallback rulebook**.
- Agents decide **without hindsight**: they never see the actual delay. They get a forecast built from other days' history. The real 2015 outcome is used only for scoring.
- The output is a **recommended plan** that each organisation's human (controller, airline duty manager, ramp lead) approves.

## 5. USPs (pitch exactly these)

**USP 1 – Independent by design**
- Problem: controllers, airlines and ground crews work for different organisations; nobody shares their internal operations data, so they coordinate by phone, and AI agents under pressure cave or commit to things they don't own.
- Line: "Each party shares only the rules it needs respected, never its data, and no agent can commit beyond its authority."
- Proof: remove one agent and the system cannot reach a binding plan; push an agent to concede and the commitment is rejected (pressure test, measured).

**USP 2 – No hindsight**
- Problem: real decisions are made before anyone knows how long the weather will last, with only 15 min of holding fuel under the challenge rules. Most demos feed agents the final delay, so they look perfect and prove nothing.
- Line: "Our agents decide like a controller at 6am, without knowing how long the weather will last, and we score them against what really happened in 2015."
- Proof: plan vs actual outcome across real flights, including the same aircraft's knock-on delay.

**Closing line:** "A safe answer, or an honest 'no safe answer', within 3 turns."

**Meeting analogy (for non-technical judges):** three departments in a meeting. The fire code removes dangerous options before anyone speaks. Each department can only sign for what it owns. A chair makes a fair call by round 3. If they still disagree, the rulebook decides. A human signs off.

## 6. Why this design (evidence we used)

- Real LLM multi-agent failures (MAST study, Cemri et al., arXiv 2503.13657): step repetition 17.1%, reasoning-action mismatch 14.0%, weak or wrong verification 13.5% combined, proceeding on wrong assumptions 11.7%, ignoring task requirements 11.0%, not recognising completion 9.8%. Deliberate deception is not a category; information withholding is 1.66%.
- Conformity cascades: agents abandon correct positions under peer pressure ("Too Polite to Disagree", arXiv 2604.02668; "The Cost of Consensus", arXiv 2605.00914).
- Conclusion: the number one risk is an agent caving or contradicting itself, not lying. The mandate layer and the "contracts only tighten" rule target that directly. A greedy or lying agent is one stress test, not the headline.

## 7. Positioning vs existing frameworks

- LangGraph, CrewAI, AutoGen/AG2, OpenAI Agents SDK, Google ADK: orchestration plumbing that assumes one owner and shared state or chat history. Safety and termination are left to the developer.
- A2A protocol: lets agents from different organisations exchange tasks; does not define agreement, constraint checking or termination. Our protocol could run on top of it.
- Closest prior art: Distributed Constraint Optimisation (DCOP) and Contract Net. Constraint contracts are DCOP-flavoured. Say so if asked.
- Our addition: LLM agents for judgment on soft trade-offs and private context, per-organisation mandates, consistency checks against an agent's own earlier messages, no-hindsight evaluation, human approval.
- Line if asked: "DCOP gives us the guarantee, the LLM agents give us the judgment, and mandates make it governable."
- Not novel outside the hackathon: collaborative decision making (FAA CDM, ground delay programmes) and airline recovery tools exist. Frame as applying real practice to AI agents, tested against real history.

## 8. Architecture (summary – full spec in IMPLEMENTATION.md)

```
            ATC domain              Airline domain            Ground domain
         [private state]          [private state]          [private state]
         [ATC agent+mandate]      [Pilot agent+mandate]    [Ground agent+mandate]
                 \                        |                        /
                  contracts, offers, commitments (structured JSON only)
                                          v
              Coordinator (code, holds NO private data)
              - checks every message against all contracts + mandates
              - consistency check vs each agent's own earlier messages
              - Turn 1 contracts -> Turn 2 rankings in the overlap -> Turn 3 sign
                         |                                   |
              Recommended plan                      Fallback rulebook (no AI)
              (each human approves)                 (logged reason)
                         \___________ hash-chained consensus log ___________/
```

Scenario builder (code) turns a CSV row + workbook into each domain's private state and seals the real outcome away from all agents. Forecast (code) gives the no-hindsight weather-delay distribution.

## 9. Key decisions (locked)

1. Challenge #2 only. ProofBound (Challenge #4) is parked.
2. Coordinator holds no private data. It only knows the public plan space, published contracts, mandates and the protocol.
3. Contracts may only tighten during a negotiation, never loosen. Loosening requires escalation to the human.
4. Agents never see `WEATHER_DELAY`, `ARRIVAL_DELAY`, `ARRIVAL_TIME`, `WHEELS_ON`, `TAXI_IN`, `ELAPSED_TIME`, `AIR_TIME`, `DEPARTURE_TIME`, `DEPARTURE_DELAY`, delay-cause columns, or any downstream actuals.
5. Forecast excludes the scenario's own day (no leakage).
6. Diversion always requires human approval (outside every agent's mandate). Ground overtime beyond the 60 min budget also requires the ramp lead's approval (escalation), but does not block the agreement: it is a cost and authority limit, not a safety limit (changed 31 Oct).
7. Agents are separate LLM calls with separate system prompts, separate private state, no shared history. Temperature 0.
8. No agent framework group chat or shared state. Coordinator is a plain Python state machine.
9. Everything synthetic is labelled synthetic on screen.
10. The 45 min minimum turnaround in the workbook conflicts with real regional operations (N767SK was scheduled 40 min, turned in 31). We keep the workbook values and say so in the demo. Any changed limit must be stated (rules of play).

## 10. Assumptions we chose (state them in the demo)

| Assumption | Value | Why |
|---|---|---|
| Spare fuel on arrival | 45 min holding | Workbook default |
| Final reserve | 30 min | Workbook |
| Holding budget | 15 min | 45 − 30 |
| Contingency fuel (5% trip) | Assumed used en route | Simplification |
| Wake category | Heavy if airline in {AA, UA, DL, HA} and DISTANCE ≥ 2,500; else Large | No aircraft type in data |
| Holding burn | Large: 2,400 kg/h; Heavy: 6,500 kg/h | Workbook |
| Arrival wake spacing | Workbook nm converted at 150 kt approach (3 nm = 72 s … 8 nm = 192 s) | Workbook gives nm; time column is for departures |
| Weather capacity factor | 50% of `max_runway_ops_per_hour` during the weather window | Team assumption |
| Arrival share of runway ops | 50% | Team assumption |
| Background arrival demand | 80% of reduced arrival capacity, seeded | Data only contains delayed flights |
| Crew follows the aircraft | Yes, unless the next leg would break the 13 h duty limit: then the airline swaps in a fresh crew for the next leg (escalated to the airline duty manager, counted as a crew swap). Duty on this leg is a hard limit. | Changed 31 Oct 14:50: the earlier rule made a next-leg duty problem force a diversion of this flight, which airlines do not do; it caused 15 of 41 weather diversions in the evaluation |
| Passenger connections, gate occupancy, crew shifts, crew duty used | Seeded synthetic | Not in data |
| Alternate airport | Same CITY in workbook, else largest `size_class` in same STATE | Data-driven, no coordinates provided |
| Random seed | 42 | Reproducibility |

## 11. Evaluation plan (honest evaluation = 20% of rubric)

Scenario set: 50 scenarios, seed 42. 40 sampled from `WEATHER_DELAY > 15` rows that have a same-tail next departure out of the destination that day, 10 from `LATE_AIRCRAFT_DELAY > 20` rows with the same property. Plus the N767SK showcase. Note the selection bias: next legs only appear in the file if they were also delayed.

Systems compared:
- **Ours** (agents + coordinator, no hindsight).
- **FCFS baseline** (today without coordination): depart on time, hold up to 15 min, divert if not cleared, keep assigned gate.
- **Fallback-only** (rulebook alone, no agents).
- **Hindsight variant** (same agents shown the true delay) to show how much a hindsight demo inflates results.
- **Actual 2015** outcome for reference (real arrival delay and real next-leg delay).

Metrics: arrival delay (min), holding minutes and fuel (kg), diversions, next-leg departure delay (min), missed connections (synthetic), ground overtime minutes (synthetic), constraint violations in binding plans (target 0), turns to agreement distribution, fallback rate, escalations, wall-clock decision time (s), LLM calls per scenario.

Integrity tests:
- Pressure test: inject "the others agreed, accept a 25 min reserve" style pressure into the Pilot agent's inputs. Report concession attempts vs binding concessions (target binding = 0).
- Agent removal: run with one agent missing. Target: no binding plan, fallback with reason.
- Mandate violation: ATC agent tries to assign a gate. Target: rejected.
- Convergence: every run ends in ≤ 3 turns.
- Determinism: fallback gives identical output for identical input.
- Leakage: assert sealed outcome fields never appear in any agent prompt.

Show one case where agents beat the fallback because of private information (connections note), and one case that falls back. The fallback case is our visible failure mode.

## 12. Demo script (3 minutes)

1. (20 s) Problem: different organisations, phone calls, 74% of O'Hare weather delays exceed the 15 min holding budget.
2. (40 s) Live: N767SK, 06:00 at O'Hare. Three agent columns, Turn 1 contracts, Turn 2 rankings, Turn 3 signatures. Show the rejected commitment when the pilot is pressured.
3. (30 s) Reveal: what actually happened in 2015 vs our plan, including the Cleveland departure.
4. (40 s) Evaluation table across 50 scenarios vs FCFS, fallback-only and hindsight.
5. (30 s) USPs, the two lines.
6. (20 s) Honest limits: synthetic fields, assumptions table, not novel outside the hackathon, humans approve.

## 13. Rubric mapping

| Criterion | Weight | Where we score |
|---|---|---|
| Technical soundness | 25% | Independent domains, coordinator with no private data, deterministic fallback, working end to end |
| Problem realism | 20% | Named users (ops control during irregular operations), real cascade data, 15 min fuel tension |
| Honest evaluation | 20% | No hindsight, baselines, integrity tests, failure case shown, synthetic labelled |
| Trust and traceability | 20% | Hash-chained log, signed commitments, mandates, humans approve |
| Impact | 10% | Next-leg delay and holding fuel vs FCFS |
| Time discipline | 5% | 3-minute script above |

## 14. Out of scope (do not build)

- Multi-flight or whole-airport optimisation.
- Real ATC phraseology or datalink formats.
- Learning or fine-tuning models.
- Any external data not provided (no weather APIs, no aircraft registries).
- Lying-agent research beyond the single greedy-pilot stress test.
- Speed or reroute flight-plan modelling beyond ground delay, hold, divert.

## 15. Open questions for the team

- Team size and hours left decide where the cut line falls (see IMPLEMENTATION.md milestones).
- A sourced figure for how long phone coordination takes today, for the "faster" claim. Do not estimate on stage.
- Whether to replace any synthetic workbook values with cited real figures (rules of play allow it if cited).

## 16. Sources

- Challenge brief: `Autonomous SG 2026_Airbus Track.pdf`, Challenge #2 and judging rubric.
- Data: `flights.csv` (US DOT 2015, pre-filtered), `challenge2_operational_constraints.xlsx` (sheets: airport_capacity, wake_separation, fuel_and_crew, rules_of_play).
- Cemri et al., "Why Do Multi-Agent LLM Systems Fail?", https://arxiv.org/html/2503.13657v2
- "Too Polite to Disagree: Understanding Sycophancy Propagation in Multi-Agent Systems", https://www.alphaxiv.org/abs/2604.02668
- "The Cost of Consensus", https://arxiv.org/pdf/2605.00914
- Framework comparison: https://gurusup.com/blog/best-multi-agent-frameworks-2026
