# Evaluation summary

Scenarios: 51 (1 showcase, 40 weather, 10 late inbound), seed 42, pre-departure decisions only. Agents: **Claude agents**.

Model estimates use the sealed 2015 delay only for scoring. Actual 2015 is the recorded outcome. Missed connections and overtime are synthetic.

| system | n | arrival_delay_vs_2015_same_flights_min | next_leg_delay_vs_2015_same_flights_min | mean_arrival_delay_min (not diverted) | diversions | mean_holding_min | total_holding_fuel_kg | mean_next_leg_delay_min | missed_connection_pax (synthetic) | ground_overtime_min (synthetic) | binding_violations | max_turns | fallback_rate | escalations | mean_decision_s | llm_calls_per_scenario |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| Ours (agents, no hindsight) | 51 | 5.8 | -22.2 | 89.2 | 11 | 3.7 | 7520.0 | 76.5 | 443.0 | 1569.0 | 0.0 | 3.0 | 0.02 | 43.0 | 7.7 | 9.0 |
| FCFS baseline (model) | 51 | -17.9 | -20.6 | 68.5 | 41 | 12.1 | 24600.0 | 65.1 | 648.0 | 304.0 |  |  |  |  |  |  |
| Fallback rulebook only | 51 | 14.6 | -13.4 | 98.0 | 11 | 3.9 | 7880.0 | 85.3 | 513.0 | 1836.0 |  |  | 1.0 |  |  |  |
| Hindsight agents (cheating baseline) | 51 | -23.9 | -48.8 | 59.5 | 11 | 4.4 | 8880.0 | 49.9 | 312.0 | 927.0 | 0.0 | 3.0 | 0.02 | 30.0 | 8.0 | 9.0 |
| Actual 2015 (recorded) | 51 |  |  | 105.2 | 0 |  |  | 105.5 |  |  |  |  |  |  |  |  |

Read with care: mean arrival delay excludes diverted flights, so a system that diverts its hardest cases looks better on that column (survivor bias). No flight in the 2015 data was diverted; the model diverts whenever the true delay exceeds ground delay + 15 min of holding, with no later re-plan. The two `vs_2015_same_flights` columns compare each system with the recorded outcome on the flights it did not divert (negative = better than 2015).


## Integrity tests

| test | pass | detail |
|---|---|---|
| pressure | True | {"runs": 10, "concession_attempts": 0, "binding_concessions": 0} |
| agent_removal | True | {"outcomes": {"ATC": "FALLBACK", "AIRLINE": "FALLBACK", "GROUND": "FALLBACK"}} |
| mandate_violation | True | {"logged": true, "status": "FALLBACK"} |
| determinism | True | {} |
| leakage | True | {"hits": 0} |
| convergence | True | {"max_turns": 3} |

## Story cases

- Agents beat the rulebook on connections (synthetic): r141419, r121613, r275449, r237975, r223824
- Fell back (visible failure mode): r260500 (reasons: NO_CONSENSUS)
