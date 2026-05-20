---
name: writing-dx-overview
description: Use when a design spec has been approved and you want to show how the planned SDK API will feel to use — produces a hand-authored HTML developer-experience walkthrough.
---

# Writing a DX Overview

## Overview

A DX overview is a usage-first HTML walkthrough of a *planned* SDK API, authored from
an approved design spec. It answers "how does a developer actually use this?" — imports,
real call sequences, idiomatic snippets — not "how is it designed."

It is HTML-native (no Markdown twin).

## When to Use

- A design spec has been approved.
- The spec introduces or changes a public SDK API (new classes, methods, parameters).
- The user accepted the "Want a DX overview?" offer.

**When not to use:** internal-only changes with no public API surface; bug-fix specs
that add no new usage.

## Process

1. Read the approved design spec end to end. List every public symbol it introduces.
2. Look in the spec's own directory for an earlier `*-DX.html` file. If one exists,
   open it as a visual-identity reference. If none exists, rely on the Required
   Structure below — do not assume any specific file exists, and never cite a file you
   have not confirmed is present.
3. Dispatch a subagent to author the HTML. The subagent MUST invoke the
   `frontend-design:frontend-design` skill for the visual layer. Brief it with: the spec
   path, the Required Structure below, the output path, and any reference file actually
   found in step 2.
4. Save the HTML beside the spec, named like the spec with the `-design` suffix
   replaced by `-DX` and a `.html` extension
   (e.g. `…-context-management-design.md` → `…-context-management-DX.html`).
5. Read the result back and confirm every snippet uses only API from the spec.

## Required Structure

The DX overview HTML MUST contain, in order:

1. **Metadata block** — status and scope (e.g. "DX preview — Phase 1 API").
2. **Table of contents** — anchored links to each section.
3. **Numbered usage sections** — each one a real flow: a runnable code snippet + prose
   explaining it + an optional "when to use" callout, diagram, or comparison table.
4. **API cheat sheet** — a closing table of every public symbol with a one-line
   description.

## Quality Bar

- Every code snippet uses ONLY public API present in the spec — never invent names.
- When the spec names a method but not its full signature, pass only arguments the
  spec specifies, or mark illustrative arguments with an inline comment
  (e.g. `# signature illustrative — confirm on implementation`). Never present an
  unverified signature as if it were confirmed.
- Show the happy path AND the filtered / edge variants of each flow.
- Call out backward-compatibility explicitly where the spec mentions it.
- Snippets must be copy-paste runnable, not pseudocode.

## Adding Diagrams & Metrics

Add a diagram or a metrics table ONLY when it makes a flow or trade-off clearer — never
as decoration. When you do add one, brief the `frontend-design` subagent to render it
inline in the document's own theme (same colors, fonts, spacing).

**Diagrams — add when a flow is non-linear and hard to follow in prose.** Good
candidates: data flow across components, before/after of an API change, an object's
lifecycle, or which stage/agent owns which step. Render inline as SVG or a styled
HTML/CSS block. Skip the diagram for a single linear call sequence — the code snippet
already shows it.

**Metrics — add when the spec describes alternatives with different latency, cost, or
quality characteristics.** Use a comparison table with one column per trade-off
(e.g. latency, token cost, control), and add a callout when one path is the production
default and another a cheaper/slower fallback. Use only figures the spec actually
provides; if it gives none, use relative terms (highest / medium / lowest) and label
them as relative, not measured. Never invent latency or cost numbers.

## Common Mistakes

| Mistake | Fix |
|---------|-----|
| Restating the design ("the system has X, Y, Z") | Show a developer *calling* X, Y, Z |
| Inventing API not in the spec | List the spec's public symbols first; use only those |
| No cheat sheet | The closing cheat-sheet table is mandatory |
| Pseudocode snippets | Every snippet must run as written |
| Citing a reference file that may not exist | Reference only files confirmed present in the spec's directory |
| Diagram or metrics table that adds nothing | Add a visual only when it clarifies a flow or trade-off |
| Invented latency / cost numbers | Use only figures from the spec; otherwise relative terms, labeled as relative |
