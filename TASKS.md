# TASKS.md – Build task list

Derived from `PLAN.md` (intent) and `IMPLEMENTATION.md` (how). Written 31 Oct 2026.
State at time of writing: **nothing built**. Folder holds only the two docs, the brief PDF, `flights.csv` and the workbook. Not a git repo.

Sizes: S ≈ <1 h, M ≈ 1–2 h, L ≈ 2–4 h (one person + Claude Code).
`→` = depends on. Each milestone's tests must pass before the next milestone's work is merged (IMPLEMENTATION §0.6).

## Status (31 Oct 2026, 14:35 SGT)

| Workstream | State |
|---|---|
| WS-A Foundations (M1) | Done, tests green |
| WS-B Decision core (M2) | Done, tests green |
| WS-C Spine (M3) | Done. `python -m dn.run --showcase --scripted` runs end to end with no API key |
| WS-D Agents + coordinator (M4) | Done with scripted agents. **D4 (live Claude showcase run) blocked on `ANTHROPIC_API_KEY`** |
| WS-E UI (M5) | Done (`app/streamlit_app.py`), AppTest green for run, pressure, replay, approve |
| WS-F Evaluation (M6) | Done with scripted agents (51 scenarios, 11 s). Rerun with `--agents claude` once the key is set |
| WS-G Pitch | Not started |

49 tests pass. Two quick code reviews were run (M1+M2, M3+M4); all confirmed bugs fixed with regression tests.

### Decisions taken (D1-D3: team lead said go with recommendations)
- D1: FCFS on N767SK diverts under the model; test asserts that.
- D2: FCFS kept, labelled "(model)"; Actual 2015 shown next to every system.
- D3: Evaluation set is pre-departure scenarios only.

### Deviations from IMPLEMENTATION.md (state these if asked)
1. **No `temperature=0`**: current Claude models (Sonnet 5.5) reject sampling params and forced `tool_choice`. Agents use structured outputs (`messages.parse`). Determinism lives in the code layer (contracts, coordinator, fallback); the saved log is the replay.
2. **LLM fills a draft schema; code merges helper contracts and workbook limits.** Loosening a helper contract is structurally impossible rather than detected. `LOOSENING_ATTEMPT` still fires for stated limits looser than the workbook or than the agent's own earlier limits (the pressure test path).
3. **ATC evaluates 5-minute slots**: a target is available if any minute in [t, t+5) meets wake spacing. Exact-minute checking left only 46% of slots and an almost empty feasible set.
4. **Late-inbound scenarios**: forecast from `LATE_AIRCRAFT_DELAY` at the **origin** by departure hour; simulation never diverts (aircraft leaves when ready, arrival delay = max(W, d)).
5. **Arrival day rollover uses `SCHEDULED_TIME`** (local times across time zones; 716 rows were wrongly pushed a day). Forecast also excludes the arrival day for overnight flights.
6. **Tie-break and broadcast order** use (P(divert), expected arrival delay, plan_id). Expected delay alone ignores diverted samples and would favour HOLD.
7. Reason code `ARRIVAL_DELAY` renamed `LATE_ARRIVAL` (avoids a sealed column name in prompts).
8. Ground overtime budget and helper contracts are enforced inside each agent's own domain code at turn 3 (private data never leaves it).
9. Log: every agent message and mandate must carry a valid HMAC, and DONE signatures must match the commitments. Known limit: truncating the tail of a log is not detectable without an external anchor.

### Diversion issue: fixed (31 Oct, 15:00)
Cause found by diagnosis over the 41 weather scenarios: 20 had a safe plan available, **15 were forced to divert by the airline's crew-duty contract**, 5 had weather longer than any plan (W > 120 + 15), 1 by ATC slots. The duty contract counted the *next* leg, so a next-leg duty problem forced this flight to divert. Airlines swap crews instead.
Fix (PLAN section 10 and IMPLEMENTATION section 7 updated first): hard duty limit on **this leg** only; a next-leg breach is a soft cost `next_leg_crew_swap`, escalated to the airline duty manager and counted in the simulation. Scripted airline (and the airline prompt) treat divert risk at or below the 10% target as acceptable before preferring shorter delays.
Result (scripted agents, 51 scenarios): diversions ours 26 -> 11, rulebook 25 -> 11, FCFS 41 (no change, no coordination). On the same non-diverted flights vs 2015: ours +3.5 min arrival, -24.4 min next-leg delay; rulebook +14.6 / -13.4.
Tried and reverted: a departure re-check rule. Observing "still closed at departure" adds no information for flights shorter than their ground delay, and the naive version over-extended (showcase to 110 min).
Showcase note: the O'Hare July early-morning forecast (n 41) has median 78 min and P90 178 min, so even a 115 min ground delay keeps a 22% divert risk. The real 31 min was the lucky case. Present this as the honest trade-off; the human chooses the risk.

---

## 0. Decisions needed before / during build (blockers)

Found by checking the spec against the real data. IMPLEMENTATION §0.2 says ask, don't guess, so these need a team answer.

| # | Issue | Evidence | Recommendation |
|---|---|---|---|
| D1 | **Simulation test contradicts the simulation model.** §14 says "N767SK with FCFS reproduces arrival delay 31", but FCFS = d 0, HOLD, and the model says W 31 > 0 + 15 → **diverted**. | §14 rules vs §14 tests | Change the test to expect DIVERT under the model. In the demo, say the real 2015 flight was not diverted because it was held 31 min on the ground at Dayton (DEPARTURE_DELAY 31 = WEATHER_DELAY 31), which is what our agents recommend, but 15 min before departure instead of reactively. |
| D2 | **FCFS baseline is a strawman.** In the data, 97.8% of `WEATHER_DELAY > 15` flights took the delay on the ground at departure, and **0 rows are DIVERTED or CANCELLED**. Under the model, FCFS will "divert" ~74% of ORD cases, which never happened. Judges reward honest baselines. | `DEPARTURE_DELAY >= WEATHER_DELAY` in 97.8% of rows; `DIVERTED.sum() == 0` | Keep FCFS (spec), but label it "reactive, no coordination (model)" and always show "Actual 2015" next to it. Report next-leg delay and holding fuel vs **Actual 2015** as the headline, not diversions vs FCFS. |
| D3 | **Airborne mode almost always diverts.** 48% of rows have `SCHEDULED_TIME > 120` → `airborne` → only HOLD or DIVERT; with a median W of 31, most divert in the sim. That skews the 50-scenario eval. | `SCHEDULED_TIME <= 120` share = 0.52 | Option A: draw the eval set from `pre_departure` scenarios only and report airborne separately as a known limitation. Option B: keep the spec mix and say so. Recommend A. |
| D4 | Team size, hours left, submission deadline. | PLAN §15 | Needed to pick the cut line (§17). |
| D5 | `ANTHROPIC_API_KEY` is not set in this shell. | `env` | Needed from Milestone 4. Put it in `.env` (gitignored). |
| D6 | System Python is 3.14 with no deps installed. | `import pandas` fails | Use `uv` with a Python 3.12 venv (`uv venv -p 3.12`). No spec change. |

---

## Workstreams at a glance

```
            WS-A Foundations (M1)
                   |
     +-------------+--------------+------------------+
     v             v              v                  v
 WS-B Decision  WS-C Spine     WS-D Agents        WS-E UI shell
 core (M2)      (M3)           prompts/schemas    (mock data)
     |             |              |                  |
     +------+------+              |                  |
            v                     |                  |
      WS-D Coordinator (M4) <-----+                  |
            |                                        |
            +--------> WS-E UI live (M5) <-----------+
            |
            +--------> WS-F Evaluation (M6)
                                |
                                v
                      WS-G Pitch & submission
```

Critical path: A1→A2→A4→B1/B3→C1→D3→D4→F1→F3→G2. Everything else hangs off it.

**Interface freeze first (T0, ~1 h):** `config.py`, `schemas.py` (all pydantic models incl. `Plan`, `Contract` union, turn messages, `Scenario` views) are written and merged before parallel work starts, so every workstream codes against the same types.

---

## WS-A Foundations (Milestone 1)

| ID | Task | Files | Done when | Size | → |
|---|---|---|---|---|---|
| A0 | Repo setup: `git init`, folder layout per §2, move `flights.csv` and xlsx into `data/` (gitignored), `requirements.txt`, `.env.example` (demo-only HMAC keys), `.gitignore` (`data/`, `runs/`, `.env`), uv venv 3.12, `pytest` runs green on an empty suite | root | `uv run pytest` passes | S | – |
| A1 | `config.py`: every constant from §4.1; assert they match the `fuel_and_crew` sheet at load | `src/dn/config.py` | import works, assertion test | S | A0 |
| A2 | `time_utils.py`: `hhmm_to_min`, 2400→1440, next-day rollover, `min_to_hhmm` for UI | `time_utils.py`, test | `hhmm_to_min(1305)==785`, rollover cases | S | A0 |
| A3 | `data_loader.py`: load CSV (`low_memory=False`, airport codes as str, 3-letter alpha filter, log count), parse 4 workbook sheets with the right header rows, parse "Super (A380)"→Super, "Any other pair" default, leading-number parse of "2,400 kg per hour". Cache the loaded frame (parquet in `runs/` or `lru_cache`) because the CSV is 38 MB | `data_loader.py`, `test_data_loader.py` | 358,774 rows; 322 airports; ORD = (4, 150, 90, 45, 3); Heavy→Large = 5 nm; default = 3 nm | M | A1 |
| A4 | `schemas.py` interface freeze (T0): `Plan`, `Contract` discriminated union (6 types), `ReasonCode` enum, `Turn1Contracts`, `Turn2Ranking`, `Turn3Commitment`, `Mandate`, `PublicScenario`, `AtcPrivate`, `AirlinePrivate`, `GroundPrivate`, `SealedOutcome`, `RecommendedPlan`, `FallbackResult`, log `Event` enum. Every synthetic field has `synthetic: true` | `schemas.py` | models import, round-trip JSON | M | A1 |
| A5 | `scenario.py` public part: flight id, wake category rule, `decision_mode`, `decision_time`, `disruption` label, destination record, `next_leg` lookup (same day + tail, origin = dest, sched dep > sched arr) | `scenario.py` | showcase next leg = OO5164 ORD→CLE 06:48 | M | A3, A4 |
| A6 | Alternate airport rule (§4.4) | `scenario.py` | ORD → MDW; airport with no candidate → None | S | A3 |
| A7 | Private states, seeded (seed 42 + scenario id): ATC arrival timeline + wake mix + taxiway label; Airline fuel, crew duty, connections, turbulence flag; Ground gates G1 + S1..Sn with busy intervals, shift end. Showcase overrides (duty crosses 13 h at ground delay ≥ 35; Cleveland connections note) | `scenario.py` | same seed → identical states; showcase overrides present | L | A5 |
| A8 | Sealing: `SealedOutcome`, `for_agent(role)`, `for_coordinator()`; sealed only reachable from simulate/baselines/evaluate | `scenario.py`, `test_leakage.py` (static part) | test asserts no sealed column name or value in any agent/coordinator view | M | A7 |
| A9 | `scenario.showcase()` | `scenario.py` | returns the 15 Jul OO6262 N767SK DAY→ORD row | S | A5 |

**M1 gate:** `test_data_loader`, leakage (static), showcase tests green.

---

## WS-B Decision core (Milestone 2) – can start right after A4, using fixtures

| ID | Task | Files | Done when | Size | → |
|---|---|---|---|---|---|
| B1 | `forecast.py`: 4-level fallback, exclude own month+day, quantiles P10–P90, sample, `p_exceeds`, level + n returned; late-inbound variant on `LATE_AIRCRAFT_DELAY` | `forecast.py`, `test_forecast.py` | ORD all-months median 31 ±1 with no exclusion; excluding a day changes n; level fallbacks trigger | M | A3 |
| B2 | `plan_space.py`: enumerate per §6, plan_id format | `plan_space.py`, `test_plan_space.py` | pre-departure ORD = 101 plans; airborne count correct | S | A4, A6 |
| B3 | `contracts.py`: evaluate all 6 types, `feasible`, `is_tightening`, `explain_empty` (greedy + removal pass) | `contracts.py`, `test_contracts.py` | satisfy/violate per type; subset accepted, superset rejected; constructed conflict explained | L | B2 |
| B4 | Contract helpers per role: ATC `available_arrival_minutes` (wake nm ÷ 150 kt both sides + reduced hourly capacity), Airline `max_ground_delay` from duty (+ optional `latest_arrival`), Ground `gate_window_free` + `gate_change_notice=20` | `contracts.py` (or `helpers.py`) | hand-built timelines give expected minutes; showcase airline helper caps d below 35 | L | B3, A7 |
| B5 | `mandates.py`: 3 mandates, HMAC signing with org keys, `check_commitment` → `MANDATE_VIOLATION`; ground overtime budget rule; DIVERT always flagged for human | `mandates.py`, `test_mandates.py` | ATC claiming `gate` rejected; overtime > 60 blocks Ground signature | M | A4 |
| B6 | `domain_costs.py`: ATC `holding_load`, Airline `expected_cost` (p_divert, E[hold], E[arrival delay], missed connections, duty flag), Ground `expected_cost` (gate change, E[next-leg delay], E[overtime]) | `domain_costs.py`, test | hand-computed values on a 5-sample forecast | M | B1, B2 |

**M2 gate:** all B tests green.

---

## WS-C Deterministic spine (Milestone 3) – E2E with no LLM

| ID | Task | Files | Done when | Size | → |
|---|---|---|---|---|---|
| C1 | `fallback.py`: rulebook §12 (smallest d with `p_exceeds(d+15) ≤ 0.10`, gate preference, largest d if none; empty F → DIVERT flagged; no alternate → HOLD G1 + "no safe option"); returns branch id | `fallback.py`, `test_fallback.py` | each branch covered; same input twice → byte-identical output | M | B1, B3 |
| C2 | `consensus_log.py`: append-only JSONL, canonical JSON, sha256 chain from 64 zeros, HMAC per agent message, `verify()` returning first broken seq | `consensus_log.py`, `test_log.py` | tampering one byte is detected at the right seq | M | A4 |
| C3 | `simulate.py`: 3 branches, holding fuel kg, next-leg delay, diverted → "aircraft unavailable", synthetic missed connections + overtime; side-by-side with Actual 2015 ("model estimate vs recorded 2015 outcome") | `simulate.py`, `test_simulate.py` | three branches; next-leg arithmetic; N767SK FCFS per **D1** decision | M | A8, A7 |
| C4 | `baselines.py`: FCFS, fallback-only (with helper contracts), hindsight hook (point-mass forecast) | `baselines.py` | showcase FCFS and fallback-only produce plans + sim results | S | C1, C3, B4 |
| C5 | CLI script `python -m dn.run --showcase --no-llm`: scenario → helpers → fallback → simulate → log → verify | `src/dn/run.py` | prints plan, sim, "Log verified" | S | C1–C4 |

**M3 gate:** showcase runs end to end without any API key.

---

## WS-D Agents + coordinator (Milestone 4)

| ID | Task | Files | Done when | Size | → |
|---|---|---|---|---|---|
| D1 | Prompts `atc.md`, `pilot.md`, `ground.md`: role, goals from the brief, mandate, "actual delay unknown", cannot accept plans outside contracts, may not loosen, output only via the tool. Can be drafted in parallel from day one | `agents/prompts/` | reviewed by the team against PLAN §4, §9 | M | A4 |
| D2 | `agents/base.py`: one Anthropic call per turn, temperature 0, tool-use structured output bound to the turn schema, 30 s timeout, no retry, schema fail → `SCHEMA_REJECT`; input = `for_agent(role)` + forecast + cost-tool outputs + published contracts + coordinator broadcast only. Log the exact prompt sent (needed for the leakage scan). `FakeAgent` for tests | `agents/base.py`, `atc.py`, `pilot.py`, `ground.py` | fake-agent tests pass; one live call per role returns a valid model | L | A4, B6, D1 |
| D3 | `coordinator.py` state machine INIT→T1→T2→T3→DONE/FALLBACK: parallel calls per turn, helper-not-loosened check, tighten-only, broadcast ≤15 plans (+ FCFS-equivalent + fallback plan), Borda max-min with tie-breaks, T3 mandate + self-consistency + contracts recheck, plain-language summary from reason codes (code, not LLM), every transition logged | `coordinator.py`, `test_coordinator.py` | with FakeAgents: happy path, missing agent, empty F, loosening attempt, mandate violation, self-contradiction, reject at T3; never > 3 turns | L | B3, B5, C1, C2, D2 |
| D4 | Live showcase run with real agents; tune prompts only (not numbers) until the run is clean; save the log as the demo fixture `runs/showcase/log.jsonl` | – | 9 API calls visible in log, DONE or explained FALLBACK, log verifies | M | D3, D5 key |

**M4 gate:** coordinator tests green with fakes; one live showcase log saved.

---

## WS-E UI (Milestone 5) – shell can start early against fixture JSON

| ID | Task | Done when | Size | → |
|---|---|---|---|---|
| E1 | Streamlit skeleton: tabs (Run, Evaluation, Rules, Log), scenario picker, renders from a saved log file (replay mode) | replay of a fixture log renders | M | A4, C2 |
| E2 | Disruption card + forecast line "Forecast from n flights (level k), your own day excluded" + synthetic badges | showcase card correct | S | E1, B1 |
| E3 | Three agent columns: mandate, private summary (operator view, labelled), turn cards, red rejections with reason codes | live and replay both render | M | E1, D3 |
| E4 | Coordinator strip (feasible-set size per turn, Borda scores, selected plan) + result card + per-role Approve buttons writing `HUMAN_APPROVAL` | approval appears in log and log still verifies | M | E3 |
| E5 | Reveal panel (collapsed): 2015 actual vs our plan vs FCFS, incl. CLE next leg | showcase reveal correct | S | C3 |
| E6 | Pressure-test toggle on the showcase (injects the §15 pressure line into Pilot T2/T3) to show the rejected commitment live | rejection card shown in red | S | D3 |
| E7 | Rules tab (workbook rules verbatim + PLAN §10 assumptions), Log tab (raw JSONL + verify status), Evaluation tab (reads `eval_summary.md`) | tabs populated | S | F3 |
| E8 | Copy pass: no em dashes, every synthetic value labelled | checklist item ticked | S | E1–E7 |

---

## WS-F Evaluation (Milestone 6)

| ID | Task | Done when | Size | → |
|---|---|---|---|---|
| F1 | Scenario sampler: 40 weather + 10 late-aircraft with same-tail next leg, seed 42 (per **D3**), plus showcase → `runs/scenarios.json` | file stable across runs | S | A5 |
| F2 | Batch runner: Ours, FCFS, Fallback-only, Hindsight, Actual 2015 over the same set; resumable (cache each scenario's log so a crash doesn't re-spend API calls); track wall-clock + LLM calls | all systems run on 5 scenarios, then 50 | L | C4, D3, F1 |
| F3 | Metrics table → `runs/eval_summary.csv` + `.md`: arrival delay, holding min + kg, diversions, next-leg delay, missed connections (synthetic), overtime (synthetic), violations in binding plans, turns distribution, fallback rate, escalations, decision time, calls/scenario | table generated | M | F2 |
| F4 | Integrity tests: pressure (concession attempts vs binding = 0), agent removal, scripted ATC gate claim, convergence ≤ 3, fallback determinism, leakage scan over every logged prompt (values **and** column names) | all pass, numbers in summary | M | F2 |
| F5 | Pick the two story cases: one where agents beat fallback through private info (connections note), one that falls back (visible failure) | case ids recorded for slides | S | F3 |
| F6 | Acceptance checklist §18 walk-through, tick each item with evidence | all 10 ticked | S | all |

Budget check: ~51 scenarios × 9 calls × (Ours + Hindsight) + pressure runs ≈ 1,000 calls. Run 5 first, then the full set.

---

## WS-G Pitch & submission

| ID | Task | Done when | Size | → |
|---|---|---|---|---|
| G1 | Answer PLAN §15 open questions: a sourced figure for phone-coordination time (or drop the claim), any cited real values | sources in PLAN §16 | S | – |
| G2 | Slides for the 3-min script (PLAN §12): problem, live demo, reveal, eval table, USPs, honest limits incl. D1–D3 | deck done | M | F3, F5 |
| G3 | Backup: screen recording of the showcase run (in case wifi or API fails on stage), replay mode as second fallback | video file + replay works offline | S | D4, E5 |
| G4 | README (1 page: install, run, replay, eval) | fresh clone runs | S | C5 |
| G5 | Rehearse to ≤ 3:00, twice, timed | under time | S | G2 |
| G6 | Submit early (time discipline 5%) | submitted | S | G5 |

---

## Suggested split

**1 person (+ Claude Code subagents):** A → B → C → D → E (live only) → F → G. Run D1 prompts and E1 shell as parallel subagents once A4 is in.

**2 people:**
- P1 (engine): A, B, C, D2–D4, F2–F4
- P2 (product): D1 prompts, E (against fixtures, then live), F1, F5, G

**3–4 people:**
- P1: A + C (data, scenario, sealing, log, sim)
- P2: B + D3 (contracts, mandates, costs, coordinator)
- P3: D1–D2, D4 + F (agents, prompts, eval)
- P4: E + G (UI, slides, recording, rehearsal)

## Cut line (from IMPLEMENTATION §17, unchanged)
Drop in this order: hindsight baseline → Rules tab → 50 → 20 scenarios → turbulence flag.
Never drop: sealing, contracts, mandates, fallback, log, pressure test.
