---
name: Bifrost
description: Airside signage as the grammar of a three-party negotiation over one disrupted flight.
colors:
  ground: "#dfe2e4"
  surface: "#f7f8f8"
  surface-2: "#edf0f1"
  ink: "#141517"
  ink-2: "#44474c"
  ink-3: "#6a6d72"
  rule: "#c6cbce"
  rule-strong: "#858c91"
  sign-black: "#141414"
  sign-yellow: "#f5c400"
  sign-yellow-hover: "#ffd21a"
  sign-red: "#c4122f"
  sign-white: "#ffffff"
  go: "#1d6b3a"
  go-tint: "#e3efe6"
  red-tint: "#f7e3e5"
  red-tint-ink: "#7d0b1d"
  yellow-tint: "#fbf0c2"
  yellow-tint-ink: "#5c4400"
  slab: "#24272b"
  slab-ink: "#e9ecee"
  slab-ink-2: "#b4bbc0"
typography:
  display:
    fontFamily: "Barlow Condensed, Arial Narrow, sans-serif"
    fontSize: "34px"
    fontWeight: 700
    lineHeight: 1
    letterSpacing: "0.03em"
  headline:
    fontFamily: "Barlow Condensed, Arial Narrow, sans-serif"
    fontSize: "30px"
    fontWeight: 600
    lineHeight: 1
    letterSpacing: "0.01em"
  title:
    fontFamily: "Barlow Condensed, Arial Narrow, sans-serif"
    fontSize: "21px"
    fontWeight: 700
    lineHeight: 1.1
    letterSpacing: "0.02em"
  sign:
    fontFamily: "Barlow Condensed, Arial Narrow, sans-serif"
    fontSize: "15px"
    fontWeight: 700
    lineHeight: 1
    letterSpacing: "0.04em"
  label:
    fontFamily: "Barlow Condensed, Arial Narrow, sans-serif"
    fontSize: "12px"
    fontWeight: 600
    lineHeight: 1
    letterSpacing: "0.06em"
  body:
    fontFamily: "Barlow, system-ui, sans-serif"
    fontSize: "15px"
    fontWeight: 400
    lineHeight: 1.5
    fontFeature: "\"tnum\""
  body-small:
    fontFamily: "Barlow, system-ui, sans-serif"
    fontSize: "13px"
    fontWeight: 400
    lineHeight: 1.5
  persuade-display:
    fontFamily: "Barlow Condensed, Arial Narrow, sans-serif"
    fontSize: "clamp(44px, 5.2vw, 76px)"
    fontWeight: 600
    lineHeight: 0.98
    letterSpacing: "-0.005em"
  persuade-section:
    fontFamily: "Barlow Condensed, Arial Narrow, sans-serif"
    fontSize: "clamp(36px, 4vw, 56px)"
    fontWeight: 600
    lineHeight: 1.02
  persuade-step:
    fontFamily: "Barlow Condensed, Arial Narrow, sans-serif"
    fontSize: "clamp(32px, 3.2vw, 46px)"
    fontWeight: 600
    lineHeight: 1.05
    letterSpacing: "0.005em"
  persuade-body:
    fontFamily: "Barlow, system-ui, sans-serif"
    fontSize: "18px"
    fontWeight: 400
    lineHeight: 1.6
    fontFeature: "\"tnum\""
rounded:
  cell: "1px"
  sign: "2px"
spacing:
  s1: "4px"
  s2: "8px"
  s3: "12px"
  s4: "16px"
  s5: "24px"
  s6: "32px"
  s7: "48px"
components:
  sign-location:
    backgroundColor: "{colors.sign-black}"
    textColor: "{colors.sign-yellow}"
    typography: "{typography.sign}"
    rounded: "{rounded.sign}"
    padding: "7px 10px"
  sign-direction:
    backgroundColor: "{colors.sign-yellow}"
    textColor: "{colors.sign-black}"
    typography: "{typography.sign}"
    rounded: "{rounded.sign}"
    padding: "7px 10px"
  sign-mandatory:
    backgroundColor: "{colors.sign-red}"
    textColor: "{colors.sign-white}"
    typography: "{typography.sign}"
    rounded: "{rounded.sign}"
    padding: "7px 10px"
  sign-go:
    backgroundColor: "{colors.go}"
    textColor: "{colors.sign-white}"
    typography: "{typography.sign}"
    rounded: "{rounded.sign}"
    padding: "7px 10px"
  button-primary:
    backgroundColor: "{colors.sign-yellow}"
    textColor: "{colors.sign-black}"
    rounded: "{rounded.sign}"
    padding: "10px 16px"
  button-primary-hover:
    backgroundColor: "{colors.sign-yellow-hover}"
  button-secondary:
    backgroundColor: "{colors.sign-white}"
    textColor: "{colors.ink}"
    rounded: "{rounded.sign}"
    padding: "10px 16px"
  tag-synthetic:
    backgroundColor: "{colors.yellow-tint}"
    textColor: "{colors.yellow-tint-ink}"
    typography: "{typography.label}"
    rounded: "{rounded.sign}"
    padding: "4px 6px"
  panel:
    backgroundColor: "{colors.surface}"
    rounded: "{rounded.sign}"
    padding: "16px 24px 24px"
  topbar:
    backgroundColor: "{colors.sign-black}"
    textColor: "{colors.sign-white}"
    height: "56px"
  select:
    backgroundColor: "{colors.sign-white}"
    textColor: "{colors.ink}"
    rounded: "{rounded.sign}"
    padding: "8px 34px 8px 10px"
  plan-cell:
    backgroundColor: "{colors.sign-white}"
    rounded: "{rounded.cell}"
    height: "34px"
  plan-cell-blocked:
    backgroundColor: "{colors.sign-red}"
    textColor: "{colors.sign-white}"
  plan-cell-chosen:
    backgroundColor: "{colors.sign-yellow}"
    textColor: "{colors.sign-black}"
  button-cta:
    backgroundColor: "{colors.sign-yellow}"
    textColor: "{colors.sign-black}"
    rounded: "{rounded.sign}"
    padding: "15px 20px"
  button-cta-hover:
    backgroundColor: "{colors.sign-yellow-hover}"
  button-cta-big:
    backgroundColor: "{colors.sign-yellow}"
    textColor: "{colors.sign-black}"
    rounded: "{rounded.sign}"
    padding: "20px 28px"
  button-cta-small:
    backgroundColor: "{colors.sign-yellow}"
    textColor: "{colors.sign-black}"
    rounded: "{rounded.sign}"
    padding: "9px 12px"
  table-slab:
    backgroundColor: "{colors.slab}"
    textColor: "{colors.slab-ink}"
    rounded: "{rounded.sign}"
    padding: "64px 24px 26px"
  table-seat:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.ink}"
    rounded: "{rounded.sign}"
    padding: "12px"
  table-option-struck:
    backgroundColor: "{colors.sign-red}"
    rounded: "{rounded.cell}"
  table-option-safe:
    backgroundColor: "{colors.slab-ink}"
    rounded: "{rounded.cell}"
  table-option-chosen:
    backgroundColor: "{colors.sign-yellow}"
    rounded: "{rounded.cell}"
---

# Design System: Bifrost

## Overview

**Creative North Star: "The Airside Sign Line"**

The interface reads like the signage an aircraft taxis past: a cool concrete ground, and on it a small set of panels whose colour tells you, before you read a word, what kind of statement they make. Black panels with yellow type say where you are. Yellow panels with black type and an arrow say which way to go. Red panels with white type say stop: a hard limit or a rejection. Everything else is plain, quiet, and ruled with 1px lines.

Density is high but legible at laptop distance. The condensed sign face carries every label, identifier, heading and button; the plain Barlow body carries explanation, always in sentence case. Numbers are tabular everywhere so turns, minutes and scores line up across columns. Corners are square (2px), so panels feel fabricated rather than soft.

The world refuses the generic card dashboard where every box weighs the same. Weight comes from sign colour, not from size or decoration, and the most important object on screen is the one yellow direction sign.

**Key Characteristics:**
- Cool concrete ground (ground) with near-white surfaces and 1px cool-grey rules.
- Three sign colours, each with one job: black for location, yellow for direction, red for mandatory.
- A fourth, quieter signal, signal green (go), only for signed and verified states.
- Barlow Condensed uppercase for panels and labels, Barlow for prose, tabular numerals throughout.
- Square 2px corners; plan-board cells at 1px.
- Motion only to advance the story: turns reveal in sequence while the location sign moves.
- Explainer (Persuade) surfaces scale the same signs up and add one dark slab, the meeting table, where the story advances step by step.

## Colors

A neutral concrete field with three saturated signal colours that never trade jobs.

### Primary
- **Direction Yellow** (sign-yellow): the recommended plan, the chosen plan-board cell, the primary action (Run, Approve), the active tab underline and the focus halo. If it is yellow, it points the way forward. Hover lifts to **Lit Yellow** (sign-yellow-hover).
- **Sign Black** (sign-black): the location sign (current protocol step, flight and plan identifiers, brand mark), the top bar, the tooltip, and the rulebook fallback sign. Always paired with yellow type or a yellow keyline when it marks location.

### Secondary
- **Mandatory Red** (sign-red): hard limits (the square bullet in each limit list), rejected commitments, coordinator violations, and plan-board cells struck out by a party's limit. White type on it, always.

### Tertiary
- **Signal Green** (go): signed commitments, completed protocol steps, approvals, verified log. Used as text, a 2px inset keyline on shortlisted cells, or a solid sign for the final "3 of 3 signed".

### Neutral
- **Apron Concrete** (ground): the page background.
- **Painted Surface** (surface): panels and the control bar.
- **Shaded Surface** (surface-2): column and row heads, info callouts, test cards, code blocks.
- **Ink** (ink), **Ink Mid** (ink-2), **Ink Quiet** (ink-3): body text, secondary prose, labels and captions.
- **Rule** (rule) for every 1px divider and grid line; **Rule Strong** (rule-strong) for input borders, the protocol separators and table header underlines.
- **Tints** (yellow-tint, red-tint, go-tint) with their deep inks (yellow-tint-ink, red-tint-ink): row highlights for "ours", warnings, the synthetic tag, and banners. Tints never stand in for the solid sign.
- **Tarmac Slab** (slab) with **Slab Ink** (slab-ink) and **Slab Ink Mid** (slab-ink-2): the dark top of the meeting table on explainer surfaces, its primary text and its secondary text (dates, counts). Safe options on the slab use Slab Ink; options not yet judged sit in a mid tarmac grey between slab and ink.

### Named Rules
**The One Job Rule.** Each sign colour has exactly one meaning: black-and-yellow is location, yellow is direction, red is mandatory, green is signed. Never use red for emphasis, yellow for decoration, or green for "nice".

**The One Yellow Sign Rule.** At most one solid yellow direction sign carries the recommendation on a screen; the primary button and the chosen plan cell repeat the same plan, never a competing one.

**The Not Only Colour Rule.** Every signal colour travels with text or an icon (party code in a blocked cell, "Signed", "Rejected", arrow on direction).

**The Painted Slab Rule.** The slab is a table top, not a dark theme: it always carries its painted 2px yellow keyline set 10px in from the edge, and the sign colours keep their usual jobs on it (red struck out, yellow chosen, location sign for the round).

## Typography

**Display Font:** Barlow Condensed (with Arial Narrow, sans-serif), weights 500 to 700
**Body Font:** Barlow (with system-ui, sans-serif), weights 400 to 600 and 400 italic
**Label/Mono Font:** Barlow Condensed for labels; the platform monospace stack only for raw log JSON and hashes.

**Character:** A sign-shop face for anything you would paint on a panel, and a calm humanist sans for anything you would read as a sentence.

### Hierarchy
- **Display** (700, 34px, 1): the plan identifier on the direction sign.
- **Headline** (600, 30px, 1): the route line (origin, arrow, destination).
- **Title** (700, 21px, 1.1, uppercase): panel headings. Column heads (18px) and row heads (17px) sit just below.
- **Sign** (700, 14 to 16px, 1, 0.04 to 0.05em, uppercase): sign panels, buttons, tabs, protocol steps, commitments.
- **Label** (600, 11 to 13px, 0.06 to 0.08em, uppercase): field labels, fact terms, table heads, subheads, tags.
- **Body** (400, 15px, 1.5): prose and values, max 72 to 80ch. Small body (12.5 to 14px) for captions and cell content.

### Persuade scale (explainer surfaces)
The same two faces, sized for reading at a distance by people new to the subject.
- **Persuade Display** (600, clamp(44px, 5.2vw, 76px), 0.98, -0.005em): the one hook headline in the first viewport.
- **Persuade Section** (600, clamp(36px, 4vw, 56px), 1.02, max 20 to 22ch): headings of full-width bands and the closing statement.
- **Persuade Step** (600, clamp(32px, 3.2vw, 46px), 1.05): the heading of each scroll step beside the meeting table.
- **Persuade Body** (400, 18px, 1.6): all explainer prose, max 34em in steps. Ledes run 18 to 21px (clamp(18px, 1.35vw, 21px)) or 20px in bands; list items 19px; fine print 15px in ink-3.
- Signs and buttons keep the sign face but grow: bar links 16px, CTA 19px (24px big, 15px small), result table heads 15px, and the "ours" result figure 24px condensed 700.

Persuade headings are short sentence-case display lines in the condensed face, never uppercase; paragraphs stay in Barlow.

### Named Rules
**The Painted Panel Rule.** Uppercase condensed type is for things a sign would say (names, IDs, states, actions). Sentences are never uppercase and never condensed.

**The Tabular Rule.** `font-variant-numeric: tabular-nums` is set on the body and inherited everywhere.

## Layout

Single centred column, max 1480px, padded 16px top and 24px sides (12px on phones). The top bar is a sticky 56px black strip: brand left, tabs centred, key state right. Below it, in order: control bar, sign legend, protocol strip, a two-column overview (disruption 1.35fr, decision min 380px), the plan board, the negotiation grid, and the reveal.

The negotiation grid is the spatial model of the product: a 148px row-head column for turns, three equal party columns and a slightly narrower coordinator column, every cell divided by 1px rules so private state stays visibly inside its own column. The plan board is a 92px label column plus 25 delay columns of at least 30px with 3px gutters.

Spacing follows a 4px-based scale (s1 to s7); 16px separates major panels, 12px separates related items. Breakpoints: at 1180px the overview stacks and the negotiation grid scrolls horizontally with 220px columns; at 760px the top bar stacks, tabs scroll, facts go to two columns and the page clips horizontal overflow.

Explainer surfaces use a 64px sticky black bar with side padding clamp(16px, 4vw, 48px). The story is a two-column grid (steps 0.85fr, table 1.15fr, max 1440px, gap clamp(24px, 4vw, 64px)): each step is at least 78vh tall (the hero fills the viewport below the bar), and the meeting table sits in a sticky stage that fills the viewport under the bar while the steps scroll past. Only the step nearest the viewport centre is at full opacity; the others rest at 32%. After the story come full-width bands (max 1240px, padding clamp(64px, 9vw, 120px) vertical, 1px rule on top), a surface-filled results band, and a black closing band with the big CTA centred. At 960px the story becomes one column, the table becomes a compact sticky strip under the bar (ground fill, 1px rule beneath), seat detail hides, every step is shown at full opacity and the two-column lists stack.

## Elevation & Depth

Mostly flat. Structure comes from 1px rules and the step from ground to surface, not from lift. Panels, the control bar and the tooltip carry one soft shadow token (`0 1px 2px rgb(20 21 23 / 0.08), 0 6px 18px -8px rgb(20 21 23 / 0.18)`) that only separates surface from ground. Sign keylines are inset box-shadows (2px yellow inside a 1px black edge on location signs; 2px black inside the chosen cell), which is a painted edge, not depth.

The meeting table is the one place with more weight: seat cards carry a slightly deeper resting shadow (`0 1px 2px rgb(20 21 23 / 0.08), 0 10px 24px -14px rgb(20 21 23 / 0.35)`) and the slab casts `0 18px 40px -20px rgb(20 21 23 / 0.6)` under its painted keyline, so the table reads as an object seen from above. Both are static; neither changes on hover.

### Named Rules
**The Painted Not Lifted Rule.** Nothing rises on hover. State is shown by a colour change, a keyline, or a 2px outline, never by a larger shadow or a lift.

## Shapes

Square-cornered throughout: 2px on signs, buttons, panels, inputs and callouts; 1px on plan-board cells, swatches and limit bullets. Limit bullets are 10px red squares, not dots. The only round shapes are the 6px "ranked" dot on plan cells and the icons. Rules are 1px; keylines are 2px (3px on the rulebook sign and on turn-2 blocked cells). The empty state uses a 1px dashed rule-strong border.

On explainer surfaces the same language holds at larger size: option cells on the slab are 1px-cornered squares (aspect ratio 1, 2px gutters), list bullets are 14px green or red squares, and the "Signed" stamp is the only rotated shape (-4deg, 2px green inset keyline).

## Components

### Sign panels
The signature primitive. Inline condensed uppercase label, 7px 10px padding, 2px corners, optional leading icon.
- **Location:** black, yellow type, 2px yellow inset keyline with a 1px black outer edge. Current protocol step, flight number, brand mark.
- **Direction:** yellow, black type. Plan IDs that are recommended, legend "Go".
- **Mandatory:** red, white type. Rejections, legend "Stop".
- **Go:** green, white type. Agreed and fully signed.
- **Quiet:** transparent with a 1px rule-strong inset keyline. Neutral identifiers (tail number, stated limits).

### Direction sign (signature)
The outcome sign in the decision panel: a solid yellow block, 40px arrow icon, 12px label line, 34px plan ID and a body line describing the plan. When no agreement is safe it becomes the **rulebook sign**: black with a 3px yellow inset keyline and yellow type.

### Plan board (signature)
Every plan is a 34px cell. White with a 1px rule keyline means it passes every limit. Red with the party code (ATC, AIR, GND) in white means ruled out; a 3px black inset marks a limit added in turn 2. A 2px green inset means shortlisted, a 6px ink dot means ranked, and the chosen plan is yellow with a 2px black inset and an arrow. Hover and focus show a 2px ink outline and a black tooltip with a yellow heading.

### Buttons
- **Shape:** square (2px), condensed 700 16px uppercase, 0.05em tracking, 10px 16px padding, leading icon.
- **Primary:** Direction Yellow with a faint 1px inset edge. Hover lightens to Lit Yellow.
- **Secondary:** white with a 1px rule-strong inset keyline; hover darkens the keyline to ink.
- **Small:** 7px 10px, 14px type.
- **Active:** moves down 1px. **Disabled:** 55% opacity. **Busy:** icon spins.
- **Focus (global):** 2px black outline, 2px offset, 4px yellow halo.
- **Large CTA (explainer surfaces):** a link styled as the primary button at Persuade scale: condensed 700 19px uppercase, 0.05em tracking, 15px 20px padding, trailing arrow, same faint inset edge. Hover goes to Lit Yellow and nudges the arrow 3px right; active moves down 1px. **Big** (24px, 20px 28px) closes the page on the black band; **Small** (15px, 9px 12px) sits in the bar and drops "Open the" on phones. Every CTA on a page points to the same place, the live demo.
- **Text link:** Barlow 500, ink, underline offset 4px, trailing chevron; the secondary action beside a CTA.

### Tags
Condensed 600 11px uppercase, 4px 6px, 1px currentColor inset keyline. The **synthetic** tag is a yellow-tint fill with deep yellow ink and is mandatory on any made-up private value.

### Inputs / Fields
- **Select:** white, 1px rule-strong border, 2px corners, custom chevron; hover border goes to ink.
- **Segmented control:** white track with a 1px rule-strong border; the checked option is a solid black segment with white type; disabled options fall to surface-2 and ink-3.
- **Checkbox:** 18px native box with red accent for the pressure test (it is a mandatory-style action) and black accent for board filters.

### Navigation
Tabs in the black top bar: condensed 600 15px uppercase, light grey at rest, white on hover, yellow text with a 3px yellow underline when selected. The protocol strip is a row of step labels joined by 22px 1px rules: grey ahead, green when done, red when failed, and the current step becomes a location sign.

### Meeting table (signature, explainer surfaces)
A top-down meeting: three seat cards around a dark slab, with the chair below. Grid of 1fr / 1.45fr / 1fr with areas airline (top), ATC and ground (left and right of the slab), chair (bottom); 14px gap, max 760px wide, 14px text.
- **Seat:** surface card, 2px corners, 12px padding, the seat shadow, a location sign naming the party with its icon, and a 13px ink-3 role line.
- **Chair:** no card; a quiet sign ("Chair: plain code, no AI") centred under the slab.
- **Slab:** slab fill, Slab Ink text, 2px yellow keyline inset 10px (6px inset, 1px keyline at 960px), at least 360px tall. A location sign at the top names the current round; the disrupted flight (location sign, 22px route line, Slab Ink Mid date) sits in the middle and scales to 86% once options appear.
- **Option grid:** 4 rows (gates) by 25 columns (delay steps) of square cells, untested in mid tarmac grey.

Step states, advanced by whichever scroll step is nearest the viewport centre:
1. **Before:** flight only.
2. **By phone:** a yellow condensed "phone · phone · phone" line on the slab.
3. **Secrets:** each seat reveals a lock line on surface-2. Private, stays at the seat.
4. **Round 1:** each seat sends a red rule note (white text, 2px corners); secrets dim to 55%.
5. **Chair checks:** options turn red (struck) or Slab Ink (safe) with a 6ms per-cell stagger; the count reads 101 then "34 safe".
6. **Round 2:** each seat shows its first choice in condensed uppercase above a 1px rule; rule notes fall back to a red outline.
7. **Round 3:** green "Signed" stamps land on each seat, the chosen option turns yellow, and the yellow direction sign with the plan lands in the slab (700ms drop and settle).
8. **Stress test:** the airline seat shows the pressure message on yellow-tint with the refusal in green.
9. **Rulebook:** stamps and plan clear; a location sign "No deal: rulebook plan" takes the plan's place.
10. **Sign-off:** each seat adds a green "approved" line with a user-check icon.

Reveals animate max-height and opacity (520ms and 360ms, standard ease); nothing lifts. The table is decorative (aria-hidden); the step text carries the meaning.

### Panels and callouts
Panels: surface fill, 2px corners, the soft surface shadow, 16px 24px 24px padding, uppercase title with a short sentence-case explanation beneath. Callouts and banners: tint fill with matching deep ink and a leading icon (red for violations, yellow for "needs a human", green for verified).

## Do's and Don'ts

### Do:
- **Do** give each signal colour one job: black-and-yellow for location, yellow for direction, red for mandatory, green for signed.
- **Do** set every label, ID, state and action in Barlow Condensed uppercase, and every sentence in Barlow sentence case.
- **Do** divide with 1px rules (rule) and keep corners at 2px (1px on plan cells).
- **Do** pair every signal colour with a word, party code or icon.
- **Do** mark synthetic values with the synthetic tag and scripted agents with "no AI".
- **Do** keep numerals tabular.
- **Do** keep the meeting table's slab dark with its painted yellow keyline, and let sign colours keep their jobs on it.

### Don't:
- **Don't** use red, yellow or green as decoration or emphasis.
- **Don't** show more than one solid yellow recommendation sign at once.
- **Don't** round corners beyond 2px or lift elements on hover.
- **Don't** set prose in the condensed face or in uppercase.
- **Don't** use em dashes in UI copy.
