# disruption-negotiation

Autonomous SG 2026, Airbus track, Challenge #2. Three independent agents (ATC, Airline, Ground) negotiate a recovery plan for one disrupted flight in at most 3 turns, under a coordinator that holds no private data, with a deterministic fallback rulebook and a hash-chained, HMAC-signed consensus log. See `PLAN.md` (intent), `IMPLEMENTATION.md` (spec), `TASKS.md` (status and deviations).

## Setup
```bash
uv venv -p 3.12 .venv && uv pip install -p .venv -r requirements.txt -e .
cp .env.example .env            # add ANTHROPIC_API_KEY for real agents
# data/ must contain flights.csv and challenge2_operational_constraints.xlsx
```

## Run
```bash
.venv/bin/pytest -q                                      # tests
.venv/bin/python -m dn.run --showcase --scripted         # N767SK end to end, no LLM
.venv/bin/python -m dn.run --showcase                    # Claude agents
.venv/bin/python -m dn.run --showcase --scripted --pressure
.venv/bin/python -m dn.evaluate --agents scripted        # 51 scenarios, all baselines, integrity tests
.venv/bin/python -m dn.evaluate --agents claude          # same with Claude agents (~1,000 calls)
.venv/bin/streamlit run app/streamlit_app.py             # UI
```
Outputs land in `runs/`: per-scenario `log.jsonl` and `prompts.jsonl`, `eval_summary.md|csv`, `scenarios.json`.

"Scripted" agents are deterministic rule-following stand-ins (no AI) used for tests, offline demos and integrity tests. They are labelled as such everywhere.
