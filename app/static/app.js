import { ICONS } from "./icons.js";

/* ------------------------------------------------------------------ helpers */
const $ = (s, r = document) => r.querySelector(s);
const esc = (v) => String(v ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);
const icon = (name, cls = "") =>
  `<svg class="icon ${cls}" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${ICONS[name] || ""}</svg>`;
const hhmm = (m) => {
  if (m == null) return "";
  const d = Math.floor(m / 1440), r = ((m % 1440) + 1440) % 1440;
  return `${String(Math.floor(r / 60)).padStart(2, "0")}:${String(r % 60).padStart(2, "0")}${d > 0 ? " +1 day" : ""}`;
};
const fmt = (v, unit = "", dp = 0) => (v == null || Number.isNaN(v) ? "n/a" : `${Number(v).toFixed(dp)}${unit}`);
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const reduced = matchMedia("(prefers-reduced-motion: reduce)").matches;

async function api(path, opts = {}) {
  const res = await fetch(path, { headers: { "Content-Type": "application/json" }, ...opts });
  const body = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(body.detail || `Request failed (${res.status})`);
  return body;
}

function toast(html, kind = "red", ms = 6000) {
  const t = $("#toast");
  t.innerHTML = `<div class="callout callout--${kind}" role="alert">${icon(kind === "red" ? "triangle-alert" : "info")}<div>${html}</div></div>`;
  clearTimeout(toast._t);
  toast._t = setTimeout(() => (t.innerHTML = ""), ms);
}

/* ------------------------------------------------------------------ vocabulary */
const ROLES = [
  { id: "ATC", name: "ATC", icon: "radio-tower", human: "Arrival controller" },
  { id: "AIRLINE", name: "Airline", icon: "plane", human: "Airline duty manager and crew" },
  { id: "GROUND", name: "Ground", icon: "truck", human: "Ramp lead" },
];
const FIELD = {
  target_arrival_min: "arrival slot", strategy: "strategy (delay, hold, divert)", ground_delay_min: "ground delay",
  gate: "gate", divert_approval: "approve a diversion",
};
const REASON = {
  FUEL_RISK: "fuel reserve", CONNECTIONS: "passenger connections", DUTY: "crew duty", OVERTIME: "ramp crew overtime",
  THROUGHPUT: "runway throughput", WAKE_SEPARATION: "wake separation", TURBULENCE: "holding turbulence",
  GATE_CONFLICT: "gate conflict", NEXT_LEG: "next departure", LATE_ARRIVAL: "arrival delay",
  DIVERSION_RISK: "diversion risk", OUTSIDE_CONTRACTS: "outside published limits", OUTSIDE_MANDATE: "outside mandate",
};
const VIOLATION = {
  SCHEMA_REJECT: "Message rejected",
  MANDATE_VIOLATION: "Outside its mandate",
  LOOSENING_ATTEMPT: "Tried to loosen a safety limit",
  SELF_CONTRADICTION: "Contradicts its own earlier limit",
};
const LIMIT_TEXT = { reserve_min: "Final fuel reserve", hold_limit_min: "Holding at most", max_ground_delay_min: "Ground delay at most" };

function planText(pid, alt) {
  if (!pid) return "";
  if (pid.startsWith("DIV-")) return `Divert to ${pid.slice(4)} (needs duty manager approval)`;
  const [head, gate] = pid.split("-");
  if (head === "HOLD") return `Depart on time, hold up to 15 min if needed, gate ${gate}`;
  return `Ground delay ${head.slice(2)} min, then hold up to 15 min, gate ${gate}`;
}
const shortPlan = (pid) => (pid || "").replace("-", " · ");

function contractText(c, pub) {
  switch (c.type) {
    case "available_arrival_minutes": {
      const rel = c.minutes.map((m) => m - pub.scheduled_arrival_min);
      const total = 25;
      return [`Can land in ${c.minutes.length} of ${total} arrival slots`, rel.length ? `Open slots: +${rel.slice(0, 8).join(", +")}${rel.length > 8 ? " ..." : ""} min after schedule` : "No slot open"];
    }
    case "max_ground_delay": return [`Ground delay at most ${c.minutes} min`, c.reason];
    case "forbid_strategy": return [`No ${c.strategy.replace("_", " ").toLowerCase()}`, c.reason];
    case "gate_change_notice": return [`Gate change needs ${c.minutes} min notice`, c.reason];
    case "latest_arrival": return [`Must arrive by ${hhmm(c.minute)}`, c.reason];
    case "gate_window_free": {
      const gates = [...new Set(c.windows.map((w) => w.gate))];
      const g1 = c.windows.filter((w) => w.gate === "G1").map((w) => `${hhmm(w.free_from)} to ${hhmm(w.free_to)}`);
      return [`Gate free windows for ${gates.length} gates`, `G1 free ${g1[0] || "never"}`];
    }
    default: return [c.type, ""];
  }
}

/* ------------------------------------------------------------------ state */
const S = { meta: null, sc: null, run: null, revealed: null, playing: false, filters: { ATC: true, AIRLINE: true, GROUND: true }, stage: 0 };

/* ------------------------------------------------------------------ boot */
async function boot() {
  bindTabs();
  S.meta = await api("/api/meta");
  const sel = $("#scenario");
  const kinds = { showcase: "Showcase", weather: "Weather at destination", late_inbound: "Late inbound aircraft" };
  const groups = {};
  for (const s of S.meta.scenarios) (groups[s.kind] ||= []).push(s);
  sel.innerHTML = Object.entries(groups).map(([k, items]) =>
    `<optgroup label="${esc(kinds[k] || k)}">${items.map((s) => `<option value="${esc(s.scenario_id)}">${esc(s.label)}</option>`).join("")}</optgroup>`).join("");
  sel.addEventListener("change", () => loadScenario(sel.value));
  const claude = $("#agents-claude");
  if (!S.meta.has_api_key) {
    claude.disabled = true;
    claude.closest("label").title = "Add ANTHROPIC_API_KEY to .env and restart the server to use Claude agents.";
  }
  $("#keystate").innerHTML = S.meta.has_api_key
    ? `${icon("key-round")} Claude agents ready <b>${esc(S.meta.model)}</b>`
    : `${icon("lock")} No API key: scripted agents only`;
  $("#run").innerHTML = `${icon("play")} Run negotiation`;
  $("#replay").innerHTML = `${icon("history")} Replay saved run`;
  $("#run").addEventListener("click", runNegotiation);
  $("#replay").addEventListener("click", replay);
  document.querySelectorAll("input[name=agents], #pressure").forEach((el) => el.addEventListener("change", () => (S.run = null, S.revealed = null, S.stage = 0, renderAll())));
  bindTip();
  await loadScenario(sel.value);
}

function bindTabs() {
  const tabs = [...document.querySelectorAll(".tab")];
  const show = (tab) => {
    tabs.forEach((t) => {
      const on = t === tab;
      t.setAttribute("aria-selected", on);
      t.tabIndex = on ? 0 : -1;
      $("#" + t.getAttribute("aria-controls")).hidden = !on;
    });
    if (tab.id === "tab-eval") renderEval();
    if (tab.id === "tab-rules") renderRules();
    if (tab.id === "tab-log") renderLog();
  };
  tabs.forEach((t, i) => {
    t.addEventListener("click", () => show(t));
    t.addEventListener("keydown", (e) => {
      const d = e.key === "ArrowRight" ? 1 : e.key === "ArrowLeft" ? -1 : 0;
      if (d) { const n = tabs[(i + d + tabs.length) % tabs.length]; n.focus(); show(n); }
    });
  });
  S.showTab = (id) => show($("#" + id));
}

const opts = () => ({ agents: document.querySelector("input[name=agents]:checked").value, pressure: $("#pressure").checked });
const runId = () => `${S.sc.public.scenario_id}${opts().pressure ? "-pressure" : ""}${opts().agents === "claude" ? "-claude" : ""}`;

async function loadScenario(id) {
  S.sc = await api(`/api/scenario/${encodeURIComponent(id)}`);
  S.run = null; S.revealed = null; S.stage = 0;
  renderAll();
}

/* ------------------------------------------------------------------ run / replay */
async function runNegotiation() {
  if (S.playing) return;
  const btn = $("#run");
  btn.disabled = true; $("#replay").disabled = true;
  btn.classList.add("is-busy");
  btn.innerHTML = `${icon("rotate-ccw")} Agents negotiating`;
  S.run = null; S.revealed = null; S.stage = 0.5; renderAll();
  try {
    const o = opts();
    const run = await api("/api/run", { method: "POST", body: JSON.stringify({ scenario_id: S.sc.public.scenario_id, ...o }) });
    await play(run);
  } catch (e) {
    S.stage = 0; renderAll();
    toast(`<b>The run did not finish.</b> ${esc(e.message)}`);
  } finally {
    btn.disabled = false; $("#replay").disabled = false; btn.classList.remove("is-busy");
    btn.innerHTML = `${icon("play")} Run again`;
  }
}

async function replay() {
  try {
    const run = await api(`/api/run/${encodeURIComponent(runId())}?scenario_id=${encodeURIComponent(S.sc.public.scenario_id)}`);
    S.revealed = null;
    await play(run);
  } catch (e) {
    toast(`<b>No saved run for this flight and setting yet.</b> Press Run negotiation first.`, "info");
  }
}

async function play(run) {
  S.playing = true;
  S.run = run;
  const stop = lastStage(run);
  for (let st = 1; st <= stop; st++) {
    S.stage = st; renderAll(st);
    if (!reduced) await sleep(st <= 3 ? 750 : 350);
  }
  S.playing = false;
  renderAll();
}

/* ------------------------------------------------------------------ log parsing */
function parse(run) {
  const E = run?.entries || [];
  const by = (ev) => E.filter((e) => e.event === ev);
  const t = { 1: {}, 2: {}, 3: {} };
  const viol = { 1: {}, 2: {}, 3: {} };
  for (const e of E) {
    const msg = e.payload?.message;
    if (e.event === "CONTRACTS") t[1][e.actor] = msg;
    if (e.event === "RANKING") t[2][e.actor] = msg;
    if (e.event === "COMMITMENT") t[3][e.actor] = msg;
    if (VIOLATION[e.event]) {
      const role = e.actor === "COORDINATOR" ? e.payload.role : e.actor;
      if (role && viol[e.turn]) (viol[e.turn][role] ||= []).push({ code: e.event, detail: e.payload.detail || e.payload.code });
    }
  }
  const feasible = Object.fromEntries(by("FEASIBLE_SET").map((e) => [e.turn, e.payload]));
  const selected = by("SELECTED")[0]?.payload;
  const done = by("DONE")[0]?.payload;
  const fallback = by("FALLBACK")[0]?.payload;
  const fbTurn = by("FALLBACK")[0]?.turn;
  const approvals = by("HUMAN_APPROVAL").map((e) => ({ ...e.payload, ts: e.ts }));
  return { t, viol, feasible, selected, done, fallback, fbTurn, approvals };
}
function lastStage(run) {
  const p = parse(run);
  return 4;
}

/* ------------------------------------------------------------------ render */
function renderAll(stage = S.stage) {
  renderProtocol(stage);
  renderDisruption();
  renderDecision(stage);
  renderGrid(stage);
  renderBoard(stage);
  renderReveal();
  if (!$("#view-log").hidden) renderLog();
}

function renderProtocol(stage) {
  const p = S.run ? parse(S.run) : null;
  const steps = [
    ["Setup", "flight and forecast"],
    ["Turn 1", "publish limits"],
    ["Turn 2", "rank plans"],
    ["Turn 3", "sign or reject"],
    ["Decision", p?.fallback ? "rulebook decided" : "plan agreed"],
    ["Approval", "humans sign off"],
  ];
  const approvedAll = p && p.approvals.length >= 3;
  const cur = !S.run ? (stage === 0.5 ? 1 : 0) : stage >= 4 ? (approvedAll ? 6 : 5) : stage;
  $("#protocol").innerHTML = steps.map(([a, b], i) => {
    let cls = i < cur ? "is-done" : i === cur ? "is-current" : "";
    if (p?.fallback && i === 4 && cur >= 4) cls += " is-failed";
    const ic = i < cur ? icon("circle-check") : "";
    return `${i ? '<li class="sep" aria-hidden="true"></li>' : ""}<li class="step ${cls}" ${i === cur ? 'aria-current="step"' : ""}>${ic}${a} <small>${b}</small></li>`;
  }).join("");
  if (stage === 0.5) $("#protocol .is-current small").textContent = "waiting for the three agents";
}

function renderDisruption() {
  const { public: p, forecast: f } = S.sc;
  const dis = p.disruption === "weather_at_destination" ? "Weather at destination" : "Late inbound aircraft";
  const nl = p.next_leg ? `${p.next_leg.flight_number} to ${p.next_leg.destination} at ${p.next_leg_departure}` : "none that day";
  $("#disruption").innerHTML = `
    <div class="panel-head"><div>
      <h2 id="disruption-h">The disruption</h2>
      <p>Real 2015 flight data. The agents get only what was knowable at decision time; the real delay stays sealed until you reveal it.</p>
    </div><span class="aside">${esc(p.date)}</span></div>
    <div class="flight-id">
      <span class="sign sign--location">${esc(p.flight_number)}</span>
      <span class="sign sign--quiet">Tail ${esc(p.tail)}</span>
      <span class="route">${esc(p.origin)} ${icon("arrow-right")} ${esc(p.destination)}</span>
    </div>
    <dl class="facts">
      <div><dt>Scheduled departure</dt><dd>${esc(p.scheduled_departure)}</dd></div>
      <div><dt>Scheduled arrival</dt><dd>${esc(p.scheduled_arrival)}</dd></div>
      <div><dt>Decision time</dt><dd>${esc(p.decision_time)} <small>(${p.decision_mode === "pre_departure" ? "before departure" : "in the air"})</small></dd></div>
      <div><dt>Problem</dt><dd>${dis}</dd></div>
      <div><dt>Same aircraft next</dt><dd>${esc(nl)}</dd></div>
      <div><dt>Alternate airport</dt><dd>${esc(p.alternate || "none")}</dd></div>
    </dl>
    <div class="forecast">
      <h3>How long could the ${p.disruption === "weather_at_destination" ? "weather" : "late aircraft"} delay be?</h3>
      <p>${esc(f.label)} (median ${f.P50.toFixed(0)} min, 9 in 10 under ${f.P90.toFixed(0)} min). The shaded band is the 15 min of holding fuel: anything longer than ground delay plus 15 min means a diversion.</p>
      ${histogram(f)}
    </div>`;
}

function histogram(f) {
  const W = 640, H = 150, pad = { l: 28, r: 8, t: 18, b: 22 };
  const step = 15, maxX = 240;
  const bins = new Array(maxX / step + 1).fill(0);
  for (const x of f.sample) bins[Math.min(Math.floor(x / step), bins.length - 1)]++;
  const peak = Math.max(...bins, 1);
  const bw = (W - pad.l - pad.r) / bins.length;
  const y = (v) => H - pad.b - (v / peak) * (H - pad.t - pad.b);
  const xAt = (m) => pad.l + (Math.min(m, maxX + step) / step) * bw;
  let s = `<svg class="hist" viewBox="0 0 ${W} ${H}" role="img" aria-label="Histogram of past delays: median ${f.P50.toFixed(0)} minutes, 90th percentile ${f.P90.toFixed(0)} minutes">`;
  s += `<rect class="budget" x="${xAt(0)}" y="${pad.t}" width="${xAt(15) - xAt(0)}" height="${H - pad.t - pad.b}"/>`;
  bins.forEach((b, i) => {
    const x = pad.l + i * bw + 1;
    s += `<rect class="bar ${i * step >= 15 ? "over" : ""}" x="${x}" y="${y(b)}" width="${Math.max(bw - 2, 1)}" height="${H - pad.b - y(b)}"><title>${i * step}${i === bins.length - 1 ? "+" : `-${i * step + step}`} min: ${b} flights</title></rect>`;
  });
  for (let m = 0; m <= maxX; m += 60) s += `<text x="${xAt(m)}" y="${H - 6}" text-anchor="middle">${m}${m === maxX ? "+" : ""} min</text>`;
  for (const [k, lab] of [["P50", "median"], ["P90", "9 in 10"]]) {
    const x = xAt(f[k]);
    s += `<line class="mark" x1="${x}" x2="${x}" y1="${pad.t - 4}" y2="${H - pad.b}"/><text class="mark-label" x="${x + 4}" y="${pad.t - 6}">${lab.toUpperCase()} ${f[k].toFixed(0)}</text>`;
  }
  s += `<text x="${xAt(0) + 3}" y="${H - pad.b - 4}" style="font-size:10px">fuel</text>`;
  return s + "</svg>";
}

function renderDecision(stage) {
  const el = $("#decision");
  const head = `<div class="panel-head"><div><h2 id="decision-h">Decision</h2>
    <p>The recommended plan, or the rulebook's answer when the agents cannot agree safely. Humans approve it.</p></div></div>`;
  const o = opts();
  const mode = o.agents === "claude" ? `Claude agents (${esc(S.meta.model)})` : `Scripted agents <span class="tag tag--noai">no AI</span>`;
  if (!S.run || stage < 4) {
    const waiting = stage === 0.5 || (S.run && stage < 4);
    el.innerHTML = head + `<div class="empty">
      <strong>${waiting ? "Negotiation in progress" : "No decision yet"}</strong>
      <span>${waiting
        ? "The agents are exchanging signed messages. Each turn appears below as it completes."
        : `Press <b>Run negotiation</b> to start. Turn 1: each party publishes the limits it needs respected. Turn 2: each ranks the plans that pass every limit. Turn 3: each signs or rejects the chosen plan.`}</span>
      <span class="status-line">${icon("info")} Mode: ${mode}${o.pressure ? ` · <span class="sign sign--mandatory" style="font-size:12px;padding:3px 6px">Pressure test on</span>` : ""}</span>
    </div>`;
    return;
  }
  const p = parse(S.run);
  const fb = p.fallback, done = p.done;
  const plan = (done || fb).plan;
  const esc_ = (done ? done.escalations : fb.escalations) || [];
  const verified = S.run.verify;
  let body = "";
  if (done) {
    body += `<div class="status-line"><span class="sign sign--go">${icon("circle-check")} Agreed</span> All three organisations signed in 3 turns.</div>`;
  } else {
    body += `<div class="status-line"><span class="sign sign--mandatory">${icon("shield-alert")} No safe agreement</span> The deterministic rulebook decided (no AI).</div>`;
    body += `<div class="callout callout--red">${icon("triangle-alert")}<div><b>Why:</b> ${esc(humanReason(fb.reason))}${fb.explanation?.length ? `<br>Conflicting limits: ${fb.explanation.map(esc).join("; ")}` : ""}<br><small>Rule applied: ${esc(ruleText(fb.branch))}</small></div></div>`;
  }
  body += `<div class="direction-sign" role="status">${icon("arrow-right")}<div>
      <div class="pid">${esc(shortPlan(plan.plan_id))}</div>
      <div class="what">${esc(planText(plan.plan_id))}${plan.target_arrival_min != null ? `. Target arrival ${hhmm(plan.target_arrival_min)}` : ""}</div></div></div>`;
  if (esc_.length) body += esc_.map((x) => `<div class="callout callout--warn">${icon("triangle-alert")}<div><b>Needs a human:</b> ${esc(x)}</div></div>`).join("");
  const roles = [["controller", "Arrival controller", "ATC organisation"], ["duty_manager", "Airline duty manager", "Airline operations control"], ["ramp_lead", "Ramp lead", "Ground handler"]];
  body += `<div><div class="subhead">Human approval</div><div class="approvals">${roles.map(([id, name, org]) => {
    const a = p.approvals.find((x) => x.role === id);
    return `<div class="approval"><span class="who">${name}<small>${org}</small></span>${a
      ? `<span class="approved">${icon("user-check")} Approved ${new Date(a.ts).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}</span>`
      : `<button class="btn btn--secondary btn--small" data-approve="${id}" type="button">${icon("file-check-2")} Approve as ${name.toLowerCase()}</button>`}</div>`;
  }).join("")}</div></div>`;
  body += `<div class="decision-foot">
    <button class="verified ${verified.ok ? "" : "bad"}" type="button" data-goto-log>${icon(verified.ok ? "shield-check" : "shield-alert")} ${esc(verified.ok ? verified.message.replace("Log verified", "Signed log verified") : verified.message)}</button>
    <button class="btn btn--primary btn--small" type="button" id="reveal-btn">${icon(S.revealed ? "eye-off" : "eye")} ${S.revealed ? "Hide 2015 outcome" : "Reveal what happened in 2015"}</button>
  </div>
  <div class="status-line" style="font-size:12.5px">${icon("info")} ${S.run.meta.agents === "claude" ? `Claude agents, ${S.run.meta.llm_calls} model calls, ${S.run.meta.wall_clock_s}s` : `Scripted agents (no AI), ${S.run.meta.llm_calls} agent calls`}${S.run.meta.pressure ? " · pressure test" : ""}</div>`;
  el.innerHTML = head + body;
  el.querySelectorAll("[data-approve]").forEach((b) => b.addEventListener("click", () => approve(b.dataset.approve, b)));
  el.querySelector("[data-goto-log]").addEventListener("click", () => S.showTab("tab-log"));
  $("#reveal-btn").addEventListener("click", toggleReveal);
}

function humanReason(r = "") {
  if (r.startsWith("MISSING_AGENT")) return `An agent did not deliver a valid turn 1 message (${r.split(": ")[1] || ""}).`;
  if (r.startsWith("NO_SAFE_OPTION")) return "No plan satisfies every published limit.";
  if (r.startsWith("INVALID_TURN2")) return `A turn 2 message was voided (${r.split(": ")[1]}).`;
  if (r.startsWith("NO_CONSENSUS")) return `Not all three signed the selected plan (${r.split(": ")[1]}).`;
  return r;
}
function ruleText(b = "") {
  return {
    R1_MIN_DELAY_MEETS_RISK: "smallest ground delay with diversion risk at or below 10%",
    R1_LARGEST_DELAY_RISK_NOT_MET: "no plan meets the 10% diversion risk target, so the largest allowed ground delay",
    R2_DIVERT: "no plan passes every limit, so divert to the alternate (duty manager approves)",
    R2_NO_ALTERNATE_HOLD: "no safe option and no alternate: hold at gate G1, human decision required",
  }[b] || b;
}

async function approve(role, btn) {
  btn.disabled = true;
  try {
    S.run = await api(`/api/run/${encodeURIComponent(S.run.run_id)}/approve`, { method: "POST", body: JSON.stringify({ role, scenario_id: S.sc.public.scenario_id }) });
    renderAll();
  } catch (e) { btn.disabled = false; toast(esc(e.message)); }
}

/* ------------------------------------------------------------------ turns grid */
function renderGrid(stage) {
  const { public: pub, mandates, private: priv } = S.sc;
  const p = S.run ? parse(S.run) : null;
  const pending = (t) => !S.run || stage < t;
  let h = `<div class="colhead rowhead" style="background:var(--surface-2)"></div>`;
  for (const r of ROLES) {
    const m = mandates[r.id];
    h += `<div class="colhead">
      <div class="who-head">${icon(r.icon)} ${r.name}</div>
      <div class="org">${esc(m.organisation)} · acts for the ${r.human.toLowerCase()}</div>
      <div class="mandate"><span><b>Can decide:</b> ${m.may_set.map((f) => FIELD[f] || f).join(", ")}</span>
      <span class="no"><b>Cannot:</b> ${m.may_not.map((f) => FIELD[f] || f).join(", ")}</span></div>
      <details class="private"><summary>${icon("chevron-down", "chev")} Private state: only ${r.name} sees it <span class="tag tag--synthetic">synthetic</span></summary>
      <dl>${priv[r.id].map(([k, v]) => `<dt>${esc(k)}</dt><dd>${esc(v)}</dd>`).join("")}</dl></details>
    </div>`;
  }
  h += `<div class="colhead coord"><div class="who-head">${icon("scale")} Coordinator</div>
    <div class="org">Plain code, no AI, no private data</div>
    <div class="mandate"><span>Checks every message against every published limit and mandate. Picks the plan with the best worst-case rank. Never more than 3 turns.</span></div></div>`;

  const rows = [
    [1, "Turn 1", "Publish limits each party needs respected"],
    [2, "Turn 2", "Rank up to 5 plans from the safe overlap"],
    [3, "Turn 3", "Sign or reject the selected plan"],
  ];
  for (const [t, title, sub] of rows) {
    h += `<div class="rowhead"><b>${title}</b><span>${sub}</span></div>`;
    for (const r of ROLES) h += cell(t, r, p, pending(t), pub, stage);
    h += coordCell(t, p, pending(t), stage);
  }
  $("#neg-grid").innerHTML = h;
}

function cell(t, r, p, pending, pub, stage) {
  if (pending) return `<div class="cell is-pending">${S.stage === 0.5 && t === 1 ? "Waiting for message" : "Not reached yet"}</div>`;
  const msg = p.t[t][r.id];
  const v = (p.viol[t][r.id] || []).map((x) => `<div class="violation" role="alert"><b>${icon("shield-alert")} ${VIOLATION[x.code]}</b>${esc(plainDetail(x.detail))}</div>`).join("");
  const enter = stage === t ? " is-entering" : "";
  if (!msg && !v) {
    const stopped = p.fallback && (p.fbTurn || 3) < t;
    const cut = p.fallback && p.fbTurn === t;
    return `<div class="cell is-pending">${stopped ? "Skipped: the rulebook decided after an earlier turn"
      : cut ? "Not processed: the coordinator stopped this turn at the voided message" : "No message"}</div>`;
  }
  let body = "";
  if (msg && t === 1) {
    body += `<ul class="limits">${msg.contracts.map((c) => { const [a, b] = contractText(c, pub); return `<li><span>${esc(a)}</span>${b ? `<small>${esc(b)}</small>` : ""}</li>`; }).join("")}</ul>`;
    const lims = Object.entries(msg.stated_limits || {});
    if (lims.length) body += `<div class="chips">${lims.map(([k, val]) => `<span class="tag">${LIMIT_TEXT[k] || k} ${val} min</span>`).join("")}</div>`;
    if (msg.notes_for_humans) body += `<p class="quote">${esc(msg.notes_for_humans)}</p>`;
  }
  if (msg && t === 2) {
    const chosen = p.selected?.plan?.plan_id;
    body += `<ol class="ranking">${msg.ranking.map((pid) => `<li><span class="${pid === chosen ? "chosen" : ""}"><span class="pid">${esc(shortPlan(pid))}</span></span></li>`).join("")}</ol>`;
    if (msg.reasons?.length) body += `<div class="chips">${msg.reasons.map((x) => `<span class="tag">${esc(REASON[x] || x)}</span>`).join("")}</div>`;
    if (msg.extra_contracts?.length) body += `<ul class="limits">${msg.extra_contracts.map((c) => `<li><span>Extra: ${esc(contractText(c, pub)[0])}</span></li>`).join("")}</ul>`;
    if (msg.justification) body += `<p class="quote">${esc(msg.justification)}</p>`;
  }
  if (msg && t === 3) {
    body += msg.accept
      ? `<div class="commit ok">${icon("circle-check")} Signed ${esc(shortPlan(msg.plan_id))}</div><span class="quote" style="font-style:normal">Takes responsibility for: ${msg.owned_fields.map((f) => FIELD[f] || f).join(", ") || "nothing"}</span>`
      : `<div class="commit no">${icon("circle-x")} Rejected</div><span>Reason: ${esc(REASON[msg.reason_if_reject] || msg.reason_if_reject)}</span>`;
  }
  return `<div class="cell${enter}">${body}${v}</div>`;
}

function plainDetail(d = "") {
  return d.replace("reserve_min", "fuel reserve").replace("hold_limit_min", "holding limit").replace("max_ground_delay_min", "max ground delay")
    .replace(/looser than workbook value/, "is looser than the workbook value").replace(/looser than turn 1 value/, "is looser than its own turn 1 value");
}

function coordCell(t, p, pending, stage) {
  if (pending) return `<div class="cell is-pending">${t === 1 ? `${S.sc.plans.length} possible plans` : ""}</div>`;
  const enter = stage === t ? " is-entering" : "";
  if (p.fallback && p.fbTurn === t) {
    return `<div class="cell${enter}"><span class="sign sign--mandatory">${icon("shield-alert")} Stop</span><span>${esc(humanReason(p.fallback.reason))}</span><span>Handed to the rulebook.</span></div>`;
  }
  if (t === 1) {
    const f = p.feasible[1];
    if (!f) return `<div class="cell is-pending">Stopped</div>`;
    return `<div class="cell${enter}"><div class="coord-num">${S.sc.plans.length} ${icon("arrow-right")} ${f.size} <small>plans pass every limit</small></div>
      <span>Plans ruled out are red on the plan board below.</span></div>`;
  }
  if (t === 2) {
    const sel = p.selected;
    if (!sel) return `<div class="cell is-pending">Stopped</div>`;
    const all = Object.entries(sel.borda).map(([pid, sc]) => ({ pid, sc, min: Math.min(...Object.values(sc)), sum: Object.values(sc).reduce((a, b) => a + b, 0) }));
    const win = all.find((r) => r.pid === sel.plan.plan_id);
    const rows = [win, ...all.filter((r) => r !== win).sort((a, b) => b.min - a.min || b.sum - a.sum)].slice(0, 5);
    const tie = win && win.min === 0;
    return `<div class="cell${enter}"><span>Selected: <span class="sign sign--direction" style="font-size:13px;padding:4px 7px">${esc(shortPlan(sel.plan.plan_id))}</span></span>
      <table class="borda"><thead><tr><th>Plan</th><th>ATC</th><th>Airl.</th><th>Grnd</th><th>Worst</th></tr></thead><tbody>
      ${rows.map((r) => `<tr class="${r.pid === sel.plan.plan_id ? "win" : ""}"><td>${esc(shortPlan(r.pid))}</td>${["ATC", "AIRLINE", "GROUND"].map((k) => `<td>${(r.sc[k] ?? 0).toFixed(2)}</td>`).join("")}<td>${r.min.toFixed(2)}</td></tr>`).join("")}
      </tbody></table><small style="color:var(--ink-3)">Rank score: 1.00 = an agent's first choice, 0 = not in its top 5. The plan with the best worst score wins.${tie ? " No plan was in all three top 5s, so the tie went to the lowest diversion risk, then the lowest expected delay." : ""}</small></div>`;
  }
  if (p.done) return `<div class="cell${enter}"><span class="sign sign--go">${icon("circle-check")} 3 of 3 signed</span><span>Recommended plan issued. Signatures checked against each organisation's key.</span></div>`;
  return `<div class="cell is-pending">Stopped</div>`;
}

/* ------------------------------------------------------------------ plan board */
function renderBoard(stage) {
  const plans = S.sc.plans;
  const p = S.run && stage >= 1 ? parse(S.run) : null;
  const blocked = (S.run && stage >= 1) ? S.run.blocked_by : {};
  const delays = [...new Set(plans.filter((x) => x.strategy !== "DIVERT").map((x) => x.ground_delay_min))].sort((a, b) => a - b);
  const gates = [...new Set(plans.filter((x) => x.gate).map((x) => x.gate))];
  const byKey = Object.fromEntries(plans.map((x) => [x.strategy === "DIVERT" ? "DIV" : `${x.gate}|${x.ground_delay_min}`, x]));
  const broadcast = new Set(stage >= 2 && p?.feasible[2] ? p.feasible[2].plan_ids : stage >= 1 && p?.feasible[1] ? p.feasible[1].plan_ids : []);
  const ranked = new Set(stage >= 2 && p ? Object.values(p.t[2]).flatMap((m) => m.ranking) : []);
  const chosen = stage >= 4 && p ? (p.done || p.fallback)?.plan?.plan_id : stage >= 2 ? p?.selected?.plan?.plan_id : null;
  const state = (pid) => {
    const hits = (blocked[pid] || []).filter((h) => S.filters[h.by] && h.turn <= Math.max(stage, 1));
    const cls = [];
    if (pid === chosen) cls.push("chosen");
    else if (hits.length) cls.push("blocked", hits.every((h) => h.turn === 2) ? "t2" : "");
    else if (broadcast.has(pid)) cls.push("safe");
    if (ranked.has(pid) && pid !== chosen) cls.push("ranked");
    return { cls: cls.join(" "), hits };
  };
  let h = `<div class="board-row axis"><span class="lab">Gate</span>${delays.map((d) => `<span class="ax">${d === 0 ? "Hold" : `+${d}`}</span>`).join("")}</div>`;
  for (const g of gates) {
    h += `<div class="board-row" role="row"><span class="lab">${g === "G1" ? "G1 (own)" : g}</span>`;
    for (const d of delays) {
      const pl = byKey[`${g}|${d}`];
      const st = state(pl.plan_id);
      h += `<button type="button" class="pc ${st.cls}" data-pid="${pl.plan_id}" aria-label="${esc(planText(pl.plan_id))}">${st.cls.includes("chosen") ? icon("arrow-right") : ""}</button>`;
    }
    h += `</div>`;
  }
  const div = byKey.DIV;
  if (div) {
    const st = state(div.plan_id);
    h += `<div class="board-row divert"><span class="lab">Divert</span><button type="button" class="pc ${st.cls}" data-pid="${div.plan_id}">${esc(planText(div.plan_id))}</button></div>`;
  }
  $("#board").innerHTML = h;
  const nBlocked = plans.filter((x) => (blocked[x.plan_id] || []).length).length;
  $("#board-count").textContent = S.run && stage >= 1 ? `${plans.length} plans · ${nBlocked} ruled out · ${plans.length - nBlocked} pass every limit` : `${plans.length} plans`;
  $("#board-tools").innerHTML = `<span>Show limits published by:</span>${ROLES.map((r) =>
    `<label class="check"><input type="checkbox" data-filter="${r.id}" ${S.filters[r.id] ? "checked" : ""}> ${icon(r.icon)} ${r.name}</label>`).join("")}
    <span style="color:var(--ink-3)">Untick a party to see the plans only its limits rule out. Hover a square for details.</span>`;
  document.querySelectorAll("[data-filter]").forEach((cb) => cb.addEventListener("change", () => { S.filters[cb.dataset.filter] = cb.checked; renderBoard(S.stage); }));
}

function bindTip() {
  const tip = $("#tip");
  const show = (el, x, y) => {
    const pid = el.dataset.pid;
    const hits = (S.run?.blocked_by?.[pid] || []);
    const names = { ATC: "ATC", AIRLINE: "Airline", GROUND: "Ground" };
    const typeText = { available_arrival_minutes: "no arrival slot", max_ground_delay: "crew duty", gate_window_free: "gate occupied", gate_change_notice: "gate change notice", forbid_strategy: "strategy forbidden", latest_arrival: "arrives too late" };
    tip.innerHTML = `<b>${esc(shortPlan(pid))}</b>${esc(planText(pid))}<br>${S.run ? (hits.length
      ? `Ruled out by ${hits.map((h) => `${names[h.by]} (${typeText[h.type] || h.type}, turn ${h.turn})`).join(", ")}`
      : "Passes every published limit") : "Run the negotiation to see which party rules it out."}`;
    tip.style.left = `${Math.min(x + 14, innerWidth - 320)}px`;
    tip.style.top = `${y + 14}px`;
    tip.classList.add("show");
  };
  document.addEventListener("pointerover", (e) => { const el = e.target.closest(".pc"); if (el) show(el, e.clientX, e.clientY); });
  document.addEventListener("pointermove", (e) => { if (tip.classList.contains("show")) { tip.style.left = `${Math.min(e.clientX + 14, innerWidth - 320)}px`; tip.style.top = `${e.clientY + 14}px`; } });
  document.addEventListener("pointerout", (e) => { if (e.target.closest(".pc")) tip.classList.remove("show"); });
  document.addEventListener("focusin", (e) => { const el = e.target.closest(".pc"); if (el) { const r = el.getBoundingClientRect(); show(el, r.left, r.bottom); } });
  document.addEventListener("focusout", (e) => { if (e.target.closest(".pc")) tip.classList.remove("show"); });
}

/* ------------------------------------------------------------------ reveal */
async function toggleReveal() {
  if (S.revealed) { S.revealed = null; renderAll(); return; }
  try {
    S.revealed = await api(`/api/reveal/${encodeURIComponent(S.run.run_id)}?scenario_id=${encodeURIComponent(S.sc.public.scenario_id)}`);
    renderAll();
    $("#reveal").scrollIntoView({ behavior: reduced ? "auto" : "smooth", block: "start" });
  } catch (e) { toast(esc(e.message)); }
}

function renderReveal() {
  const el = $("#reveal");
  if (!S.revealed || !S.run) { el.hidden = true; return; }
  el.hidden = false;
  const R = S.revealed, rows = R.rows, a = R.actual;
  const what = R.disruption === "weather_at_destination" ? "weather delay" : "inbound lateness";
  const cols = [
    ["ours", "Our plan", `${shortPlan(R.plans.ours)}`],
    ["fallback_only", "Rulebook only", shortPlan(R.plans.fallback_only)],
    ["fcfs", "No coordination", "depart on time, hold, divert"],
  ];
  const line = (label, get, unit = " min", badIf) =>
    `<tr><td>${label}</td>${cols.map(([k]) => { const v = get(rows[k]); return `<td class="${k === "ours" ? "ours" : ""} ${badIf && badIf(rows[k]) ? "bad" : ""}">${v}</td>`; }).join("")}<td>${get(null)}</td></tr>`;
  el.innerHTML = `<div class="panel-head"><div><h2 id="reveal-h">What actually happened in 2015</h2>
    <p>The sealed outcome, opened only now. Model estimates replay each plan against the real ${what}; the last column is what was recorded in 2015.</p></div></div>
    <p class="reveal-lede">The real ${what} was <b>${fmt(R.true_delay_min, " min")}</b>. The flight arrived <b>${fmt(a.arrival_delay_min, " min")}</b> late in 2015${a.next_leg_departure_delay_min != null ? `, and the same aircraft's next departure left <b>${fmt(a.next_leg_departure_delay_min, " min")}</b> late` : ""}.</p>
    <div class="scroll-x"><table class="compare">
      <thead><tr><th></th>${cols.map(([k, n, s]) => `<th class="${k === "ours" ? "ours" : ""}">${n}<small>${esc(s)}</small></th>`).join("")}<th>Recorded 2015<small>actual outcome</small></th></tr></thead>
      <tbody>
        ${line("Diverted", (r) => (r ? (r.diverted ? "Yes" : "No") : "No"), "", (r) => r.diverted)}
        ${line("Arrival delay", (r) => (r ? (r.diverted ? "diverted" : fmt(r.arrival_delay_min, " min")) : fmt(a.arrival_delay_min, " min")))}
        ${line("Holding in the air", (r) => (r ? fmt(r.holding_min, " min") : "n/a"))}
        ${line("Holding fuel burned", (r) => (r ? fmt(r.holding_fuel_kg, " kg") : "n/a"))}
        ${line("Next departure delay (same aircraft)", (r) => (r ? (r.diverted ? "aircraft unavailable" : fmt(r.next_leg_departure_delay_min, " min")) : fmt(a.next_leg_departure_delay_min, " min")))}
        ${line(`Missed connections <span class="tag tag--synthetic">synthetic</span>`, (r) => (r ? `${r.missed_connection_pax_synthetic} passengers` : "n/a"))}
        ${line(`Ramp crew overtime <span class="tag tag--synthetic">synthetic</span>`, (r) => (r ? fmt(r.ground_overtime_min_synthetic, " min") : "n/a"))}
      </tbody></table></div>
    <p class="status-line" style="margin-top:var(--s3);font-size:13px">${icon("info")} Model estimate vs recorded 2015 outcome. The model allows 15 min of holding before a diversion and makes one decision; the 2015 flight was held on the ground at its origin instead.</p>`;
}

/* ------------------------------------------------------------------ evaluation tab */
async function renderEval() {
  const el = $("#eval");
  if (el.dataset.done) return;
  const e = await api("/api/eval");
  if (!e.available) {
    el.innerHTML = `<article class="panel"><div class="empty"><strong>No evaluation yet</strong><span>Run <code>python -m dn.evaluate --agents scripted</code> (or <code>--agents claude</code>) and reload this tab.</span></div></article>`;
    return;
  }
  const T = Object.fromEntries(e.table.map((r) => [r.system.split(" (")[0], r]));
  const ours = e.table[0], fb = e.table.find((r) => r.system.startsWith("Fallback")), fcfs = e.table.find((r) => r.system.startsWith("FCFS"));
  const COLS = [
    ["diversions", "Diversions", "fewer is better"],
    ["arrival_delay_vs_2015_same_flights_min", "Arrival vs 2015", "min, same flights, negative = earlier"],
    ["next_leg_delay_vs_2015_same_flights_min", "Next departure vs 2015", "min, same flights"],
    ["mean_holding_min", "Holding", "mean min in the air"],
    ["total_holding_fuel_kg", "Holding fuel", "kg, all flights"],
    ["missed_connection_pax (synthetic)", "Missed connections", "passengers, synthetic"],
    ["ground_overtime_min (synthetic)", "Ramp overtime", "min, synthetic"],
    ["binding_violations", "Unsafe plans agreed", "must be 0"],
    ["fallback_rate", "Fallback rate", "share decided by rulebook"],
    ["max_turns", "Max turns", "limit 3"],
  ];
  const cellv = (r, k) => (r[k] == null ? "" : typeof r[k] === "number" ? (k === "fallback_rate" ? `${Math.round(r[k] * 100)}%` : Number.isInteger(r[k]) ? r[k] : r[k].toFixed(1)) : r[k]);
  const testText = {
    pressure: ["Pressure test", "Airline told the others agreed to a 25 min reserve"],
    agent_removal: ["Agent removal", "With any one agent missing, no plan is agreed"],
    mandate_violation: ["Mandate check", "ATC claims the gate decision and is rejected"],
    determinism: ["Rulebook determinism", "Same input, same output, twice"],
    leakage: ["No hindsight", "Sealed 2015 outcome never appears in a prompt"],
    convergence: ["Turn limit", "Every run ends within 3 turns"],
  };
  el.innerHTML = `
  <article class="panel"><div class="panel-head"><div><h2>Evaluation</h2>
    <p>${esc(e.scope)}. Agents: ${esc(e.agents)}. Every system faces the same flights; the real 2015 delay is used only to score.</p></div></div>
    <div class="headline-findings">
      <div class="finding"><b>${ours.diversions} vs ${fcfs?.diversions}</b><span>diversions: our agents vs no coordination, out of ${ours.n} flights</span></div>
      <div class="finding"><b>${fmt(ours["next_leg_delay_vs_2015_same_flights_min"], " min", 1)}</b><span>same aircraft's next departure vs 2015, on flights not diverted (rulebook alone: ${fmt(fb?.["next_leg_delay_vs_2015_same_flights_min"], " min", 1)})</span></div>
      <div class="finding"><b>${ours.binding_violations}</b><span>agreed plans that broke a published limit, across all runs</span></div>
    </div></article>
  <article class="panel"><div class="panel-head"><div><h2>Systems compared</h2><p>Hindsight agents are a cheating baseline: they are shown the real delay. They show how much a hindsight demo would flatter the result.</p></div></div>
    <div class="scroll-x"><table class="data"><thead><tr><th>System</th>${COLS.map(([, n, s]) => `<th>${n}<small>${s}</small></th>`).join("")}</tr></thead>
    <tbody>${e.table.map((r, i) => `<tr class="${i === 0 ? "ours" : r.system.startsWith("Hindsight") ? "cheat" : ""}"><td>${esc(r.system)}</td>${COLS.map(([k]) => `<td>${cellv(r, k)}</td>`).join("")}</tr>`).join("")}</tbody></table></div>
    <p class="status-line" style="margin-top:var(--s3);font-size:13px">${icon("info")} The 2015 comparison uses only the flights each system did not divert, so diverting the hardest cases cannot flatter a system.</p></article>
  <article class="panel"><div class="panel-head"><div><h2>Integrity tests</h2><p>Attempts to break the safety rules. A pass means the rule held in code, not that an agent behaved.</p></div></div>
    <div class="tests">${e.integrity.map((t) => { const [n, d] = testText[t.test] || [t.test, ""]; return `<div class="test"><div class="commit ${t.pass ? "ok" : "no"}">${icon(t.pass ? "circle-check" : "circle-x")} ${n}</div><p>${d}</p><p class="mono">${esc(Object.entries(t.detail).map(([k, v]) => `${k.replace(/_/g, " ")}: ${typeof v === "object" ? Object.entries(v).map(([a, b]) => `${a} ${b}`).join(", ") : v}`).join(" · "))}</p></div>`; }).join("")}</div></article>
  ${e.story.length ? `<article class="panel"><div class="panel-head"><div><h2>Cases to look at</h2><p>Pick these flights in the selector on the Negotiation tab.</p></div></div><ul>${e.story.map((s) => `<li>${esc(s)}</li>`).join("")}</ul></article>` : ""}`;
  el.dataset.done = "1";
}

/* ------------------------------------------------------------------ rules tab */
async function renderRules() {
  const el = $("#rules");
  if (el.dataset.done) return;
  const r = await api("/api/rules");
  el.innerHTML = `
  <article class="panel"><div class="panel-head"><div><h2>Rules of play</h2><p>From the challenge workbook, verbatim.</p></div></div>
    <table class="data left"><thead><tr>${r.rules_header.map((x) => `<th>${esc(x)}</th>`).join("")}</tr></thead>
    <tbody>${r.rules.map((row) => `<tr>${row.map((c) => `<td>${esc(c)}</td>`).join("")}</tr>`).join("")}</tbody></table></article>
  <article class="panel"><div class="panel-head"><div><h2>Our assumptions</h2><p>Every value we chose or changed, and why. Stated here because the rules require any changed limit to be shown.</p></div></div>
    <table class="data left"><thead><tr><th>Assumption</th><th>Value</th><th>Why</th></tr></thead>
    <tbody>${r.assumptions.map((row) => `<tr>${row.slice(0, 3).map((c) => `<td>${esc(c.replace(/\*\*/g, ""))}</td>`).join("")}</tr>`).join("")}</tbody></table></article>`;
  el.dataset.done = "1";
}

/* ------------------------------------------------------------------ log tab */
function summarise(e) {
  const m = e.payload?.message;
  switch (e.event) {
    case "MANDATE_ISSUED": return `Mandate signed: may set ${e.payload.may_set.join(", ")}`;
    case "SCENARIO_PUBLIC": return `Public facts for ${e.payload.flight_number} ${e.payload.origin} to ${e.payload.destination}`;
    case "FORECAST": return e.payload.label;
    case "CONTRACTS": return `${m.contracts.length} limits published, signed`;
    case "FEASIBLE_SET": return `${e.payload.size} plans pass every limit`;
    case "RANKING": return `Ranked ${m.ranking.join(", ")}`;
    case "SELECTED": return `Selected ${e.payload.plan.plan_id}`;
    case "COMMITMENT": return m.accept ? `Signed ${m.plan_id}` : `Rejected ${m.plan_id}`;
    case "DONE": return `Recommended ${e.payload.plan.plan_id}`;
    case "FALLBACK": return `Rulebook: ${e.payload.plan.plan_id} (${e.payload.reason})`;
    case "HUMAN_APPROVAL": return `${e.payload.name} approved ${e.payload.plan_id}`;
    default: return e.payload?.detail || e.payload?.code || "";
  }
}
function renderLog() {
  const el = $("#log");
  if (!S.run) {
    el.innerHTML = `<article class="panel"><div class="empty"><strong>No run loaded</strong><span>Run or replay a negotiation on the Negotiation tab. Its signed log appears here.</span></div></article>`;
    return;
  }
  const v = S.run.verify;
  el.innerHTML = `<article class="panel"><div class="panel-head"><div><h2>Consensus log</h2>
    <p>Append-only. Each entry carries the hash of the one before it, so editing any entry breaks the chain. Agent messages and mandates carry an HMAC signature from their organisation's key. Click a row to see the full entry.</p></div>
    <span class="aside">${esc(S.run.run_id)}</span></div>
    <div class="banner ${v.ok ? "ok" : "bad"}">${icon(v.ok ? "shield-check" : "shield-alert")} ${esc(v.ok ? `${v.message}: hash chain intact, every signature valid` : v.message)}</div>
    <div class="scroll-x" style="margin-top:var(--s3)"><table class="data left log"><thead><tr><th>#</th><th>Turn</th><th>From</th><th>Event</th><th>What happened</th><th>Hash</th></tr></thead><tbody>
    ${S.run.entries.map((e) => `<tr class="log-row" data-seq="${e.seq}" tabindex="0"><td>${e.seq}</td><td>${e.turn}</td><td>${esc(e.actor)}</td><td>${VIOLATION[e.event] ? `<span class="sign sign--mandatory" style="font-size:12px;padding:3px 6px">${e.event.replace(/_/g, " ")}</span>` : esc(e.event.replace(/_/g, " ").toLowerCase())}</td><td style="text-align:left">${esc(summarise(e))}</td><td class="mono">${e.hash.slice(0, 10)}</td></tr><tr hidden data-detail="${e.seq}"><td colspan="6"><pre class="json">${esc(JSON.stringify(e, null, 2))}</pre></td></tr>`).join("")}
    </tbody></table></div></article>`;
  el.querySelectorAll(".log-row").forEach((row) => {
    const toggle = () => { const d = el.querySelector(`[data-detail="${row.dataset.seq}"]`); d.hidden = !d.hidden; };
    row.addEventListener("click", toggle);
    row.addEventListener("keydown", (ev) => { if (ev.key === "Enter" || ev.key === " ") { ev.preventDefault(); toggle(); } });
  });
}

boot().catch((e) => toast(`<b>Could not load the dashboard.</b> ${esc(e.message)}. Is the server running?`));
