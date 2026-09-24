# 🥤 Juicetification: The Lean Rush

**An experiential lean-operations simulation for the classroom.**
Students inherit a chaotic juice bar, run it through a 15-minute morning rush, and
then redesign it round after round. The engine is tuned so that genuine lean
improvements are rewarded and the classic traps — batching, made-ahead inventory,
gold-plated equipment — visibly backfire. Students *discover* the seven wastes
rather than being lectured on them.

Built as a single-file [Streamlit](https://streamlit.io) app with an embedded
discrete-event simulation. No database, no server, no accounts.

---

## Quick start

```bash
pip install -r requirements.txt
streamlit run app.py
```

Then open the URL Streamlit prints (usually <http://localhost:8501>).

Requires Python 3.9+. Dependencies: `streamlit`, `pandas`, `matplotlib`, and the
optional `streamlit-sortables` (enables true drag-and-drop for the layout; without
it the app falls back to ◀ ▶ buttons and works identically).

---

## Learning objectives

By the end of a session a student can:

| # | Outcome |
|---|---------|
| 1 | **Identify** which of the seven wastes (TIMWOOD) dominates from operational data |
| 2 | **Apply** the 5 S's as concrete counter-measures to five of those wastes |
| 3 | **Explain** cycle time, work-in-process, and where a bottleneck actually is |
| 4 | **Use** standard work to reduce *variation*, not just the average |
| 5 | **Design** a visual workplace that prevents defects |
| 6 | **Run** a PDCA / kaizen improvement cycle and name each phase |
| 7 | **Evaluate** whether a lean intervention is worth its cost — the central judgement of the game |

---

## How a round works — the PDCA loop

Each screen is one turn of the Plan-Do-Check-Act cycle, read top to bottom:

1. **CHECK** — the last rush's Lean Score, profit, KPIs, the 7-wastes dashboard,
   the 5S board, and your progress toward the three objectives.
2. **ACT** — the **Coaching Kata**. The coach states the target condition and the
   actual condition, then asks *"what obstacle is most in your way?"* as a
   multiple-choice question you must answer before you can run again.
3. **PLAN** — seven decisions, one per waste. You may rehearse: an automatic
   dry-run previews your plan's Δ profit, and an optional profit-impact test
   ranks every lever available this round. You then **commit a prediction**.
4. **DO** — the big RUN button in the sidebar fires the rush, and next round's
   CHECK tells you whether your prediction was right.

*Act flows straight into the next Plan — that is kaizen.*

---

## The decisions

Each of the seven wastes has one counter-measure decision. Five of them are
exactly the 5 S's; the last two need quality tools and capacity.

| Waste | Counter-measure | Lean concept | Cost / rush |
|-------|-----------------|--------------|-------------|
| Overproduction | One-piece flow (batch 1, no pre-made) | 5S #1 Sort | free |
| Transport | Line the stations up in process order | 5S #2 Set in order | $1 |
| Motion | Clean & label stations | 5S #3 Shine | $3 – $6 |
| Overprocessing | Standard work (4 tiers) | 5S #4 Standardize | $0 – $8 |
| Inventory | One-piece flow **or** FIFO rotation **or** pull/kanban | 5S #5 Sustain | free / $1 / $3 |
| Defects | Visual order signals (4 tiers) | Visual workplace | $0 – $10 |
| Waiting | Right-size staff or blenders at the bottleneck | Capacity | varies |

**Improvements have tiers, and the top tier is usually a trap.** The cheap first
tier delivers most of the benefit (recipe cards alone can add ~$40/rush); the
premium tier often loses money. Discovering where the value stops is the point.

---

## The Lean Score

A 0–100 composite of five dimensions, each a **per-drink rate** so the score means
the same thing in a quiet shop or a slammed one:

| Dimension | Weight | What it measures |
|-----------|--------|------------------|
| Waste | 40% | Spoiled / unsold units per customer |
| Correctly served | 25% | Customers served *right*, of those who arrived |
| Quality | 15% | Wrong-order rate |
| Speed | 10% | Average cycle time |
| Flow | 10% | Work-in-process congestion |

Waste carries the most weight — eliminating it is the heart of lean, and it keeps
the overproduction trap from ever winning. The score rises smoothly and
monotonically along the improvement path, so every genuine change is visible.

---

## Finishing — the three objectives

The core simulation is complete only when **all three** are true:

- ✅ **Every waste worth addressing is addressed** — each has its counter-measure
  decision in place, *or* nothing available for that waste would pay for itself in
  this shop, in which case leaving it alone is itself the lean decision
- ✅ **Lean Score ≥ 70**
- ✅ **Running a profit** (> $0)

A live "Objectives (x/3)" panel shows exactly what is still missing. There is no
round-count shortcut — the number of rounds is however many the student needs.
Both thresholds sit well below what a well-run shop reaches in every random
scenario, so the goal is always achievable.

---

## The debrief and assessment

Most of the learning in a simulation happens in the debrief, so the game gates on
it. Once the objectives are met, students get:

- a **per-waste table** — what they did to each of the seven, the tool, the result;
- a written **"your lean journey"** narrative and whole-arc charts;
- the **ROI reveal** — a leave-one-out analysis of what each of *their* decisions
  actually contributed, held back until now so they had to discover it;
- the **lean priority ladder** — the general rule their game just demonstrated;
- **four written reflections** (biggest lever, what wasn't worth it, prediction
  accuracy, and transfer to a real process);
- a **five-question knowledge check** with instant feedback and a score.

**The PDF report can be downloaded at any time after the first round, and its
first page says plainly whether it is COMPLETE or INCOMPLETE** — an incomplete one
also lists exactly what is outstanding (objectives not yet met, reflections or
knowledge-check questions unanswered, no name entered) and is tagged in the page
footer and the file name. It is a clean, auto-paginating, multi-page document —
title page with KPI cards, a round-by-round table, decisions per round, and every
recorded answer — ready to submit to an LMS.

---

## Instructor notes

- **Every student gets a different shop.** Each session generates a random but
  always-solvable scenario: scrambled layout, inherited batch size and pre-made
  pile, one secretly slow station, plus demand, customer patience and crew
  error-rate. The best set of decisions genuinely differs between students, so
  answers can't be copied — and comparing strategies makes a good discussion.
- **Two modes.** *Guided* walks through the wastes and opens one decision at a
  time (the coach's highest-payoff pick); *Free play* unlocks every control.
- **Grade the reasoning, not the score.** The report's reflections and knowledge
  check are the assessable artifact; the Lean Score is feedback, not the goal. A
  first-round panel in the app now tells students up front that the debrief is
  required and reviewed, which discourages "max everything" speed-runs.
- **Plan ~30–45 minutes, ideally in one sitting.** Without per-student storage
  configured, progress lives only in the browser session and is lost on refresh
  or after the tab sits idle (Streamlit reclaims idle sessions). To let students
  pause and resume, hand out **signed-in `?game=…&sid=…` links** with storage
  configured (see *Per-student progress and resume* above) — the app then saves
  and restores automatically and shows a "Signed in / progress saved" note.
- **Two modes.** *Guided* walks through the wastes and opens one decision at a
  time (the coach's highest-payoff pick); *Free play* unlocks every control.
- **Scenario settings** (demand, replications) can be overridden in the sidebar.
- Class discussion prompts that work well: *Why did your best first move differ
  from your neighbour's? Which change did you keep that you shouldn't have?*

---

## Instructor configuration (the Director)

The app ships with sensible defaults and needs no configuration to run. For
instructors who want to tune the scenario or the grading, it also speaks the
shared **Juicetification Director** protocol via two small files — `manifest.py`
(the parameter schema) and `juice_director.py` (the shared, unmodified loader).

- **With no URL parameters, the app is unchanged** — it uses the built-in
  defaults, so `streamlit run app.py` behaves exactly as documented above.
- **`?manifest=1`** makes the app emit its parameter schema as JSON, so the
  Director can discover what is configurable.
- **`?cfg=<base64-json>`** overrides any parameters — for example, forcing every
  student into a *Slammed* rush and raising the passing Lean Score to 85, or
  widening the inherited over-batching range.
- **`?seed=<int>`** pins the random scenario, so a whole section faces the same
  shop; **`?sec=<code>`** tags the section.

Configurable parameters (see `manifest.py`) cover the **scenario** (bottleneck
bias and slowdown range, rush-intensity mix, demand multiplier, customer
patience, baseline defect range, inherited batch and made-ahead ranges), the
**rush** (length, blend-setup and hand-off times), and **grading** (the Lean
Score and profit required to finish). Nothing in the Director changes when a
manifest is edited — that is the point of the split.

### Per-student progress and resume (`student_store.py`)

The app can persist each student's progress and write a completion record via
the shared `student_store` module. It is a **safe no-op until configured**, so
`streamlit run app.py` works with no secrets set. When configured (an encryption
key plus Dropbox credentials — see the module header), the app:

- treats a **Director game link (`?game=<code>`) as a managed session** and
  loads that game's saved configuration straight from storage;
- **gates on a student ID** before the lab starts (any `?game=` link, or any
  storage-enabled deployment, requires the student to identify themselves);
- gives each student a **stable, unique scenario** derived from their ID, so a
  refresh or a return visit lands on the same shop;
- **autosaves** progress after each meaningful step and **restores** it on load
  (`?sid=` in the URL makes resume automatic); and
- **records a completion** (final P&L) the Director can read for grading.

**Troubleshooting.** If students aren't asked to log in or progress isn't saving,
open the app with **`?diag=1`** — a self-check page that shows whether this
deployment actually detects the storage secrets (presence only, never values).
`storage enabled` must be true; it needs `DB_ENCRYPTION_KEY` plus either
`DROPBOX_ACCESS_TOKEN` or all of `DROPBOX_REFRESH_TOKEN` + `DROPBOX_APP_KEY` +
`DROPBOX_APP_SECRET`, configured as this app's own Streamlit secrets.

Only game logic-free progress state is stored — decisions, round, history,
reflections and coach state — as plain JSON; figures, RNGs and transient
simulation objects are never persisted. Persistence requires the `cryptography`
and `dropbox` packages (listed in `requirements.txt`); they are imported lazily,
so a deployment that leaves storage unconfigured still runs without using them.

---

## Design notes

- **Discrete-event engine** — a heapq scheduler with non-homogeneous Poisson
  arrivals (thinning), customer patience/abandonment, station contention, and
  batch/blend setup amortisation. Every round runs multiple replications, so
  students also see the *spread*, not just the average.
- **The coach** rotates through several questions per waste, always targeting the
  waste whose fix would add the most profit right now (it dry-runs each option),
  and it withholds the specific answer until the student asks for help.
- **Costs are real.** Every lean practice carries an upkeep cost per rush, so
  "lean is always good" is not a winning strategy.

---

## Repository layout

```
juicetification-lean-rush/
├── app.py                     # the entire application — engine + UI in one file
├── juice_director.py          # shared Director config loader (drop-in, unmodified)
├── manifest.py                # instructor-configurable parameter schema
├── student_store.py           # per-student progress/resume (drop-in; no-op unless configured)
├── requirements.txt           # Python dependencies
├── README.md
├── LICENSE                    # MIT
├── .gitignore
├── docs/
│   ├── instruction_sheet.pdf  # one-page visual student handout
│   ├── pedagogical_review.md  # learning-theory analysis behind the design
│   └── academic_paper/
│       ├── Juicetification_The_Lean_Rush_paper.docx   # design & pedagogy paper
│       └── figures/           # figures used in the paper (fig1–fig5)
└── tools/
    ├── make_instruction_sheet.py   # regenerates docs/instruction_sheet.pdf
    ├── make_paper_figures.py       # regenerates the paper figures from the engine
    └── make_paper.js               # rebuilds the .docx paper (Node; `npm i docx`)
```

Run any tool from the repository root, e.g. `python tools/make_instruction_sheet.py`.

---

## License

Released under the MIT License — see `LICENSE`.

---

## Version

**v1.0** — first public release.
