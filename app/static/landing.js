import { ICONS } from "./icons.js";

const $ = (s, r = document) => r.querySelector(s);
const $$ = (s, r = document) => [...r.querySelectorAll(s)];
const svg = (name) =>
  `<svg class="icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${ICONS[name] || ""}</svg>`;
$$("[data-icon]").forEach((el) => (el.outerHTML = svg(el.dataset.icon)));

/* ---------------------------------------------------------------- plan grid
   The real plan board from the Claude run on SkyWest 6262: rows are gates G1, S1, S2, S3;
   columns are ground delay 0 (hold) to 120 min in 5 min steps. x = ruled out by a published rule. */
const BOARD = [
  "x.x..x...x.x..xxx...xxxxx",
  "xxxxxxxxxxxx..xxx...x...x",
  "xxxxxxxx.x.x..xxx...x...x",
  "xxxxxxxxxxxxxxxxxxxxx...x",
];
const PICK = [1, 23]; // gate S1, 115 min
const grid = $("#options");
BOARD.forEach((row, r) => [...row].forEach((c, k) => {
  const d = document.createElement("i");
  d.className = "opt";
  d.dataset.x = c === "x" ? "1" : "0";
  d.dataset.pick = r === PICK[0] && k === PICK[1] ? "1" : "0";
  d.style.transitionDelay = `${(r * 25 + k) * 6}ms`;
  grid.append(d);
}));

/* ---------------------------------------------------------------- table states */
const T = $("#table");
const seats = ["airline", "atc", "ground"].map((s) => $(`.seat--${s}`, T));
const each = (sel, fn) => seats.forEach((s) => $$(sel, s).forEach(fn));
const toggle = (el, on, cls = "show") => el && el.classList.toggle(cls, on);

function setStep(n) {
  T.dataset.step = n;
  each(".secret", (e) => { toggle(e, n >= 2); toggle(e, n >= 3, "dim"); });
  each(".note", (e) => { toggle(e, n >= 3); toggle(e, n >= 5, "dim"); });
  each(".rank", (e) => { toggle(e, n >= 5); toggle(e, n >= 7, "dim"); });
  each(".stamp", (e) => toggle(e, n >= 6 && n !== 8));
  each(".approve", (e) => toggle(e, n >= 9));
  toggle($(".pressure", T), n === 7);
  toggle($(".phones", T), n === 1);
  toggle($(".options", T), n >= 4);
  toggle($(".count", T), n >= 4);
  toggle($(".plan", T), n >= 6 && n !== 8);
  toggle($(".rulebook", T), n === 8);
  toggle($(".flight", T), n >= 4, "small");
  $$(".opt", grid).forEach((o) => {
    o.className = "opt";
    if (n >= 4) o.classList.add(o.dataset.x === "1" ? "x" : "ok");
    if (n >= 6 && n !== 8 && o.dataset.pick === "1") o.className = "opt pick";
  });
}

const steps = $$(".step");
let current = -1;
const io = new IntersectionObserver((entries) => {
  // pick the step whose centre is nearest the viewport centre
  const mid = innerHeight / 2;
  let best = null, dist = Infinity;
  for (const s of steps) {
    const r = s.getBoundingClientRect();
    const d = Math.abs(r.top + r.height / 2 - mid);
    if (r.bottom > 0 && r.top < innerHeight && d < dist) { dist = d; best = s; }
  }
  if (!best) return;
  const n = Number(best.dataset.step);
  if (n !== current) {
    current = n;
    steps.forEach((s) => s.classList.toggle("is-active", s === best));
    setStep(n);
  }
}, { threshold: [0, 0.25, 0.5, 0.75, 1], rootMargin: "-20% 0px -20% 0px" });
steps.forEach((s) => io.observe(s));
setStep(0);
steps[0].classList.add("is-active");

/* ---------------------------------------------------------------- live results */
const fmt = (v, dp = 0) => (v == null ? "n/a" : Number(v).toFixed(dp));
async function results() {
  const box = $("#results-table");
  try {
    let e = await (await fetch("/api/eval?which=claude")).json();
    if (!e.available) throw new Error("no results");
    const row = (pre) => e.table.find((r) => r.system.startsWith(pre)) || {};
    const ours = row("Ours"), fb = row("Fallback"), none = row("FCFS");
    const pressure = (e.integrity || []).find((t) => t.test === "pressure");
    const tries = pressure?.detail?.runs, gave = pressure?.detail?.binding_concessions;
    const nl = ours["next_leg_delay_vs_2015_same_flights_min"];
    box.innerHTML = `<table>
      <thead><tr><th></th><th class="ours">With our assistants</th><th>Rulebook alone</th><th>No coordination</th></tr></thead>
      <tbody>
        <tr><td>Planes that had to land at another airport<small>out of ${ours.n} flights; in 2015 none did, because planes waited on the ground instead</small></td><td class="ours">${ours.diversions}</td><td>${fb.diversions ?? ""}</td><td>${none.diversions ?? ""}</td></tr>
        <tr><td>The same plane's next flight, compared with 2015<small>minutes, on the flights that did not divert; minus means earlier than what really happened</small></td><td class="ours">${fmt(nl, 0)} min</td><td>${fmt(fb["next_leg_delay_vs_2015_same_flights_min"], 0)} min</td><td>${fmt(none["next_leg_delay_vs_2015_same_flights_min"], 0)} min</td></tr>
        <tr><td>Agreed plans that broke a safety rule<small>across every test run</small></td><td class="ours">${ours.binding_violations ?? 0}</td><td>n/a</td><td>n/a</td></tr>
        ${tries ? `<tr><td>Times pressure made an assistant give up a safety rule<small>out of ${tries} pressure tests</small></td><td class="ours">${gave}</td><td>n/a</td><td>n/a</td></tr>` : ""}
      </tbody></table>
      <p class="fine">${e.agents.startsWith("Claude") ? "Results from Claude assistants" : "Results from scripted stand-in assistants (no AI)"}, ${e.scope}.</p>`;
    const live = $('[data-live="pressure"]');
    if (live && tries) live.textContent = `In ${tries} pressure tests, the assistants gave up a safety rule ${gave} times.`;
  } catch {
    box.innerHTML = `<p class="muted">Test results are shown on the live demo's Evaluation tab.</p>`;
  }
}
results();
