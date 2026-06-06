# chargeback-prediction-model — Project Context for Claude

## What this project is

A predictive model that connects upstream data quality conditions to downstream
chargeback outcomes, quantifying the preventable portion and generating a ranked
remediation roadmap. Built as a portfolio piece for Lailara LLC demonstrating
the practice's core move: turning a written-off cost into a quantified,
controllable, preventable one.

**Business question this project answers:** Which upstream data quality
conditions will generate chargebacks, at what probability and dollar value,
so the brand can intervene before shipment?

**Tier:** Heavy

## Stack and tools

- Primary language: TBD (likely Python)
- Key packages/libraries: TBD — settled in planning
- Database: TBD — Cinderhaven Data Platform marts (fct_deductions, product
  data, EDI history, shipment data)
- Entry point: TBD
- Other tools: TBD

## Project files

- CLAUDE.md (this file) — permanent rules and facts
- DECISIONS.md — durable choices and reasoning
- HANDOFF.md — current session state
- PLAN.md — current work arc
- FAILURES.md — things tried that didn't work
- docs/solutions/ — documented solutions to past problems (architecture patterns, bugs, workflow learnings), organized by category with YAML frontmatter (module, tags, problem_type)

Read PLAN.md and HANDOFF.md at session start. DECISIONS.md and
FAILURES.md as relevant.

## Voice and standards

- Economist style for all written deliverables: sober, declarative,
  data-forward
- No marketing voice ("leverage," "synergy," "best-in-class," "unlock")
- No hedging that softens a real finding
- Charts must be readable by non-data-scientist audiences
- Every risk score must come with a plain-language operational explanation

## Rules

### Honesty and judgment

- Say "I don't know" or "I can't verify this" instead of guessing.
  This applies to industry context, technical claims, what code did,
  and anything else.
- Tell me what I need to hear, not what I want to hear. If a decision
  looks wrong, say so. If code I wrote has problems, say so. Honest
  assessment, not validation.
- If a rule in this file is too vague to verify whether you're
  following it, flag it for revision rather than guessing at compliance.

### Building and proposing

- No speculative abstractions. If something isn't needed right now,
  don't build it. Helper functions get added when called by real code,
  not in anticipation. Parameters get added when there's a second use
  case, not the first.
- When proposing a tool, library, or approach, present at least two
  alternatives with tradeoffs, even if one is clearly preferred. Do
  not propose a single solution and move on.
- Tie proposals back to the business question this project is
  answering. If you can't connect a proposal to that question, the
  proposal is probably fluff and should be reconsidered.
- Interpretability mandated. Black-box models are barred — a CFO needs
  to see WHY a SKU is high-risk, not just that it is. Tree-based with
  explicit feature attribution (SHAP-style) is the current direction.

### How to work the project

- Work in vertical slices, not horizontal phases. Build one feature
  end-to-end (working from input to output) before moving to the next.
- When a feature is working, suggest a simple test to verify it stays
  working.
- Do not start tasks outside the current PLAN.md arc without flagging
  it to the user first.
- Do not refactor unrelated code unprompted.
- Do not rename things unless asked.

### Git branching

- Before risky or experimental changes, suggest creating a branch.
- What counts as "risky": changing how the project is structured,
  trying a new library, rewriting a working feature.
- Keep it simple: `git checkout -b experiment/short-description`
  before the change, merge back to main if it works.

### Scope creep detection

- Periodically check whether the current work matches PLAN.md.
  If the user has been building something not in the plan for more
  than ~15 minutes, flag it.
- Also flag if the user keeps adding tasks to PLAN.md without
  completing existing ones.

## Working with PLAN.md

PLAN.md defines the current arc of work. Read it at session start.

- Mark tasks complete as they're finished, in the same commit as the work
- If a task is wrong-sized, in the wrong order, or no longer relevant,
  flag it rather than silently restructuring
- "Out of scope" items are decisions, not suggestions

## Session reminders

### Session start protocol

1. Read CLAUDE.md, PLAN.md, and HANDOFF.md
2. If HANDOFF.md's most recent entry is more than 24 hours old AND
   there are uncommitted changes, flag this
3. Briefly state the starting point from HANDOFF.md so the user
   confirms you're caught up
4. Confirm the current PLAN.md arc is still active
5. Check the Improvement History section of PLAN.md for overdue audits
6. Remind the user: `/log` (save checkpoint), `/wrap` (end session),
   `/improve` (review and improve), `/clarify` (scope the work)

### Watchdog triggers

- User finishes a task → suggest `/log`
- Approaching context limit → suggest `/compact` or `/wrap`
- User signals end of session → suggest `/wrap`
- User seems unsure what's next → run `/next`

## Defaults

- Default to flagging gaps rather than filling with plausible-sounding
  but unverified content
- Default to short responses unless the task is substantive
- Default to asking before promoting a log entry to a DECISIONS.md entry
- Default to answering, not offering to answer

## Data contract

Data contract: 50 SKUs / 5 product lines / 6 retailers per CINDERHAVEN_CANONICAL.md

Canonical retailers: WMT (Walmart, 180 doors), COSTCO (Costco, 60 doors),
WHOLEFOODS (Whole Foods, 120 doors), SPROUTS (Sprouts, 90 doors),
KGR (Kroger, 150 doors), REGIONAL (Regional Group, 40 doors).

All demo fixtures, test data, and generated JSON must use only these six
retailer codes. The generator script (`scripts/generate_sample_json.py`)
is the source of truth for demo data.
